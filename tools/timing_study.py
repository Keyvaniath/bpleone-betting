"""Do favourites shorten or drift between the first DraftKings price we record and the close? (2026-11-13)

Run from the repo root: python tools/timing_study.py   (read-only)

If favourites systematically shorten into the close, a lean (always a favourite) logged earlier
would collect closing line value; if they drift, later is better. Per sport, over every game in
data/dk_lines_<sport>.json whose open and close are different snapshots (open_late excluded):
change in the favourite's no-vig probability, open -> close, in points; bootstrap 90% CI.
First read 11/13/26: NFL -0.37 [-0.84,+0.08] n=163; NBA -0.32 [-0.80,+0.13] n=234;
NHL +0.07 [-0.07,+0.22] n=293. No timing effect: leans stay logged on game day."""
import json, os, random, statistics as st

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def nv(h, a):
    try:
        h, a = float(h), float(a)
        ph = (100 / (h + 100)) if h > 0 else (-h / (-h + 100))
        pa = (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
        return ph / (ph + pa)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    random.seed(7)
    for sp in ("nfl", "nba", "nhl"):
        ev = json.load(open(os.path.join(DATA, f"dk_lines_{sp}.json"), encoding="utf-8")).get("events") or {}
        ch = []
        for e in ev.values():
            o, c = e.get("open") or {}, e.get("close") or {}
            if e.get("open_late") or not o or not c or o.get("at") == c.get("at"):
                continue
            po, pc = nv(o.get("ml_home"), o.get("ml_away")), nv(c.get("ml_home"), c.get("ml_away"))
            if po is None or pc is None:
                continue
            ch.append((pc - po) * (1 if po >= 0.5 else -1) * 100)
        if not ch:
            print(sp.upper(), "no data")
            continue
        bs = sorted(st.mean(random.choices(ch, k=len(ch))) for _ in range(2000))
        print(f"{sp.upper()}: n={len(ch)} favourite open->close {st.mean(ch):+.2f} pts "
              f"(90% CI [{bs[100]:+.2f}, {bs[1899]:+.2f}]), shortened {sum(1 for x in ch if x > 0)}/{len(ch)}")


if __name__ == "__main__":
    main()
