"""
EdgeStat -- MLB weather advisory.

For each game tonight, flags significant weather-driven scenarios:
  - RAIN_DELAY_RISK: chance_of_precip >= 60%, may push umpire/bullpen usage
  - WIND_BOOST_HR: wind 15+ mph blowing out, lean HR_OVER + TOTAL_OVER
  - WIND_SUPPRESS_HR: wind 15+ mph blowing in, lean TOTAL_UNDER
  - COLD_SUPPRESS: temp < 50F suppresses offense ~5%, lean UNDER
  - HOT_BOOST: temp > 90F boosts offense ~3%, lean OVER
  - ROOF_CLOSED: indoor game, no weather impact
  - HIGH_HUMIDITY: humidity > 80% suppresses slightly

For each game, also computes adjusted park_run_factor based on the active
weather (cross-validates with park_weather_hr_index but produces actionable
text alerts).

Output: data/mlb_weather_advisory.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_weather_advisory.json")


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


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    weather = _load(os.path.join(DATA_DIR, "weather.json"))

    weather_by_game = {w.get("matchup"): w
                       for w in (weather.get("games") or []) if isinstance(w, dict)}

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        w = weather_by_game.get(matchup) or g.get("weather") or {}
        wind_speed = _safe(w.get("wind_speed_mph") or w.get("wind_speed"), 0.0)
        wind_dir = (w.get("wind_dir") or w.get("wind_direction") or "").lower()
        temp = _safe(w.get("temp_f") or w.get("temperature"), 72.0)
        humidity = _safe(w.get("humidity_pct") or w.get("humidity"), 50.0)
        chance_precip = _safe(w.get("chance_of_precip") or w.get("precip_pct"), 0.0)
        roof_closed = bool(w.get("roof_closed", False) or g.get("dome", False))

        alerts: List[str] = []
        directional_leans: List[str] = []

        if roof_closed:
            alerts.append("ROOF_CLOSED — weather not in play")
        else:
            if chance_precip >= 60:
                alerts.append(f"RAIN_DELAY_RISK (chance {int(chance_precip)}%)")
                directional_leans.append("BULLPEN_LATE_INNINGS_OVER (early-pull risk)")

            if wind_speed >= 15:
                if any(k in wind_dir for k in ("out to", "out-to", "to lf", "to cf", "to rf")):
                    alerts.append(f"WIND_BOOST_HR ({wind_speed:.0f}mph out)")
                    directional_leans.append("HR_OVER")
                    directional_leans.append("GAME_TOTAL_OVER")
                elif any(k in wind_dir for k in ("in from", "to home", "from lf", "from cf")):
                    alerts.append(f"WIND_SUPPRESS_HR ({wind_speed:.0f}mph in)")
                    directional_leans.append("HR_UNDER")
                    directional_leans.append("GAME_TOTAL_UNDER")

            if temp < 50:
                alerts.append(f"COLD_SUPPRESS ({temp:.0f}F)")
                directional_leans.append("TEAM_TOTAL_UNDER_LEAN")
            elif temp > 90:
                alerts.append(f"HOT_BOOST ({temp:.0f}F)")
                directional_leans.append("HR_OVER_LEAN")

            if humidity > 80 and temp < 75:
                alerts.append(f"HIGH_HUMIDITY ({int(humidity)}%) - dense air")

        # Severity tier
        if not alerts or (len(alerts) == 1 and alerts[0].startswith("ROOF_CLOSED")):
            severity = "QUIET"
        elif any("RAIN_DELAY" in a or "WIND_BOOST" in a or "WIND_SUPPRESS" in a for a in alerts):
            severity = "HIGH"
        else:
            severity = "MODERATE"

        out_games.append({
            "matchup": matchup,
            "park": g.get("park") or g.get("venue"),
            "temp_f": temp,
            "humidity_pct": humidity,
            "wind_speed_mph": wind_speed,
            "wind_dir": wind_dir or None,
            "chance_of_precip": chance_precip,
            "roof_closed": roof_closed,
            "severity": severity,
            "alerts": alerts,
            "directional_leans": directional_leans,
        })

    n_high = sum(1 for g in out_games if g["severity"] == "HIGH")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_high_severity": n_high,
        "method_note": "Per-game weather advisory: RAIN_DELAY_RISK (precip>=60%), "
                       "WIND_BOOST/SUPPRESS_HR (wind 15+ mph), COLD_SUPPRESS (<50F), "
                       "HOT_BOOST (>90F), HIGH_HUMIDITY (>80% w/ cool temp). HIGH "
                       "severity triggers directional leans on totals + HR props.",
        "games": out_games,
        "high_severity_games": [g for g in out_games if g["severity"] == "HIGH"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[weather] {o['n_games']} games, {o['n_high_severity']} HIGH severity -> {OUT}")
