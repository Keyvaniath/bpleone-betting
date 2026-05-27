"""
EdgeStat -- Cross-sport event board.

Unified aggregator across all 9 per-event preview modules:
  MLB game, NBA game, NHL game, soccer match, tennis match,
  UFC fight, golf tournament, F1 race, WNBA game.

Pulls LOCK + STRONG events from each + presents as single ranked board.

Output: data/cross_sport_event_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_event_board.json")


PREVIEW_SOURCES = [
    ("MLB",     "mlb_game_preview.json",       "matchup",    "GAME_LOCK", "GAME_STRONG"),
    ("NBA",     "nba_game_preview.json",       "matchup",    "GAME_LOCK", "GAME_STRONG"),
    ("NHL",     "nhl_game_preview.json",       "matchup",    "GAME_LOCK", "GAME_STRONG"),
    ("SOCCER",  "soccer_match_preview.json",   "match",      "MATCH_LOCK", "MATCH_STRONG"),
    ("TENNIS",  "tennis_match_preview.json",   "match",      "MATCH_LOCK", "MATCH_STRONG"),
    ("UFC",     "ufc_fight_card_preview.json", "fight",      "FIGHT_LOCK", "FIGHT_STRONG"),
    ("GOLF",    "golf_tournament_preview.json","tournament", "TOURNAMENT_LOCK", "TOURNAMENT_STRONG"),
    ("F1",      "f1_race_preview.json",        "race",       "RACE_LOCK", "RACE_STRONG"),
    ("WNBA",    "wnba_game_preview.json",      "matchup",    "GAME_LOCK", "GAME_STRONG"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    by_sport: Dict[str, int] = {}
    by_tier: Dict[str, int] = {}

    for sport, fname, event_field, lock_tier, strong_tier in PREVIEW_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for ev in (data.get("locks_and_strong") or data.get("previews") or []):
            if not isinstance(ev, dict): continue
            tier = ev.get("tier") or ""
            if tier not in (lock_tier, strong_tier): continue
            event_name = ev.get(event_field) or "?"
            events.append({
                "sport": sport,
                "event": event_name,
                "tier": tier,
                "is_lock": tier == lock_tier,
                "n_lock_signals": (ev.get("n_pitcher_locks", 0) +
                                   ev.get("n_team_locks", 0) +
                                   ev.get("n_goalie_locks", 0) +
                                   ev.get("n_skater_locks", 0) +
                                   ev.get("n_player_locks", 0) +
                                   ev.get("n_locks", 0)),
                "recommended_angles": ev.get("recommended_angles") or [],
            })
            by_sport[sport] = by_sport.get(sport, 0) + 1
            by_tier[tier] = by_tier.get(tier, 0) + 1

    # Sort: LOCKs first, then by lock signal density
    events.sort(key=lambda e: (not e["is_lock"], -e.get("n_lock_signals", 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_events": len(events),
        "n_locks": sum(1 for e in events if e["is_lock"]),
        "n_strong": sum(1 for e in events if not e["is_lock"]),
        "by_sport": by_sport,
        "by_tier": by_tier,
        "method_note": "Cross-sport event-level board. Pulls LOCK + STRONG-tier "
                       "events from all 9 per-event preview synthesizers. Sorted "
                       "with LOCKs first, then by lock signal density.",
        "events": events,
        "top_15": events[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[cross-sport-event] {o['n_events']} events "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG) "
          f"by_sport={o['by_sport']} -> {OUT}")
