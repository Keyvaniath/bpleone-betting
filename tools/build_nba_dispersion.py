"""Build data/nba_dispersion.json -- the REAL game-to-game spread of NBA player
stats, fitted on last season's box scores (ESPN summaries for every 2025-26
regular-season final in data/game_finals_nba.json).

WHY (2026-11-03): the NBA prop modules assumed sigma = 22-30% of the projection
(rebounds: max(1.8, 0.22 x proj)). Measured on 26.7k player-games, an 8-rpg
player's game-to-game SD is 3.3, not 1.8; 20 ppg -> 7.5 not 5.0. Too-narrow
sigmas = overconfident props (REB_OVER hit 40% at 64% predicted).

Fit per stat: SD = a * mean^b (log-log across players with >= 20 games of
>= 10 min and >= 15 min average). This is WITHIN-player variation with the
mean known -- projection error comes on top -- so it is a floor, not a ceiling.

Usage: python tools/build_nba_dispersion.py
"""
import datetime as dt
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import espn_box_logs as eb  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATS = ("pts", "reb", "ast", "fg3m", "to", "stl", "blk", "fta", "pra", "pr", "pa", "ra")


def _val(r, s):
    combo = {"pra": ("pts", "reb", "ast"), "pr": ("pts", "reb"), "pa": ("pts", "ast"), "ra": ("reb", "ast")}
    if s in combo:
        return sum((r.get(k) or 0) for k in combo[s])
    return r.get(s)


def main():
    with open(os.path.join(REPO, "data", "game_finals_nba.json"), encoding="utf-8") as f:
        fin = [g for g in json.load(f)["games"] if "2025-10-21" <= g["date"] < "2026-04-20" and g.get("season_type") == 2]

    def one(g):
        s = eb._http(f"{eb.BASE_URL}/basketball/nba/summary?event={g['id']}")
        return eb._parse_basketball(s or {}, g["date"], eb.BASKETBALL_STATS) if s else []

    rows = []
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(one, fin):
            rows.extend(r)
    by = defaultdict(list)
    for r in rows:
        if (r.get("min") or 0) >= 10:
            by[r["name"]].append(r)
    fit = {}
    for s in STATS:
        xs, ys = [], []
        for g in by.values():
            if len(g) < 20 or statistics.mean([x.get("min") or 0 for x in g]) < 15:
                continue
            v = [_val(x, s) for x in g if _val(x, s) is not None]
            if len(v) < 20:
                continue
            m, sd = statistics.mean(v), statistics.pstdev(v)
            if m > 0.3 and sd > 0:
                xs.append(math.log(m))
                ys.append(math.log(sd))
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        fit[s] = {"a": round(math.exp(my - b * mx), 4), "b": round(b, 4), "n_players": n}
        print(s, fit[s])
    with open(os.path.join(REPO, "data", "nba_dispersion.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "source": f"ESPN NBA summaries, 2025-26 regular season ({len(fin)} games, {len(rows)} player-games)",
                   "model": "SD = a * mean^b, within-player game-to-game", "fit": fit}, f, indent=1)


if __name__ == "__main__":
    main()
