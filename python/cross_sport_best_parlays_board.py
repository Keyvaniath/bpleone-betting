"""
EdgeStat -- Cross-sport best parlays board.

Aggregates all parlay builders into a single ranked board of tonight's
top recommended same-game / multi-leg parlays:
  - nba_player_sgp_builder
  - mlb_batter_sgp_builder
  - nhl_skater_sgp_builder
  - nhl_goalie_save_parlay_builder
  - mlb_closer_save_parlay_builder

Each parlay is ranked by parlay_p_correlated (or parlay_p), with sport
diversification preferred in the top 10.

Output: data/cross_sport_best_parlays_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_best_parlays_board.json")


PARLAY_SOURCES = [
    ("NBA_PLAYER_SGP", "nba_player_sgp_builder.json", "player",
     "parlay_p_correlated"),
    ("MLB_BATTER_SGP", "mlb_batter_sgp_builder.json", "batter",
     "parlay_p_correlated"),
    ("NHL_SKATER_SGP", "nhl_skater_sgp_builder.json", "skater",
     "parlay_p_correlated"),
    ("NHL_GOALIE_PARLAY", "nhl_goalie_save_parlay_builder.json", "goalie",
     "parlay_p"),
    ("MLB_CLOSER_PARLAY", "mlb_closer_save_parlay_builder.json", "closer",
     "parlay_p"),
    ("WNBA_PLAYER_SGP", "wnba_player_sgp_builder.json", "player",
     "parlay_p_correlated"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    all_parlays: List[Dict[str, Any]] = []

    for source_id, fname, subject_field, p_field in PARLAY_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for p in (data.get("parlays") or []):
            if not isinstance(p, dict): continue
            parlay_p = p.get(p_field) or p.get("parlay_p") or 0
            n_legs = p.get("n_legs") or len(p.get("legs") or [])
            if n_legs < 2: continue

            sport = source_id.split("_")[0]
            all_parlays.append({
                "source": source_id,
                "sport": sport,
                "subject": p.get(subject_field) or "?",
                "matchup": p.get("matchup") or p.get("fight") or p.get("match"),
                "n_legs": n_legs,
                "parlay_p": round(parlay_p, 4),
                "legs": p.get("legs"),
            })

    # Sort by parlay_p descending
    all_parlays.sort(key=lambda p: -p["parlay_p"])

    # Top 10 with sport diversification (max 3 per sport)
    seen_sport_counts: Dict[str, int] = {}
    top_10_diverse: List[Dict[str, Any]] = []
    for p in all_parlays:
        sport = p["sport"]
        if seen_sport_counts.get(sport, 0) >= 3: continue
        top_10_diverse.append(p)
        seen_sport_counts[sport] = seen_sport_counts.get(sport, 0) + 1
        if len(top_10_diverse) >= 10: break

    # By sport breakdown
    by_sport: Dict[str, int] = {}
    for p in all_parlays:
        by_sport[p["sport"]] = by_sport.get(p["sport"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total_parlays": len(all_parlays),
        "by_sport": by_sport,
        "method_note": "Aggregates all parlay/SGP builders into single ranked "
                       "board. Top 10 diversified (max 3 per sport). All parlays "
                       "ranked by parlay_p (correlated where applicable).",
        "top_10_diverse": top_10_diverse,
        "top_25_overall": all_parlays[:25],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[best-parlays] {o['n_total_parlays']} parlays "
          f"by_sport={o['by_sport']} -> {OUT}")
