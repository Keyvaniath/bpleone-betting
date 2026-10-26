"""Seed extension (2026-10-26): picks priced at the pipeline's OTHER placeholders.

pipeline.py filled `ml_away or 100`, `ml_home or -110`, `total or 8.5` when no
book was loaded. The 10/23 re-price matched only -110. This finds:
  * settled MLB moneylines recorded at exactly +100 with no book_american
  * settled pod totals recorded at the 8.5 line
and looks each up in the git history of data/espn_odds.json (DraftKings via
ESPN): last PRE-GAME snapshot at/before the pick, else the first pre-game one
after. Output rows use the ml_reprice_2026_10.json row format; totals rows add
`real_total`.
"""
import datetime as dt, json, os, subprocess, sys
from collections import defaultdict

REPO = sys.argv[1]
OUT = sys.argv[2]
sys.path.insert(0, os.path.join(REPO, "python"))
import all_picks_tracker as apt  # noqa: E402


def load(p):
    return json.load(open(os.path.join(REPO, p), encoding="utf-8"))


L = load("data/all_picks_ledger.json")["picks"]
A = load("data/ledger_archive.json").get("picks") or []
seed = {r["pick_id"] for r in load("data/ml_reprice_2026_10.json")["rows"]}

cands = []
for origin, rows in (("L", L), ("A", A)):
    for p in rows:
        if not p.get("settled") or p.get("voided") or p["pick_id"] in seed or p.get("repriced"):
            continue
        side = apt._is_mlb_moneyline_market(p)
        if side and p.get("fair_american") == 100 and p.get("book_american") is None:
            cands.append(("ml", origin, side, p))
        elif p.get("source") == "pod" and str(p.get("market") or "").upper() in ("OVER_8.5", "UNDER_8.5"):
            cands.append(("total", origin, None, p))
print("candidates", len(cands))

dates = sorted({str(c[3]["date"])[:10] for c in cands})
want = set()
for d in dates:
    d0 = dt.date.fromisoformat(d)
    for k in (-1, 0, 1):
        want.add((d0 + dt.timedelta(days=k)).isoformat())

log = subprocess.run(["git", "-C", REPO, "log", "--format=%H %cI", "--", "data/espn_odds.json"],
                     capture_output=True, text=True).stdout.split("\n")
commits = []
for l in log:
    if not l.strip():
        continue
    h, t = l.split()
    tu = dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc)
    if tu.date().isoformat() in want:
        commits.append(h)
print("snapshots to read", len(commits))

# matchup -> list of (snapshot_utc, commence_utc, status, market)
snaps = defaultdict(list)
for h in commits:
    try:
        o = json.loads(subprocess.run(["git", "-C", REPO, "show", f"{h}:data/espn_odds.json"],
                                      capture_output=True).stdout.decode("utf-8"))
    except Exception:
        continue
    ga = str(o.get("generated_at") or "")[:19]
    try:
        g_at = dt.datetime.fromisoformat(ga)          # CI clock = UTC
    except ValueError:
        continue
    for g in o.get("games") or []:
        if g.get("sport") != "MLB" or not g.get("market"):
            continue
        snaps[g["matchup"]].append((g_at, g.get("commence_time"), g.get("status"), g["market"]))


def et_date(ct):
    try:
        return (dt.datetime.fromisoformat(ct.replace("Z", "+00:00")) - dt.timedelta(hours=4)).date().isoformat()
    except Exception:
        return None


rows = []
for kind, origin, side, p in cands:
    mu = str(p.get("player_or_matchup") or "")
    d = str(p["date"])[:10]
    try:
        rec = dt.datetime.fromisoformat(str(p.get("recorded_at"))[:19])  # CI clock = UTC
    except ValueError:
        rec = None
    pre = sorted([s for s in snaps.get(mu, []) if s[2] == "pre" and et_date(s[1] or "") == d],
                 key=lambda s: s[0])
    before = [s for s in pre if rec and s[0] <= rec]
    pick = (before[-1], "before_pick") if before else ((pre[0], "first_pregame_after") if pre else (None, None))
    s, chosen = pick
    base = {"pick_id": p["pick_id"], "origin": origin, "date": d, "matchup": mu,
            "market": p.get("market"), "source": p.get("source"), "old_fair": p.get("fair_american"),
            "result": p.get("result"), "old_payout": p.get("payout_units"), "kind": kind}
    if kind == "ml":
        px = s[3].get("ml_home" if side == "home" else "ml_away") if s else None
        if px is None:
            rows.append({**base, "side": side, "status": "unpriced"})
        else:
            dec = 1 + px / 100 if px > 0 else 1 + 100 / abs(px)
            newp = round(dec - 1, 4) if p.get("result") == "won" else (-1.0 if p.get("result") == "lost" else 0.0)
            rows.append({**base, "side": side, "status": "repriced", "book_american": px,
                         "snapshot_at": s[0].isoformat(), "chosen": chosen, "new_payout": newp})
    else:
        tot = s[3].get("total") if s else None
        if tot is None:
            rows.append({**base, "status": "unpriced_total"})
        elif float(tot) == 8.5:
            rows.append({**base, "status": "line_real", "real_total": tot, "snapshot_at": s[0].isoformat()})
        else:
            rows.append({**base, "status": "unpriced_total", "real_total": tot, "snapshot_at": s[0].isoformat(),
                         "chosen": chosen})

from collections import Counter
print(Counter((r["kind"], r["status"]) for r in rows))
json.dump({"note": ("2026-10-26 extension: picks graded at the pipeline's OTHER placeholders "
                    "(+100 away moneyline, 8.5 total) matched to the real DraftKings pre-game line "
                    "from the git history of espn_odds.json. ml repriced/unpriced as on 10/23; a pod "
                    "total whose real line was not 8.5 was a bet on a line that did not exist -> "
                    "voided (unpriced_total); line_real = 8.5 was the real line, kept."),
           "n": len(rows), "rows": rows}, open(OUT, "w", encoding="utf-8"), indent=1)
