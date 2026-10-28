"""Build data/dk_lines_{nfl,nhl}.json -- the DraftKings pre-game line for every
NFL / NHL game in the git history of data/espn_odds.json, keyed by ESPN event id.

For each event: `open` = the first pre-game snapshot, `close` = the last one
before first pitch/puck drop (both {ml_home, ml_away, total, over_price,
under_price, spread, at}). The game-lines desk backtests against `close` and
keeps the file growing from the live espn_odds.json every run (no git needed
in CI); this tool seeds it from history once.

Usage: python tools/build_dk_line_history.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPORTS = ("NFL", "NHL")
KEYS = ("ml_home", "ml_away", "total", "over_price", "under_price", "spread")


def main():
    log = subprocess.run(["git", "-C", REPO, "log", "--reverse", "--format=%H", "--", "data/espn_odds.json"],
                         capture_output=True, text=True).stdout.split()
    out = {s: {} for s in SPORTS}
    for i, h in enumerate(log):
        try:
            o = json.loads(subprocess.run(["git", "-C", REPO, "show", f"{h}:data/espn_odds.json"],
                                          capture_output=True).stdout.decode("utf-8"))
        except Exception:
            continue
        ga = str(o.get("generated_at"))[:19]
        for g in o.get("games") or []:
            sp, eid, m = g.get("sport"), g.get("event_id"), g.get("market") or {}
            if sp not in out or not eid or g.get("status") != "pre" or m.get("ml_home") is None:
                continue
            snap = {k: m.get(k) for k in KEYS}
            snap["at"] = ga
            row = out[sp].setdefault(str(eid), {"matchup": g.get("matchup"), "home": g.get("home"),
                                                 "away": g.get("away"), "commence": g.get("commence_time"),
                                                 "open": snap})
            row["close"] = snap
            row["commence"] = g.get("commence_time") or row.get("commence")
    for sp, rows in out.items():
        p = os.path.join(REPO, "data", f"dk_lines_{sp.lower()}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "sport": sp,
                       "source": "DraftKings via ESPN odds (data/espn_odds.json git history + daily live)",
                       "n_events": len(rows), "events": rows}, f, indent=0)
        print(sp, len(rows), "events ->", p)


if __name__ == "__main__":
    main()
