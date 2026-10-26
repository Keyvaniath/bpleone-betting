"""Find X.get(k, NUMERIC_CONST) used directly as an operand of arithmetic or a
comparison (where a stored None crashes). With --fix, rewrite:
    default 0 / 0.0      -> (X.get(k) or 0)            (exactly equivalent for numbers)
    other numeric default -> _nz(X.get(k), D)           (None-only fallback, keeps a real 0)
and insert the _nz helper where needed."""
import ast, os, sys
from collections import Counter

ROOT = sys.argv[1]
FIX = "--fix" in sys.argv

HELPER = '''

def _nz(v, d):
    """None-safe default (2026-10-26): `.get(k, d)` only covers a MISSING key;
    a key stored as None still reaches the arithmetic and crashes."""
    return d if v is None else v
'''


def is_numget(n):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
            and len(n.args) == 2 and not n.keywords
            and isinstance(n.args[1], ast.Constant) and type(n.args[1].value) in (int, float))


class V(ast.NodeVisitor):
    def __init__(self):
        self.hits = []

    def _chk(self, n, ctx):
        if is_numget(n):
            self.hits.append((n, ctx))

    def visit_BinOp(self, node):
        self._chk(node.left, "binop"); self._chk(node.right, "binop")
        self.generic_visit(node)

    def visit_Compare(self, node):
        self._chk(node.left, "cmp")
        for c in node.comparators:
            self._chk(c, "cmp")
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.USub):
            self._chk(node.operand, "neg")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # names this function compares to None: an assignment feeding one of
        # them may depend on seeing None, so it is left alone
        self._nonechk = getattr(self, "_nonechk", [])
        names = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Compare) and any(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops):
                for x in [n.left] + n.comparators:
                    if isinstance(x, ast.Name):
                        names.add(x.id)
        self._nonechk.append(names)
        self.generic_visit(node)
        self._nonechk.pop()
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            guarded = set().union(*getattr(self, "_nonechk", [set()])) if getattr(self, "_nonechk", None) else set()
            if node.targets[0].id not in guarded:
                self._chk(node.value, "assign")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._chk(node.value, "aug")
        self.generic_visit(node)

    def visit_Call(self, node):
        # round(x.get(k, 0), 2) / int(...) / float(...) / abs(...) / min/max
        if isinstance(node.func, ast.Name) and node.func.id in ("round", "int", "float", "abs", "min", "max", "sum"):
            for a in node.args:
                self._chk(a, "call:" + node.func.id)
                if isinstance(a, (ast.GeneratorExp, ast.ListComp)) and node.func.id in ("sum", "min", "max"):
                    self._chk(a.elt, "gen:" + node.func.id)
        self.generic_visit(node)

    def visit_JoinedStr(self, node):
        for v in node.values:
            if isinstance(v, ast.FormattedValue) and v.format_spec is not None:
                self._chk(v.value, "fmt")
        self.generic_visit(node)


def rewrite(src, hits):
    # ast col offsets are UTF-8 BYTE offsets: edit the byte string, and check
    # every span decodes to exactly the node's source before replacing it.
    b = src.encode("utf-8")
    starts = [0]
    for l in b.split(bytes([10])):
        starts.append(starts[-1] + len(l) + 1)
    edits = []
    need_nz = False
    for n, ctx in hits:
        if n.lineno != n.end_lineno:
            continue
        a = starts[n.lineno - 1] + n.col_offset
        e = starts[n.end_lineno - 1] + n.end_col_offset
        seg = ast.get_source_segment(src, n)
        if b[a:e].decode("utf-8") != seg:
            raise SystemExit(f"offset mismatch line {n.lineno}: {b[a:e]!r} vs {seg!r}")
        obj = ast.get_source_segment(src, n.func.value)
        if not isinstance(n.func.value, (ast.Name, ast.Attribute, ast.Call, ast.Subscript)):
            obj = f"({obj})"      # the parens are not part of the receiver node
        key = ast.get_source_segment(src, n.args[0])
        d = n.args[1].value
        dtxt = ast.get_source_segment(src, n.args[1])
        if d == 0:
            new = f"({obj}.get({key}) or {dtxt})"
        else:
            new = f"_nz({obj}.get({key}), {dtxt})"
            need_nz = True
        edits.append((a, e, new.encode("utf-8")))
    for a, e, new in sorted(edits, reverse=True):
        b = b[:a] + new + b[e:]
    src = b.decode("utf-8")
    if need_nz and "def _nz(" not in src:
        ls = src.split("\n")
        last = 0
        for i, l in enumerate(ls[:250]):
            if l.startswith(("import ", "from ")):
                last = i
        j = last
        if "(" in ls[j] and ")" not in ls[j]:
            while ")" not in ls[j]:
                j += 1
        ls.insert(j + 1, HELPER.rstrip("\n"))
        src = "\n".join(ls)
    return src, len(edits)


tot = Counter(); files = Counter(); changed = 0
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        src = open(p, encoding="utf-8").read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        v = V(); v.visit(tree)
        # dedupe nodes hit twice
        seen = set(); hits = []
        for n, c in v.hits:
            if id(n) not in seen:
                seen.add(id(n)); hits.append((n, c))
        if not hits:
            continue
        for _, c in hits:
            tot[c.split(":")[0]] += 1
        files[f] = len(hits)
        if FIX:
            new, k = rewrite(src, hits)
            compile(new, p, "exec")
            open(p, "w", encoding="utf-8", newline="").write(new)
            changed += k
print("hits", sum(tot.values()), dict(tot), "files", len(files), "rewritten", changed)
print(files.most_common(15))
