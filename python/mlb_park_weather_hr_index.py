"""
EdgeStat -- MLB park + weather HR index.

For each game tonight, computes a 0-150 "HR environment index" combining:
  - Park HR factor (Coors 1.30, Yankee Stadium 1.18, Oracle 0.85)
  - Wind speed/direction (out to LF/RF = boost, in = suppress)
  - Temperature (warm air carries ball; +1F = +0.4% HR rate)
  - Humidity (humid air denser = slight suppress)
  - Roof status (closed = neutral; open = weather active)

Tier:
  130+    HOMER_FRIENDLY    — All HR/TB props lean OVER aggressively
  110-130 HITTER_FRIENDLY   — Mild OVER bias on HR/TB
  90-110  NEUTRAL           — Use book baseline
  70-90   PITCHER_FRIENDLY  — Mild UNDER bias on HR/TB
  <70     PITCHER_GRAVEYARD — Strong UNDER bias on HR, lean UNDER team totals

Output: data/mlb_park_weather_hr_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json")


# Park HR factors (2024 baselines, 1.0 = neutral)
PARK_HR_FACTOR = {
    "Coors Field":           1.30,
    "Great American Ball Park": 1.18,
    "Yankee Stadium":        1.18,
    "Wrigley Field":         1.10,
    "Citizens Bank Park":    1.12,
    "Globe Life Field":      1.08,
    "Truist Park":           1.05,
    "Minute Maid Park":      1.08,
    "Rate Field":            1.05,
    "Citi Field":            1.00,
    "PNC Park":              0.95,
    "Petco Park":            0.92,
    "Oracle Park":           0.85,
    "Comerica Park":         0.92,
    "T-Mobile Park":         0.92,
    "Kauffman Stadium":      0.93,
    "Tropicana Field":       0.95,
    "Oakland Coliseum":      0.95,
    "Angel Stadium":         0.98,
    "Dodger Stadium":        1.02,
    "Loan Depot Park":       0.92,
    "Target Field":          1.00,
    "Nationals Park":        1.00,
    "Camden Yards":          1.02,
    "Progressive Field":     0.98,
    "Fenway Park":           1.05,
    "Rogers Centre":         1.02,
    "Busch Stadium":         0.98,
    "American Family Field": 1.05,
    "Chase Field":           1.05,
}


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


def _wind_factor(wind_speed: float, wind_dir: str) -> float:
    """Compute wind contribution: 1.0 = neutral, >1 = HR boost."""
    if not wind_dir: return 1.0
    wd = wind_dir.lower()
    # Out to CF/LF/RF
    if any(k in wd for k in ("out to", "out-to", "to lf", "to cf", "to rf", "from home")):
        return 1.0 + wind_speed * 0.012  # ~12% boost at 10mph
    # In from CF/LF/RF
    if any(k in wd for k in ("in from", "to home", "from lf", "from cf", "from rf")):
        return max(0.70, 1.0 - wind_speed * 0.014)
    # Cross (LR or RL): mild suppress
    if "left to right" in wd or "right to left" in wd or "across" in wd:
        return 1.0 - wind_speed * 0.003
    return 1.0


def _temp_factor(temp_f: float) -> float:
    """Warmer = more HR. +1F over 70F = +0.4% HR rate."""
    return 1.0 + (temp_f - 70.0) * 0.004


def _humidity_factor(humidity: float) -> float:
    """Higher humidity = slight HR suppress (dense air); 50% = baseline."""
    return 1.0 - (humidity - 50) * 0.0008


def _tier(score: float) -> str:
    if score >= 130: return "HOMER_FRIENDLY"
    if score >= 110: return "HITTER_FRIENDLY"
    if score >= 90: return "NEUTRAL"
    if score >= 70: return "PITCHER_FRIENDLY"
    return "PITCHER_GRAVEYARD"


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    weather = _load(os.path.join(DATA_DIR, "weather.json"))

    parks_today = today.get("parks") or {}
    weather_by_game = {w.get("matchup"): w
                       for w in (weather.get("games") or []) if isinstance(w, dict)}

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue") or ""
        # Park HR factor
        park_hr_factor = PARK_HR_FACTOR.get(park) or \
                         _safe((parks_today.get(park) or {}).get("hr_factor"), 1.0)

        # Weather
        w = weather_by_game.get(matchup) or g.get("weather") or {}
        wind_speed = _safe(w.get("wind_speed_mph") or w.get("wind_speed"), 0.0)
        wind_dir = w.get("wind_dir") or w.get("wind_direction") or ""
        temp = _safe(w.get("temp_f") or w.get("temperature"), 72.0)
        humidity = _safe(w.get("humidity_pct") or w.get("humidity"), 50.0)
        roof_closed = bool(w.get("roof_closed", False) or g.get("dome", False))

        wind_f = 1.0 if roof_closed else _wind_factor(wind_speed, wind_dir)
        temp_f = _temp_factor(temp)
        hum_f = _humidity_factor(humidity)

        # Composite: park * wind * temp * humidity, then scale to 0-150 (100 = neutral)
        composite = park_hr_factor * wind_f * temp_f * hum_f
        index = round(composite * 100, 1)
        tier = _tier(index)

        leans: List[str] = []
        if tier == "HOMER_FRIENDLY":
            leans = ["HR_OVER_AGGRESSIVE", "TB_OVER", "TEAM_TOTAL_OVER", "GAME_TOTAL_OVER"]
        elif tier == "HITTER_FRIENDLY":
            leans = ["HR_OVER_MILD", "TB_OVER_LEAN"]
        elif tier == "PITCHER_FRIENDLY":
            leans = ["HR_UNDER_LEAN", "GAME_TOTAL_UNDER_LEAN"]
        elif tier == "PITCHER_GRAVEYARD":
            leans = ["HR_UNDER_AGGRESSIVE", "TEAM_TOTAL_UNDER", "F5_TOTAL_UNDER"]

        out_games.append({
            "matchup": matchup,
            "park": park,
            "park_hr_factor": round(park_hr_factor, 3),
            "weather": {
                "wind_speed_mph": wind_speed,
                "wind_dir": wind_dir,
                "temp_f": temp,
                "humidity_pct": humidity,
                "roof_closed": roof_closed,
            },
            "factors": {
                "park": round(park_hr_factor, 3),
                "wind": round(wind_f, 3),
                "temp": round(temp_f, 3),
                "humidity": round(hum_f, 3),
            },
            "composite_index": index,
            "tier": tier,
            "leans": leans,
        })

    out_games.sort(key=lambda r: -r["composite_index"])
    n_homer = sum(1 for g in out_games if g["tier"] == "HOMER_FRIENDLY")
    n_graveyard = sum(1 for g in out_games if g["tier"] == "PITCHER_GRAVEYARD")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_homer_friendly": n_homer,
        "n_pitcher_graveyards": n_graveyard,
        "method_note": "HR Index = park_HR * wind_factor * temp_factor * humidity_factor "
                       "scaled to 100 = neutral. HOMER_FRIENDLY 130+, HITTER 110-130, "
                       "NEUTRAL 90-110, PITCHER 70-90, GRAVEYARD <70. "
                       "Drives HR/TB/Total OVER & UNDER leans.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hr-env] {o['n_games']} games, {o['n_homer_friendly']} homer-friendly, "
          f"{o['n_pitcher_graveyards']} graveyards -> {OUT}")
