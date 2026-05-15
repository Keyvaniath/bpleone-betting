"""
EdgeStat -- lineup quality aggregator.

For each game's confirmed lineup, sum each batter's xwOBA * expected PA
to produce a per-team 'lineup quality' score. This is a much sharper
signal than season team wRC+ for projecting tonight's runs because:

  - It uses the ACTUAL 9 batters in tonight's lineup (not the season-average roster).
  - It applies Statcast quality-of-contact metrics (xwOBA) instead of luck-influenced
    raw stats.
  - It weights by batting-order PA estimates (lead-off gets 4.65 PA, 9th gets 3.85).

Output: weighted xwOBA per team + a 'lineup_quality_index' normalized to
100 = league average (similar to wRC+ scaling).

Writes data/lineup_quality.json keyed by game.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "lineup_quality.json")

# PA by batting-order slot
PA_BY_ORDER = {1: 4.65, 2: 4.55, 3: 4.45, 4: 4.35, 5: 4.25,
               6: 4.15, 7: 4.05, 8: 3.95, 9: 3.85}
LEAGUE_XWOBA = 0.320   # ~MLB average


def score_lineup(lineup: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum each batter's xwOBA-weighted PA; return aggregate + index."""
    try:
        import statcast as sc
    except Exception:
        sc = None
    if not lineup:
        return {"n_batters": 0}
    total_pa = 0.0
    total_xwoba_pa = 0.0     # sum of xwOBA * PA
    season_proxy_pa = 0.0    # fallback if no statcast
    details = []
    for b in lineup:
        pa = PA_BY_ORDER.get(b.get("order"), 4.2)
        total_pa += pa
        pid = b.get("id")
        b_stats = sc.batter_stats(pid) if sc and pid else {}
        xwoba = b_stats.get("xwoba")
        if xwoba is not None and xwoba > 0:
            total_xwoba_pa += xwoba * pa
            details.append({"order": b.get("order"), "name": b.get("name"),
                            "xwoba": xwoba, "pa": pa, "source": "statcast"})
        else:
            # Fallback to league avg
            total_xwoba_pa += LEAGUE_XWOBA * pa
            season_proxy_pa += pa
            details.append({"order": b.get("order"), "name": b.get("name"),
                            "xwoba": None, "pa": pa, "source": "league_avg"})
    weighted_xwoba = total_xwoba_pa / total_pa if total_pa else 0
    # Index: 100 = league avg, +/-1 point ~= 1% above/below league wOBA
    quality_index = int(round(100 * weighted_xwoba / LEAGUE_XWOBA))
    return {
        "n_batters": len(lineup),
        "total_pa": round(total_pa, 1),
        "weighted_xwoba": round(weighted_xwoba, 4),
        "lineup_quality_index": quality_index,
        "statcast_coverage": round((1 - season_proxy_pa / total_pa) * 100, 1) if total_pa else 0,
        "by_batter": details,
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    out_games = []
    for g in m.get("games", []):
        L = g.get("lineups") or {}
        home_score = score_lineup(L.get("home") or [])
        away_score = score_lineup(L.get("away") or [])
        if home_score.get("n_batters") or away_score.get("n_batters"):
            out_games.append({
                "matchup": g.get("matchup"),
                "time": g.get("time"),
                "park": g.get("venue") or g.get("park"),
                "away": away_score,
                "home": home_score,
            })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "league_xwoba_baseline": LEAGUE_XWOBA,
        "games": out_games,
    }


def write_lineup_quality(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote lineup_quality -> {path}")
    print(f"  Games with lineups: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        a, h = g["away"], g["home"]
        print(f"  {g['matchup']:14} | away idx {a.get('lineup_quality_index','?')} "
              f"({a.get('statcast_coverage','?')}% Statcast) | "
              f"home idx {h.get('lineup_quality_index','?')} "
              f"({h.get('statcast_coverage','?')}% Statcast)")


if __name__ == "__main__":
    write_lineup_quality(build_all())
