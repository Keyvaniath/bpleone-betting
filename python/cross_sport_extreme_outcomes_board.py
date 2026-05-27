"""
EdgeStat -- Cross-sport extreme outcomes board.

Unified long-shot/extreme outcome watchlist across all sports:
  - MLB: no-hitter, shutout, cycle
  - NBA: triple-double, 50-burger
  - NHL: shutout
  - Soccer: hat trick

Each entry has estimated probability + recommended long-shot bet.
Provides high-payout entertainment plays + occasional value finds.

Output: data/cross_sport_extreme_outcomes_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_extreme_outcomes_board.json")


WATCHLIST_SOURCES = [
    ("MLB_NO_HITTER", "mlb_no_hitter_watchlist.json", "pitcher",
     "est_p_no_hitter", "Hit-for-cycle / shutout / no-hitter"),
    ("MLB_CYCLE", "mlb_cycle_watchlist.json", "batter",
     "est_p_cycle", "Hit for the cycle"),
    ("NHL_SHUTOUT", "nhl_shutout_watchlist.json", "goalie",
     "p_shutout", "Goalie shutout"),
    ("NBA_TRIPLE_DOUBLE", "nba_triple_double_watchlist.json", "player",
     "p_td", "Triple-double"),
    ("NBA_50_BURGER", "nba_50_burger_watchlist.json", "player",
     "est_p_50plus_pts", "50+ points"),
    ("SOCCER_HAT_TRICK", "soccer_hat_trick_watchlist.json", "player",
     "est_p_3plus_goals_hat_trick", "3+ goals hat trick"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    extreme_picks: List[Dict[str, Any]] = []

    for source_id, fname, subject_field, p_field, market in WATCHLIST_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for r in (data.get("watchlist") or []):
            if not isinstance(r, dict): continue
            p = r.get(p_field, 0) or 0
            sport = source_id.split("_")[0]
            extreme_picks.append({
                "source": source_id,
                "sport": sport,
                "market": market,
                "subject": r.get(subject_field) or "?",
                "team": r.get("team"),
                "matchup": r.get("matchup") or r.get("match") or r.get("fight"),
                "estimated_probability": round(p, 4),
                "advisory": r.get("advisory"),
                "recommended_markets": r.get("recommended_markets") or [],
            })

    # Sort by estimated probability descending
    extreme_picks.sort(key=lambda p: -p["estimated_probability"])

    by_sport: Dict[str, int] = {}
    by_market: Dict[str, int] = {}
    for p in extreme_picks:
        by_sport[p["sport"]] = by_sport.get(p["sport"], 0) + 1
        by_market[p["market"]] = by_market.get(p["market"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_extreme_picks": len(extreme_picks),
        "by_sport": by_sport,
        "by_market": by_market,
        "method_note": "Cross-sport extreme outcome watchlist. Aggregates "
                       "no-hitter, cycle, shutout, triple-double, 50-burger, "
                       "hat-trick candidates. Each has estimated probability + "
                       "recommended long-shot bet. High-payout entertainment "
                       "plays + occasional value finds.",
        "extreme_picks": extreme_picks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[extreme-outcomes] {o['n_extreme_picks']} picks "
          f"by_market={o['by_market']} -> {OUT}")
