"""Seed data/nfl_qb_games.json -- passing lines for every NFL final in
data/game_finals_nfl.json (ESPN game summaries), plus the last 10 days from
the dated scoreboard. Re-run to extend; stored games are skipped.

Usage: python tools/build_nfl_qb_seed.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import nfl_qbs as nq  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    with open(os.path.join(REPO, "data", "game_finals_nfl.json"), encoding="utf-8") as f:
        finals = [g for g in json.load(f).get("games") or [] if g.get("id")]
    doc = nq.load()
    games = doc.setdefault("games", {})
    before = len(games)
    n = nq.fetch(finals, games) + nq.fetch(nq._recent_finals(10), games)
    nq.save(doc)
    print(f"{n} new games ({before} -> {len(games)}) -> {nq.PATH}")


if __name__ == "__main__":
    main()
