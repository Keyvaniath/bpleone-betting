"""Do NBA favourites on the second night of a back-to-back drift between our first price and the close? (2026-11-16)

Run from the repo root: python tools/b2b_study.py   (read-only)

Motivation: 11/14 CLE -142 lean closed +276 (starters rested on a B2B); 11/16 Alpha HOU -148 on a B2B
moved to -130 within hours of the lock. If B2B favourites systematically lose value from our first
snapshot to the close, a lean logged early on game day carries rest-news risk, and logging NBA leans
after the injury report would be justified. Pre-registered read: compare the favourite's no-vig move
(first snapshot -> close, points, + = favourite shortened) for B2B favourites vs all other favourites,
with a bootstrap 90% CI on the difference. Only games whose open and close are different snapshots.
"""
import json, os, random, statistics as st, sys, datetime as dt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "python"))
os.chdir(os.path.join(ROOT, "python"))
import game_lines_desk as gld   # noqa: E402


def nv(h, a):
    try:
        h, a = float(h), float(a)
        ph = (100 / (h + 100)) if h > 0 else (-h / (-h + 100))
        pa = (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
        return ph / (ph + pa)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    random.seed(11)
    ev = json.load(open(os.path.join(ROOT, "data", "dk_lines_nba.json"), encoding="utf-8")).get("events") or {}
    finals = gld.load_finals("nba")
    played = {}
    for g in finals:
        d = str(g.get("date") or "")[:10]
        for t in (g.get("home"), g.get("away")):
            if t:
                played.setdefault(gld._norm_team("nba", t), set()).add(d)
    b2b, other = [], []
    for e in ev.values():
        o, c = e.get("open") or {}, e.get("close") or {}
        if e.get("open_late") or not o or not c or o.get("at") == c.get("at"):
            continue
        po, pc = nv(o.get("ml_home"), o.get("ml_away")), nv(c.get("ml_home"), c.get("ml_away"))
        if po is None or pc is None:
            continue
        fav_home = po >= 0.5
        move = (pc - po) * (1 if fav_home else -1) * 100
        mu = str(e.get("matchup") or "")
        if " @ " not in mu:
            continue
        away, home = [gld._norm_team("nba", x.strip()) for x in mu.split(" @ ")]
        fav = home if fav_home else away
        try:
            day = gld._et_day(dt.datetime.fromisoformat(str(e.get("commence")).replace("Z", "+00:00")))
        except Exception:
            continue
        prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
        (b2b if prev in played.get(fav, set()) else other).append(move)
    if not b2b or not other:
        print("not enough data", len(b2b), len(other))
        return
    diffs = sorted(st.mean(random.choices(b2b, k=len(b2b))) - st.mean(random.choices(other, k=len(other))) for _ in range(4000))
    print(f"B2B favourites:   n={len(b2b)} move first->close {st.mean(b2b):+.2f} pts, drifted out {sum(1 for x in b2b if x < 0)}/{len(b2b)}")
    print(f"other favourites: n={len(other)} move first->close {st.mean(other):+.2f} pts, drifted out {sum(1 for x in other if x < 0)}/{len(other)}")
    print(f"difference (B2B - other): {st.mean(b2b) - st.mean(other):+.2f} pts, 90% CI [{diffs[200]:+.2f}, {diffs[3799]:+.2f}]")


if __name__ == "__main__":
    main()
