"""
EdgeStat -- unified real-stats lookup helper.

Wraps data/player_stats_<sport>.json (populated by espn_player_stats.py)
to give prop modules REAL per-game averages instead of hardcoded estimates.

Used by all new prop modules going forward. Pattern:

    from real_stats_lookup import get_player_stat
    ppg = get_player_stat("nba", "luka doncic", "pts_per_game",
                          fallback={"ppg": 28.5})

Returns dict with:
    {"value": float, "n_games": int, "source": "real" | "fallback"}

Caches the JSON load so multiple lookups in same process are fast.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional, Union


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_sport(sport: str) -> Dict[str, Dict[str, Any]]:
    """Return {player_name_lower: player_record}."""
    key = sport.lower()
    if key in _CACHE: return _CACHE[key]
    path = os.path.join(_DATA_DIR, f"player_stats_{key}.json")
    idx: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(path):
        try:
            with open(path) as f: d = json.load(f)
            for p in (d.get("players") or []):
                nm = (p.get("name") or "").lower().strip()
                if nm: idx[nm] = p
        except Exception:
            pass
    _CACHE[key] = idx
    return idx


def get_player_stat(
    sport: str,
    player_name: str,
    stat_key: str,
    fallback: Optional[Union[float, int]] = None,
    min_games: int = 5,
) -> Dict[str, Any]:
    """Look up REAL per-game stat for player.

    Returns:
        {"value": float, "n_games": int, "source": "real" | "fallback" | "missing"}

    sport: "nba" | "wnba" | "nhl"
    stat_key: e.g. "pts_per_game", "reb_per_game", "ast_per_game",
              "threes_per_game", "shots_per_game", "goals_per_game"
    fallback: numeric default if real data missing or player has < min_games
    min_games: ignore real data if player has fewer logged games than this
    """
    idx = _load_sport(sport)
    rec = idx.get((player_name or "").lower().strip())
    if rec:
        n_games = rec.get("n_games") or 0
        val = rec.get(stat_key)
        if val is not None and n_games >= min_games:
            return {"value": float(val), "n_games": n_games, "source": "real"}
    if fallback is not None:
        return {"value": float(fallback), "n_games": 0, "source": "fallback"}
    return {"value": 0.0, "n_games": 0, "source": "missing"}


def get_player_record(sport: str, player_name: str) -> Optional[Dict[str, Any]]:
    """Return full ESPN player record or None."""
    idx = _load_sport(sport)
    return idx.get((player_name or "").lower().strip())


def has_real_data(sport: str, player_name: str, min_games: int = 5) -> bool:
    rec = get_player_record(sport, player_name)
    return rec is not None and (rec.get("n_games") or 0) >= min_games


def coverage_report(sport: str) -> Dict[str, Any]:
    """Quick sanity check: how many players have N games of real data."""
    idx = _load_sport(sport)
    total = len(idx)
    with_5 = sum(1 for p in idx.values() if (p.get("n_games") or 0) >= 5)
    with_20 = sum(1 for p in idx.values() if (p.get("n_games") or 0) >= 20)
    return {
        "sport": sport,
        "total_players_indexed": total,
        "with_at_least_5_games": with_5,
        "with_at_least_20_games": with_20,
    }


if __name__ == "__main__":
    # Self-test: print coverage for each sport
    for sport in ("nba", "wnba", "nhl"):
        print(coverage_report(sport))
    # Spot-check a few stars
    for name, sport in [("luka doncic", "nba"), ("nikola jokic", "nba"),
                        ("aja wilson", "wnba"), ("connor mcdavid", "nhl")]:
        r = get_player_record(sport, name)
        if r:
            print(f"{name} ({sport}): {r.get('n_games')} games, {r.get('pts_per_game') or r.get('points_per_game')} ppg/pts")
        else:
            print(f"{name} ({sport}): NOT FOUND in ESPN data")
