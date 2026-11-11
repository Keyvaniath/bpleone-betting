"""Seed data/nba_player_games.json -- every player's minutes and Game Score in
every NBA final since 2025-10-21 (ESPN summaries, one call per game).

Finals come from data/game_finals_nba.json; the rows the daily merge added
without an ESPN id are resolved from the dated scoreboard. Re-runnable: games
already in the store are skipped.

Usage: python tools/build_nba_avail_seed.py
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import nba_avail as na  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    with open(os.path.join(REPO, "data", "game_finals_nba.json"), encoding="utf-8") as f:
        fin = json.load(f)["games"]
    metas = [{"id": str(g["id"]), "date": g["date"]} for g in fin if g.get("id")]
    for d in sorted({g["date"] for g in fin if not g.get("id")}):
        metas.extend(na.scoreboard_finals(dt.date.fromisoformat(d)))
    doc = na.load()
    before = len(doc["games"])
    n = na.fetch(metas, doc)
    na.save(doc)
    gms = na.ordered_games(doc)
    print(f"finals {len(fin)} | metas {len(metas)} | store {before} -> {len(doc['games'])} (+{n}) | "
          f"{gms[0]['d']}..{gms[-1]['d']} | players {len(doc['names'])} | "
          f"replacement rate {na.measure_repl(gms)} GS/min")


if __name__ == "__main__":
    main()
