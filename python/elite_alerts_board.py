"""
EdgeStat -- Cross-sport elite alerts unified board.

Pulls all 5+ aligned-signal alerts from the sport-specific synthesizers
into a single board for the homepage / dashboard. Distinct from
cross_sport_alpha_scanner (which crawls per-pick edges) -- this surfaces
ENTITY-LEVEL alignment (pitcher / lineup / goalie / skater / player).

Sources:
  - mlb_dominant_outing_alerts.json     (pitcher dominance)
  - mlb_pitcher_fade_alerts.json        (pitcher fade)
  - mlb_offensive_explosion_alerts.json (lineup explosion)
  - mlb_matchup_confluence_alerts.json  (fade + explosion pair)
  - nba_player_ceiling_stack.json       (NBA player multi-OVER)
  - nhl_goalie_dominance_alerts.json    (NHL goalie dominance)
  - nhl_skater_ceiling_stack.json       (NHL skater multi-OVER)

Output: data/elite_alerts_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "elite_alerts_board.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    sources = {
        "MLB_PITCHER_DOMINANCE": (
            _load(os.path.join(DATA_DIR, "mlb_dominant_outing_alerts.json")),
            "alerts", "pitcher", "n_positive_signals", "matchup",
        ),
        "MLB_PITCHER_FADE": (
            _load(os.path.join(DATA_DIR, "mlb_pitcher_fade_alerts.json")),
            "alerts", "pitcher", "n_negative_signals", "matchup",
        ),
        "MLB_OFFENSIVE_EXPLOSION": (
            _load(os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json")),
            "alerts", "team", "n_positive_signals", "matchup",
        ),
        "MLB_MATCHUP_CONFLUENCE": (
            _load(os.path.join(DATA_DIR, "mlb_matchup_confluence_alerts.json")),
            "confluences", "matchup", "combined_signal_count", "matchup",
        ),
        "NBA_PLAYER_CEILING": (
            _load(os.path.join(DATA_DIR, "nba_player_ceiling_stack.json")),
            "alerts", "player", "n_aligned_overs", "matchup",
        ),
        "NHL_GOALIE_DOMINANCE": (
            _load(os.path.join(DATA_DIR, "nhl_goalie_dominance_alerts.json")),
            "alerts", "goalie", "n_positive_signals", "matchup",
        ),
        "NHL_SKATER_CEILING": (
            _load(os.path.join(DATA_DIR, "nhl_skater_ceiling_stack.json")),
            "alerts", "player", "n_aligned_overs", "matchup",
        ),
    }

    board: List[Dict[str, Any]] = []
    sport_totals: Dict[str, int] = {}

    for source_key, (data, list_key, entity_field, signal_field, matchup_field) in sources.items():
        items = data.get(list_key) or []
        for a in items:
            if not isinstance(a, dict): continue
            n_signals = a.get(signal_field, 0)
            if n_signals < 5: continue  # only 5+ signal alerts on the elite board
            board.append({
                "source": source_key,
                "sport": source_key.split("_")[0],
                "entity": a.get(entity_field) or a.get("team"),
                "matchup": a.get(matchup_field) or "",
                "tier": a.get("tier"),
                "n_signals": n_signals,
                "signal_details": a.get("signals") or {},
                "extras": {
                    k: v for k, v in a.items()
                    if k in (
                        "expected_K", "expected_outs", "p_qs", "p_blowup",
                        "p_5plus_runs", "p_30plus_saves", "p_shutout",
                        "lineup_tier", "park_tier", "tt_direction",
                        "recommended_markets",
                    )
                },
            })
            sport_totals[source_key.split("_")[0]] = sport_totals.get(
                source_key.split("_")[0], 0
            ) + 1

    board.sort(key=lambda b: (-b["n_signals"], b["sport"], b["entity"] or ""))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_elites": len(board),
        "by_sport": sport_totals,
        "by_source": {
            src: sum(1 for b in board if b["source"] == src)
            for src in sources.keys()
        },
        "method_note": "Aggregates all 5+ signal alerts from sport-specific "
                       "synthesizers (dominance/fade/explosion/confluence/ceiling). "
                       "Surfaces entity-level alignment for homepage 'Tonight's Elites'.",
        "elites": board,
        "top_10": board[:10],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[elite-board] {o['n_elites']} entities across "
          f"{len(o['by_sport'])} sports -> {OUT}")
