"""
EdgeStat -- weather-conditional projection adjustments.

For each game tonight, takes the weather from today.json + park metadata
and computes a per-game HR-rate multiplier (+/-%) plus a directional
implied OVER/UNDER lean.

Rules (free-knowledge baselines from baseball research literature):
  Wind speed:
    <5 mph        - neutral
    5-9 mph       - small effect
    10-19 mph     - large effect (multiplier scaled)
    20+ mph       - very large
  Wind direction vs park orientation:
    Out-to-CF     - HR multiplier UP, OVER lean
    In-from-CF    - HR multiplier DOWN, UNDER lean
    Out-to-LF/RF  - HR multiplier UP especially for opposite-side pull hitters
    In-from-LF/RF - HR multiplier DOWN especially for that-side pull hitters
    Crossing      - neutral
  Temperature:
    >85F          - HR multiplier UP +3-5%
    <55F          - HR multiplier DOWN -3-5%
  Indoor games:
    Always neutral

Note: this is a research-grade refinement, not a replacement for pipeline
park_factor. It sits ON TOP of park_factor as a daily delta.

Output: data/weather_conditional.json
  {
    "generated_at": "...",
    "n_games": 15,
    "by_game": [
      {
        "matchup": "...", "park": "...", "is_indoor": false,
        "temp_f": 78, "wind_mph": 12, "wind_dir_deg": 90, "wind_label": "out to CF",
        "hr_mult_delta_pct": +14.0,
        "lean": "OVER" | "UNDER" | "neutral",
        "reason": "..."
      }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
OUT_PATH = os.path.join(DATA_DIR, "weather_conditional.json")


# Stadium home-plate-to-CF compass orientation (degrees from north). Wind
# direction "out to CF" is wind blowing AWAY from home plate towards CF.
PARK_ORIENTATIONS = {
    # Approximate orientations (HP -> CF direction in degrees, 0 = N)
    "Fenway Park": 45, "Wrigley Field": 45, "Yankee Stadium": 75,
    "Citi Field": 25, "Citizens Bank Park": 35, "Nationals Park": 20,
    "Truist Park": 25, "Marlins Park": 35, "loanDepot park": 35,
    "PNC Park": 120, "Great American Ball Park": 120, "Wrigley": 45,
    "Coors Field": 0, "Dodger Stadium": 25, "Petco Park": 0,
    "Oracle Park": 110, "T-Mobile Park": 110, "Angel Stadium": 30,
    "Kauffman Stadium": 45, "Globe Life Field": 0, "Minute Maid Park": 350,
    "Daikin Park": 350, "American Family Field": 130, "Target Field": 90,
    "Progressive Field": 0, "Comerica Park": 130, "Guaranteed Rate Field": 130,
    "Rate Field": 130, "Oakland Coliseum": 60, "Sutter Health Park": 30,
    "Tropicana Field": 65, "Rogers Centre": 0, "Camden Yards": 30,
    "Oriole Park at Camden Yards": 30, "Busch Stadium": 200,
    "Chase Field": 25,
}


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _wind_label(wind_dir_deg: Optional[int], park: Optional[str]) -> str:
    """Translate wind compass to baseball-aware label given park orientation."""
    if wind_dir_deg is None:
        return ""
    park_o = PARK_ORIENTATIONS.get(park or "", None)
    if park_o is None:
        # Just give the compass direction
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[round((wind_dir_deg % 360) / 45) % 8]
    # Wind direction relative to CF axis. wind_dir_deg = direction wind is
    # blowing TOWARD. For "out to CF" wind must be blowing in the same
    # direction as the HP->CF axis.
    rel = ((wind_dir_deg - park_o) + 360) % 360
    if rel < 30 or rel > 330:
        return "out to CF"
    if 150 <= rel <= 210:
        return "in from CF"
    if 30 <= rel <= 60:
        return "out to LF"
    if 300 <= rel <= 330:
        return "out to RF"
    if 60 < rel < 150:
        return "L-to-R cross"
    if 210 < rel < 300:
        return "R-to-L cross"
    return ""


def _hr_mult_and_lean(weather: Dict[str, Any], park: Optional[str]) -> Dict[str, Any]:
    is_indoor = weather.get("is_indoor")
    if is_indoor:
        return {"hr_mult_delta_pct": 0.0, "lean": "neutral",
                "reason": "Indoor / roof closed -- weather neutralized"}
    wind_mph = weather.get("wind_mph") or 0
    wind_dir = weather.get("wind_dir_deg")
    temp = weather.get("temp_f") or 70
    label = _wind_label(wind_dir, park)

    mult_pct = 0.0
    reasons = []

    # Wind contribution
    if wind_mph >= 10:
        magnitude = min(wind_mph / 10.0, 2.5)   # cap at ~2.5x scale
        base_effect = magnitude * 5.0           # 10 mph -> 5%, 20 mph -> 10%
        if "out to CF" in label or "out to LF" in label or "out to RF" in label:
            mult_pct += base_effect
            reasons.append(f"Wind {wind_mph}mph {label} -- HR rate UP ~{base_effect:.0f}%")
        elif "in from CF" in label:
            mult_pct -= base_effect
            reasons.append(f"Wind {wind_mph}mph {label} -- HR rate DOWN ~{base_effect:.0f}%")
        elif "cross" in label:
            reasons.append(f"Wind {wind_mph}mph {label} -- mostly neutral on HR")
    elif wind_mph >= 5:
        # Small effect
        if "out to" in label:
            mult_pct += 2.0
            reasons.append(f"Mild wind {wind_mph}mph {label} -- slight OVER lean")
        elif "in from" in label:
            mult_pct -= 2.0
            reasons.append(f"Mild wind {wind_mph}mph {label} -- slight UNDER lean")

    # Temperature contribution
    if temp >= 90:
        mult_pct += 4
        reasons.append(f"Hot {temp}°F -- ball carries +4%")
    elif temp >= 80:
        mult_pct += 2
        reasons.append(f"Warm {temp}°F -- modest carry")
    elif temp <= 50:
        mult_pct -= 4
        reasons.append(f"Cold {temp}°F -- ball doesn't carry -4%")
    elif temp <= 60:
        mult_pct -= 2
        reasons.append(f"Cool {temp}°F -- slight UNDER lean")

    # Final lean
    if mult_pct >= 6:    lean = "OVER"
    elif mult_pct <= -6: lean = "UNDER"
    else:                lean = "neutral"

    return {
        "hr_mult_delta_pct": round(mult_pct, 1),
        "lean": lean,
        "reason": "; ".join(reasons) if reasons else "weather largely neutral",
        "wind_label": label,
    }


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    out: List[Dict[str, Any]] = []
    for g in today.get("games") or []:
        w = g.get("weather") or {}
        park = g.get("park")
        info = _hr_mult_and_lean(w, park)
        out.append({
            "matchup": g.get("matchup"),
            "park": park,
            "is_indoor": w.get("is_indoor"),
            "temp_f": w.get("temp_f"),
            "wind_mph": w.get("wind_mph"),
            "wind_dir_deg": w.get("wind_dir_deg"),
            "carry_index": w.get("carry_index"),
            **info,
        })
    out.sort(key=lambda x: -abs(x.get("hr_mult_delta_pct", 0)))
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(out),
        "by_game": out,
        "over_lean_games": [g["matchup"] for g in out if g.get("lean") == "OVER"],
        "under_lean_games": [g["matchup"] for g in out if g.get("lean") == "UNDER"],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games']} games scored")
    print(f"  OVER lean: {p['over_lean_games']}")
    print(f"  UNDER lean: {p['under_lean_games']}")
