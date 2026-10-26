"""Every settled MLB moneyline (working + archive) without book_american vs the
DraftKings pre-game line in the git history of data/espn_odds.json."""
import datetime as dt, json, os, subprocess, sys
from collections import defaultdict, Counter

REPO = sys.argv[1]
OUT = sys.argv[2]
sys.path.insert(0, os.path.join(REPO, "python"))
import all_picks_tracker as apt  # noqa: E402

CURATED = None
try:
    CURATED = set(apt.CURATED_SOURCES)
except Exception:
    pass


def load(p):
    return json.load(open(os.path.join(REPO, p), encoding="utf-8"))


L = load("data/all_picks_ledger.json")["picks"]
A = load("data/ledger_archive.json").get("picks") or []
C = []
for origin, rows in (("L", L), ("A", A)):
    for p in rows:
        side = apt._is_mlb_moneyline_market(p)
        if side and p.get("settled") and not p.get("voided") and p.get("book_american") is None \
                and p.get("result") in ("won", "lost", "push"):
            C.append((origin, side, p))
print("candidates", len(C), Counter(o for o, _, _ in C))

days = set()
for _, _, p in C:
    d0 = dt.date.fromisoformat(str(p["date"])[:10])
    for k in (-1, 0, 1):
        days.add((d0 + dt.timedelta(days=k)).isoformat())
log = subprocess.run(["git", "-C", REPO, "log", "--format=%H %cI", "--", "data/espn_odds.json"],
                     capture_output=True, text=True).stdout.split("\n")
hs = [l.split()[0] for l in log if l.strip()
      and dt.datetime.fromisoformat(l.split()[1]).astimezone(dt.timezone.utc).date().isoformat() in days]
print("snapshots", len(hs))
snaps = defaultdict(list)
for h in hs:
    try:
        o = json.loads(subprocess.run(["git", "-C", REPO, "show", f"{h}:data/espn_odds.json"],
                                      capture_output=True).stdout.decode("utf-8"))
    except Exception:
        continue
    ga = str(o.get("generated_at"))[:19]
    for g in o.get("games") or []:
        if g.get("sport") == "MLB" and g.get("market"):
            snaps[g["matchup"]].append((ga, g.get("commence_time"), g.get("status"), g["market"]))


def etd(ct):
    try:
        return (dt.datetime.fromisoformat(ct.replace("Z", "+00:00")) - dt.timedelta(hours=4)).date().isoformat()
    except Exception:
        return None


def dec(a):
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


rows = []
for origin, side, p in C:
    mu = str(p.get("player_or_matchup") or "")
    d = str(p["date"])[:10]
    pre = sorted([s for s in snaps.get(mu, []) if s[2] == "pre" and etd(s[1] or "") == d])
    rec = str(p.get("recorded_at") or "")[:19]
    before = [s for s in pre if s[0] <= rec]
    s, chosen = ((before[-1], "before_pick") if before else ((pre[0], "first_pregame_after") if pre else (None, None)))
    dk = s[3].get("ml_home" if side == "home" else "ml_away") if s else None
    fa = p.get("fair_american")
    r = {"pick_id": p["pick_id"], "origin": origin, "source": p.get("source"), "date": d, "matchup": mu,
         "side": side, "recorded": fa, "dk": dk, "result": p.get("result"),
         "old_payout": p.get("payout_units"), "snapshot_at": s[0] if s else None, "chosen": chosen}
    if dk is not None:
        r["new_payout"] = (round(dec(dk) - 1, 4) if p["result"] == "won" else (-1.0 if p["result"] == "lost" else 0.0))
        try:
            r["gap_cents"] = round(abs((dec(fa) if fa not in (None, 0) else 0) - dec(dk)) * 100, 1)
        except Exception:
            r["gap_cents"] = None
    rows.append(r)

json.dump(rows, open(OUT, "w", encoding="utf-8"), indent=1)
has = [r for r in rows if r["dk"] is not None]
print("with DK line", len(has), "no DK line", len(rows) - len(has))
for lo, hi in ((0, 5), (5, 15), (15, 50), (50, 1e9)):
    b = [r for r in has if r.get("gap_cents") is not None and lo <= r["gap_cents"] < hi]
    print(f"gap {lo:>3}-{hi:<5} n={len(b):4d}  net recorded {sum(float(r['old_payout'] or 0) for r in b):+8.2f}u"
          f" -> at DK {sum(r['new_payout'] for r in b):+8.2f}u   sources {Counter(r['source'] for r in b).most_common(4)}")
print("CURATED_SOURCES attr:", CURATED)
