"""Seed data/nhl_goalie_games.json -- every NHL regular-season + playoff
boxscore (goalies: starter flag, shots, saves, TOI) from 2024-25 through
yesterday, from api-web.nhle.com. Re-run to extend; already-stored games are
skipped. The game-lines desk grows the file daily (python/nhl_goalies.grow).

Usage: python tools/build_nhl_goalie_seed.py [YYYY-MM-DD start]
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import nhl_goalies as ng  # noqa: E402


def main():
    start = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2024, 10, 4)
    end = dt.date.today() - dt.timedelta(days=1)
    doc = ng.load()
    games = doc.setdefault("games", {})
    before = len(games)
    n = ng.fetch_range(start, end, games)
    ng.save(doc)
    print(f"{n} new boxscores ({before} -> {len(games)}) {start} -> {end} -> {ng.PATH}")


if __name__ == "__main__":
    main()
