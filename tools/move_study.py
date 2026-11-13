"""Does the desk model predict LINE MOVES? (2026-11-13)

Run from the repo root: python tools/move_study.py   (read-only; restore data/ with git checkout afterwards)

A model can lose to the closing price and still have value if it reliably points at the side
the market will move toward: bet that side at the OPENING number and you collect closing line
value. Test, walk-forward on this season's DraftKings-priced games:
  open  = the first DraftKings snapshot the desk recorded for the game (dk_lines_<sport>.json);
  close = the last pre-start snapshot;
  gap   = model home probability - no-vig open home probability;
  move  = no-vig close home probability - no-vig open home probability.
Rule: when |gap| >= T, take the model's side at the OPEN price; score CLV vs the close and
EV at the no-vig close. Pre-registered: a "bet the open" strategy is only worth building if
the mean CLV is positive with a 90% bootstrap CI clear of zero at the chosen T (T chosen
before looking: 0.04), on games whose open and close are different snapshots.
Caveat: the model's pre-game probability uses everything known before the game DATE, which
is a little more than was known at the open for lines posted days ahead (NFL)."""
import os, sys, math, random
_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python")
sys.path.insert(0, _PY)
os.chdir(_PY)
import datetime as dt
import game_lines_desk as gld

cap = {}
_o = gld.lean_backtest
gld.lean_backtest = lambda rows: (cap.__setitem__("rows", rows), _o(rows))[1]
gld.grow_lines = lambda sport: gld._load(os.path.join(gld.DATA_DIR, f"dk_lines_{sport}.json")).get("events") or {}
T = 0.04


def dec(a):
    return 1 + a / 100 if a >= 0 else 1 + 100 / abs(a)


for sport in ("nfl", "nba", "nhl"):
    gld.run_sport(sport)
    rows = cap["rows"]
    lines = gld._load(os.path.join(gld.DATA_DIR, f"dk_lines_{sport}.json")).get("events") or {}
    by = {}
    for eid, ev in lines.items():
        o, c = ev.get("open") or {}, ev.get("close") or {}
        if not o or not c or o.get("at") == c.get("at"):
            continue
        try:
            d = (dt.datetime.fromisoformat(str(ev["commence"]).replace("Z", "+00:00")) - dt.timedelta(hours=4)).date().isoformat()
        except Exception:
            continue
        by[(d, f"{gld._norm_team(sport, ev.get('away'))} @ {gld._norm_team(sport, ev.get('home'))}")] = (o, c)
    gaps, moves, bets = [], [], []
    for r in rows:
        oc = by.get((r["date"], r["matchup"]))
        if not oc:
            continue
        o, c = oc
        po, pc = gld._no_vig(o.get("ml_home"), o.get("ml_away")), gld._no_vig(c.get("ml_home"), c.get("ml_away"))
        if po is None or pc is None:
            continue
        gap, move = r["p_elo"] - po, pc - po
        gaps.append(gap); moves.append(move)
        if abs(gap) >= T:
            side_home = gap > 0
            px_o = o.get("ml_home") if side_home else o.get("ml_away")
            px_c = c.get("ml_home") if side_home else c.get("ml_away")
            if px_o is None or px_c is None:
                continue
            pts = (1 / dec(px_c) - 1 / dec(px_o)) * 100
            pf = pc if side_home else 1 - pc
            bets.append((pts, pf * dec(px_o) - 1))
    n = len(gaps)
    if n < 10:
        print(f"== {sport.upper()}: only {n} games with distinct open and close snapshots -- not enough")
        continue
    mg, mm = sum(gaps) / n, sum(moves) / n
    cov = sum((g - mg) * (m - mm) for g, m in zip(gaps, moves))
    vg = sum((g - mg) ** 2 for g in gaps); vm = sum((m - mm) ** 2 for m in moves)
    corr = cov / math.sqrt(vg * vm) if vg and vm else float("nan")
    same = sum(1 for g, m in zip(gaps, moves) if abs(m) > 0.005 and (g > 0) == (m > 0))
    moved = sum(1 for m in moves if abs(m) > 0.005)
    print(f"== {sport.upper()}: {n} games with a distinct open and close; lines moved > 0.5 pts in {moved}")
    print(f"   corr(model gap at the open, open->close move) = {corr:+.3f}; the line moved toward the model's side in {same}/{moved} ({same / moved * 100 if moved else 0:.0f}%)")
    if bets:
        k = len(bets)
        mp = sum(b[0] for b in bets) / k
        rng = random.Random(7)
        boots = sorted(sum(rng.choice(bets)[0] for _ in range(k)) / k for _ in range(4000))
        print(f"   bet the model's side at the OPEN when |gap| >= {T:.2f}: {k} bets, CLV {mp:+.2f} pts (90% CI [{boots[200]:+.2f}, {boots[3799]:+.2f}]), "
              f"beat the close {sum(1 for b in bets if b[0] > 0)}/{k}, EV at the no-vig close {sum(b[1] for b in bets) / k * 100:+.2f}%")
        print("   verdict:", "PROMISING: build a bet-the-open forward test" if boots[200] > 0 else "no reliable CLV from betting the open on this model")
