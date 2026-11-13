"""Run from the repo root: python tools/cover_study.py  (read-only; restore data/ with git checkout afterwards)

Can the desk model predict SPREAD covers better than a coin flip? (2026-11-13)
Walk-forward, this season, DraftKings' last pre-game spread NUMBER (prices were not recorded before today,
so this tests information, not betting returns). Model margin = sigma * Phi^-1(p_model_home);
cover prob = P(N(mu, sigma) > -home_line). Market cover prob = 0.5 by construction. Pushes dropped.
Pre-registered: no spread desk unless the model's cover log loss beats ln 2 = 0.6931 with a 90% CI clear of zero."""
import os, sys, json, math, random
_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python")
sys.path.insert(0, _PY)
os.chdir(_PY)
import datetime as dt
import game_lines_desk as gld
from statistics import NormalDist
N = NormalDist()

cap = {}
_o = gld.lean_backtest
gld.lean_backtest = lambda rows: (cap.__setitem__("rows", rows), _o(rows))[1]
gld.grow_lines = lambda sport: gld._load(os.path.join(gld.DATA_DIR, f"dk_lines_{sport}.json")).get("events") or {}
SIGMA = {"nfl": 13.5, "nba": 12.0}

for sport in ("nfl", "nba"):
    gld.run_sport(sport)
    rows = cap["rows"]
    lines = gld._load(os.path.join(gld.DATA_DIR, f"dk_lines_{sport}.json")).get("events") or {}
    finals = {(g["date"], g["away"], g["home"]): g for g in gld.load_finals(sport)}
    spread_by = {}
    for eid, ev in lines.items():
        c = ev.get("close") or {}
        if c.get("spread") is None:
            continue
        try:
            d = (dt.datetime.fromisoformat(str(ev["commence"]).replace("Z", "+00:00")) - dt.timedelta(hours=4)).date().isoformat()
        except Exception:
            continue
        spread_by[(d, f"{gld._norm_team(sport, ev.get('away'))} @ {gld._norm_team(sport, ev.get('home'))}")] = float(c["spread"])
    s = SIGMA[sport]
    data = []
    for r in rows:
        sp = spread_by.get((r["date"], r["matchup"]))
        a, h = r["matchup"].split(" @ ")
        g = finals.get((r["date"], a, h))
        if sp is None or not g:
            continue
        margin = g["home_score"] - g["away_score"]
        if margin + sp == 0:
            continue                                   # push
        y = 1.0 if margin + sp > 0 else 0.0            # home covers
        p = min(max(r["p_elo"], 0.01), 0.99)
        mu_model = s * N.inv_cdf(p)
        pm = 1 - N.cdf((-sp - mu_model) / s)
        data.append((y, pm, sp, mu_model))
    n = len(data)
    ll = lambda p, y: -(y * math.log(min(max(p, 1e-6), 1 - 1e-6)) + (1 - y) * math.log(1 - min(max(p, 1e-6), 1 - 1e-6)))
    best = None
    for w in [i / 20 for i in range(21)]:
        L = sum(ll(1 - N.cdf((-sp - (-sp + w * (mu + sp))) / s), y) for y, pm, sp, mu in data) / n
        if best is None or L < best[1]:
            best = (w, L)
    raw = sum(ll(pm, y) for y, pm, sp, mu in data) / n
    gains = [math.log(2) - ll(pm, y) for y, pm, sp, mu in data]
    rng = random.Random(7)
    boots = sorted(sum(gains[rng.randrange(n)] for _ in range(n)) / n for _ in range(1000))
    # simple bet rule at the (assumed) -110 standard, for scale only -- NOT a graded record
    bets = [(y, pm) for y, pm, sp, mu in data if abs(pm - 0.5) >= 0.04]
    wins = sum(1 for y, pm in bets if (y == 1.0) == (pm > 0.5))
    print(f"== {sport.upper()} covers, n={n} (pushes dropped), sigma {s}")
    print(f"   log loss: coin flip 0.6931 | model {raw:.4f} | best blend w={best[0]} {best[1]:.4f}")
    print(f"   model gain vs coin flip {sum(gains)/n:+.4f}, 90% CI [{boots[50]:+.4f}, {boots[949]:+.4f}]")
    print(f"   cover rate when the model leans >= 4 pts off 50%: {wins}-{len(bets)-wins} ({(wins/len(bets)*100 if bets else 0):.1f}%; 52.4% breaks even at -110)")
    print("   verdict:", "TEST A SPREAD DESK" if boots[50] > 0 else "NO EDGE on covers (do not build a spread desk on this model)")
