"""Build data/nhl_skater_rates.json from scratch: every NHL boxscore since
2024-25 (game ids from data/nhl_goalie_games.json + the schedule through
yesterday), replayed in date order. The NB dispersion per stat is chosen on
LAST season's games (2025-26) by walk-forward log loss.

Usage: python tools/build_nhl_skater_rates.py
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import nhl_goalies as ng      # noqa: E402
import nhl_skaters as ns      # noqa: E402


def main():
    ids = {str(g["nhl_id"]): g["date"] for g in ng.ordered_games()}
    end = dt.date.today() - dt.timedelta(days=1)
    for gid, d in ng._schedule_ids(end - dt.timedelta(days=10), end):
        ids.setdefault(str(gid), d)
    games = ns.fetch_games(sorted(ids.items(), key=lambda x: (x[1], x[0])))
    print(f"{len(games)} boxscores")
    st = ns.SkaterState()
    cal = ns.replay(games, st, cal_from="2025-10-01", cal_to="2026-09-01")
    ns.save(st, cal)
    for stat, c in cal.items():
        print(stat, "r =", c["dispersion_r"], c["logloss_by_r"])
    print(f"{len(st.p)} skaters -> {ns.PATH}")


if __name__ == "__main__":
    main()
