"""
EdgeStat -- top picks evolution tracker.

Each run, captures the current top_25 picks and appends to a rolling log
so we can see WHICH picks survived all cycles (stable signal = more
trustworthy) and which ones flickered in/out (noise).

A pick that appears in every cycle's top_25 for the day is a STABLE
pick -- the model consistently rates it highly across data refreshes.
A pick that appears once and disappears is noise.

Output: data/pick_evolution.json
   {
     "date": "2026-05-20",
     "n_cycles_today": 3,
     "stable_picks": [...],     # appeared in every cycle
     "flickering_picks": [...], # appeared in some cycles
     "history": [
        {cycle_at: "...", n_picks: 25, pick_ids: [...]},
        ...
     ]
   }
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "pick_evolution.json")

MAX_CYCLES_PER_DAY = 30   # truncate the per-day cycles log


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _pick_id(pick):
    sport = pick.get("sport") or "?"
    pm = pick.get("player_or_matchup") or "?"
    market = pick.get("market") or "?"
    # Collapse market line variants
    market_family = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", market)
    return f"{sport}|{pm}|{market_family}".lower()


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    state = _load(OUT)
    today_str = dt.date.today().isoformat()

    current_top25 = top_plays.get("top_25") or []
    current_cycle = {
        "cycle_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_picks": len(current_top25),
        "pick_ids": [_pick_id(p) for p in current_top25],
        "pick_details": [
            {
                "pick_id": _pick_id(p),
                "sport": p.get("sport"),
                "player_or_matchup": p.get("player_or_matchup"),
                "market": p.get("market"),
                "prob": p.get("prob"),
                "edge_pct": p.get("edge_pct"),
            } for p in current_top25
        ],
    }

    # Reset history if it's a new day
    if state.get("date") != today_str:
        history = [current_cycle]
    else:
        history = (state.get("history") or [])
        history.append(current_cycle)
        history = history[-MAX_CYCLES_PER_DAY:]

    # Identify stable picks (appeared in every cycle today)
    if len(history) >= 2:
        sets_per_cycle = [set(c["pick_ids"]) for c in history]
        # Intersection = stable
        stable_ids = set.intersection(*sets_per_cycle)
        # Union = all picks ever seen today
        all_ids = set.union(*sets_per_cycle)
        flickering_ids = all_ids - stable_ids
    else:
        stable_ids = set(history[0]["pick_ids"]) if history else set()
        flickering_ids = set()

    # Map back to pick details (use the most recent cycle's details)
    latest_details = {d["pick_id"]: d for d in current_cycle["pick_details"]}
    stable_picks = [latest_details[pid] for pid in stable_ids if pid in latest_details]
    # For flickering, also include older cycle details
    flick_details = {}
    for c in history:
        for d in c.get("pick_details", []):
            flick_details[d["pick_id"]] = d
    flickering_picks = [flick_details[pid] for pid in flickering_ids if pid in flick_details]

    stable_picks.sort(key=lambda x: -(x.get("edge_pct") or 0))
    flickering_picks.sort(key=lambda x: -(x.get("edge_pct") or 0))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "date": today_str,
        "n_cycles_today": len(history),
        "n_stable_picks": len(stable_picks),
        "n_flickering_picks": len(flickering_picks),
        "stable_picks": stable_picks,
        "flickering_picks": flickering_picks,
        "history": history,
        "note": ("Stable = pick appears in every cycle's top_25 today. "
                  "Flickering = pick appeared in some cycles but not others. "
                  "Stable picks have stronger signal -- the model agrees "
                  "across data refreshes."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Pick evolution: cycle {p['n_cycles_today']} today")
    print(f"  Stable picks (appeared all cycles): {p['n_stable_picks']}")
    print(f"  Flickering picks: {p['n_flickering_picks']}")
    if p['n_cycles_today'] >= 2:
        print(f"\n  Top 5 stable picks:")
        for x in p['stable_picks'][:5]:
            print(f"    [{x.get('sport'):7s}] {x.get('player_or_matchup','?')[:25]:25s} {x.get('market','?')[:25]:25s} edge {x.get('edge_pct',0):+.1f}%")
