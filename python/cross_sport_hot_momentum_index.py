"""
EdgeStat -- Cross-sport hot momentum index.

Unified hot/cold board across all sport heat modules:
  - mlb_batter_heat
  - nba_player_heat
  - wnba_player_heat
  - golf_player_heat

For each sport, surface top HOT and top COLD players. Combined into
single board for cross-sport momentum view.

Output: data/cross_sport_hot_momentum_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_hot_momentum_index.json")


HEAT_SOURCES = [
    ("MLB", "mlb_batter_heat.json", "batter"),
    ("NBA", "nba_player_heat.json", "player"),
    ("WNBA", "wnba_player_heat.json", "player"),
    ("GOLF", "golf_player_heat.json", "player"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _extract_entries(data: Dict[str, Any], sport: str, subject_field: str,
                     category: str) -> List[Dict[str, Any]]:
    """Extract entries from various possible keys (hot, cold, heating_up,
    cooling_down, etc.)."""
    entries: List[Dict[str, Any]] = []
    keys_for_hot = ("hot", "heating_up", "hot_players")
    keys_for_cold = ("cold", "cooling_down", "cold_players")

    if category == "HOT":
        target_keys = keys_for_hot
    else:
        target_keys = keys_for_cold

    for k in target_keys:
        for r in (data.get(k) or []):
            if isinstance(r, dict):
                entries.append({
                    "sport": sport,
                    "player": r.get(subject_field) or r.get("player") or "?",
                    "team": r.get("team"),
                    "trend": (r.get("trend") or k).upper(),
                    "score": r.get("score") or r.get("heat_score") or 0,
                    "category": category,
                })
            elif isinstance(r, str):
                entries.append({
                    "sport": sport,
                    "player": r,
                    "trend": k.upper(),
                    "category": category,
                })

    # Also pull "rows" entries with trend classification
    for r in (data.get("rows") or []):
        if not isinstance(r, dict): continue
        trend = (r.get("trend") or r.get("classification") or "").upper()
        is_hot = "HOT" in trend or "HEATING" in trend
        is_cold = "COLD" in trend or "COOLING" in trend
        if (category == "HOT" and is_hot) or (category == "COLD" and is_cold):
            entries.append({
                "sport": sport,
                "player": r.get(subject_field) or r.get("player") or "?",
                "team": r.get("team"),
                "trend": trend or category,
                "score": r.get("score") or r.get("heat_score") or 0,
                "category": category,
            })

    return entries


def run() -> Dict[str, Any]:
    hot: List[Dict[str, Any]] = []
    cold: List[Dict[str, Any]] = []

    for sport, fname, subject in HEAT_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        hot.extend(_extract_entries(data, sport, subject, "HOT"))
        cold.extend(_extract_entries(data, sport, subject, "COLD"))

    # Dedupe per sport
    def _dedupe(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for e in entries:
            key = (e["sport"], (e.get("player") or "").lower())
            if key in seen: continue
            seen.add(key)
            out.append(e)
        return out

    hot = _dedupe(hot)
    cold = _dedupe(cold)

    # By sport count
    hot_by_sport: Dict[str, int] = {}
    cold_by_sport: Dict[str, int] = {}
    for h in hot:
        hot_by_sport[h["sport"]] = hot_by_sport.get(h["sport"], 0) + 1
    for c in cold:
        cold_by_sport[c["sport"]] = cold_by_sport.get(c["sport"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_hot_total": len(hot),
        "n_cold_total": len(cold),
        "hot_by_sport": hot_by_sport,
        "cold_by_sport": cold_by_sport,
        "method_note": "Aggregates HOT/COLD entries from mlb_batter_heat + "
                       "nba_player_heat + wnba_player_heat + golf_player_heat. "
                       "Unified cross-sport momentum board for tonight's hot/cold "
                       "narrative bets.",
        "hot_players": hot[:30],
        "cold_players": cold[:30],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hot-momentum] {o['n_hot_total']} HOT, {o['n_cold_total']} COLD "
          f"hot_by_sport={o['hot_by_sport']} -> {OUT}")
