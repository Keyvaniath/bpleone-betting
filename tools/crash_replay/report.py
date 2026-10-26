import json, sys
S = sys.argv[1]
def load(m):
    rows = [json.loads(l) for l in open(f"{S}/run_{m}/results.jsonl", encoding="utf-8")][1:]
    return {r["cmd"]: r for r in rows}
def last(tb):
    ls = [l for l in tb.strip().splitlines() if l.strip()]
    if not ls: return ""
    fr = [l for l in ls if 'File "' in l and "Python313" not in l and "site-packages" not in l]
    loc = fr[-1].strip() if fr else ""
    loc = loc.split("python\\")[-1] if "python\\" in loc else loc[-80:]
    return loc + " || " + ls[-1][:170]
for m in ("base", "offday", "nulls"):
    M = load(m)
    bad = [(c, r) for c, r in M.items() if r["rc"] != 0 or r["batch_errors"]]
    print(f"===== {m.upper()}: {len(bad)} failing / {len(M)}")
    for c, r in sorted(bad):
        print(f"- {c} rc={r['rc']}\n    {last(r['tb']) or (r.get('tail') or '')[-200:].replace(chr(10), ' ')}")
        for be in r["batch_errors"][:8]: print("    B:", be[:220])
