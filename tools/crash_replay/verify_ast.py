"""For every changed .py: AST(HEAD) with the intended rewrite applied must equal
AST(working copy) minus the inserted _nz/_fmtv helpers. Lists files that differ
(those contain changes beyond the mechanical rewrite -- expected only for the
hand-edited files)."""
import ast, subprocess, sys

REPO = sys.argv[1]
names = subprocess.run(["git", "-C", REPO, "diff", "--name-only", "--", "python"],
                       capture_output=True, text=True).stdout.split()


class T(ast.NodeTransformer):
    def visit_Call(self, n):
        self.generic_visit(n)
        if (isinstance(n.func, ast.Attribute) and n.func.attr == "get" and len(n.args) == 2
                and not n.keywords and isinstance(n.args[1], ast.Constant)
                and type(n.args[1].value) in (int, float)):
            bare = ast.Call(func=n.func, args=[n.args[0]], keywords=[])
            if n.args[1].value == 0:
                return ast.BoolOp(op=ast.Or(), values=[bare, n.args[1]])
            return ast.Call(func=ast.Name(id="_nz", ctx=ast.Load()), args=[bare, n.args[1]], keywords=[])
        return n


def strip_helpers(tree):
    tree.body = [s for s in tree.body if not (isinstance(s, ast.FunctionDef) and s.name in ("_nz", "_fmtv"))]
    return tree


def norm(tree):
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


class Undo(ast.NodeTransformer):
    """Map the new tree back: (X.get(k) or 0) / _nz(X.get(k), D) -> X.get(k, D)."""
    def visit_BoolOp(self, n):
        self.generic_visit(n)
        if (isinstance(n.op, ast.Or) and len(n.values) == 2 and isinstance(n.values[0], ast.Call)
                and isinstance(n.values[0].func, ast.Attribute) and n.values[0].func.attr == "get"
                and len(n.values[0].args) == 1 and isinstance(n.values[1], ast.Constant)
                and type(n.values[1].value) in (int, float) and n.values[1].value == 0):
            g = n.values[0]
            return ast.Call(func=g.func, args=[g.args[0], n.values[1]], keywords=[])
        return n

    def visit_Call(self, n):
        self.generic_visit(n)
        if isinstance(n.func, ast.Name) and n.func.id == "_nz" and len(n.args) == 2 \
                and isinstance(n.args[0], ast.Call) and isinstance(n.args[0].func, ast.Attribute) \
                and n.args[0].func.attr == "get" and len(n.args[0].args) == 1:
            g = n.args[0]
            return ast.Call(func=g.func, args=[g.args[0], n.args[1]], keywords=[])
        return n


diff_files = []
for nm in names:
    old = subprocess.run(["git", "-C", REPO, "show", "HEAD:" + nm], capture_output=True).stdout.decode("utf-8")
    new = open(f"{REPO}/{nm}", encoding="utf-8").read()
    a = strip_helpers(ast.parse(old))
    b = strip_helpers(ast.parse(new))
    # Compare by undoing the rewrite on the new tree (pre-existing `or 0` forms
    # in HEAD are normalised identically on both sides).
    if norm(Undo().visit(a)) != norm(Undo().visit(b)):
        diff_files.append(nm)
print(f"{len(names)} changed files; {len(diff_files)} with changes beyond the mechanical rewrite:")
for f in diff_files:
    print("  ", f)
