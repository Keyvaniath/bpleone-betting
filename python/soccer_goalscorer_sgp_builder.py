"""
EdgeStat -- Soccer goalscorer SGP builder.

For each player with high goalscorer probability, builds the same-player
SGP:
  - Anytime Goal YES (if p_score >= 0.40)
  - 2+ Goals YES (if p_score_2 >= 0.18)
  - 1+ Shot On Target YES (if available)
  - 3+ Shots YES (if signaled)
  - Booked / Yellow Card YES (if from cards prop)

Apply 1.12x correlation boost (goal-scorers also tend to take more shots
and may be more likely to commit fouls / get booked).

Output: data/soccer_goalscorer_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_goalscorer_sgp_builder.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    goalscorer = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))
    goalscorer_2 = _load(os.path.join(DATA_DIR, "soccer_goalscorer_2plus.json"))
    player_shots = _load(os.path.join(DATA_DIR, "soccer_player_shots_props.json"))

    # Build top goalscorer per player
    goal_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (goalscorer.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in goal_idx:
                    goal_idx[key] = r

    goal2_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (goalscorer_2.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in goal2_idx:
                    goal2_idx[key] = _safe(r.get("p_2plus_goals") or r.get("p"))

    shots_idx = {_norm(r.get("player")): r
                 for r in (player_shots.get("rows") or []) if isinstance(r, dict)}

    parlays: List[Dict[str, Any]] = []
    for name, g_data in goal_idx.items():
        p_score = _safe(g_data.get("p_score") or g_data.get("p"))
        if p_score < 0.40: continue

        legs: List[Dict[str, Any]] = [
            {"market": "Anytime Goal YES", "p": round(p_score, 3)},
        ]

        p_score_2 = goal2_idx.get(name, 0)
        if p_score_2 >= 0.18:
            legs.append({"market": "2+ Goals YES", "p": round(p_score_2, 3)})

        shots_data = shots_idx.get(name, {})
        shots_ec = (shots_data.get("edge_class") or "").upper()
        if "OVER" in shots_ec:
            legs.append({"market": "Shots OVER", "p": 0.54})

        if len(legs) < 2: continue

        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        parlay_p_corr = min(parlay_p_naive * 1.12, 0.99)

        parlays.append({
            "player": g_data.get("player"),
            "match": g_data.get("match") or g_data.get("matchup"),
            "team": g_data.get("team"),
            "p_score": round(p_score, 3),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
            "advisory": "Goalscorer SGP. Goal scorers also generate shots. "
                        "1.12x correlation boost.",
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "Soccer goalscorer same-player SGP. Anytime goal p >= 40%. "
                       "Optional: 2+ goals (p >= 18%), shots OVER. 1.12x "
                       "correlation boost.",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-goalscorer-sgp] {o['n_parlays']} SGP builds -> {OUT}")
