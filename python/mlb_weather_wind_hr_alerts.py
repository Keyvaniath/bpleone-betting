"""
EdgeStat -- MLB weather wind HR alerts.

Surfaces games where weather conditions strongly favor HR scoring:
  - Wind blowing OUT (wind direction toward outfield)
  - Wind speed >= 12 mph
  - HOMER_FRIENDLY park tier
  - Hot temp (>= 75F)

When 3+ conditions align, recommend:
  - Game total OVER + HR-related props
  - Team total OVER for both sides
  - Top HR candidates from park_adjusted_hr_predictor

Output: data/mlb_weather_wind_hr_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_weather_wind_hr_alerts.json")


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
    weather = _load(os.path.join(DATA_DIR, "mlb_weather_advisory.json"))
    park = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_adjusted_hr_predictor.json"))

    # Build matchup-level weather
    weather_idx: Dict[str, Dict[str, Any]] = {}
    for g in (weather.get("games") or weather.get("rows") or []):
        if isinstance(g, dict):
            weather_idx[g.get("matchup", "")] = g

    park_idx: Dict[str, Dict[str, Any]] = {}
    for g in (park.get("games") or park.get("rows") or []):
        if isinstance(g, dict):
            park_idx[g.get("matchup", "")] = g

    # Top HR candidates per matchup from park_adjusted_hr_predictor
    hr_candidates_by_matchup: Dict[str, List[str]] = {}
    for c in (park_hr.get("candidates") or []):
        if isinstance(c, dict):
            m = c.get("matchup", "")
            if m:
                hr_candidates_by_matchup.setdefault(m, []).append(c.get("batter"))

    all_matchups = set(weather_idx) | set(park_idx)

    alerts: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        w = weather_idx.get(matchup, {})
        p = park_idx.get(matchup, {})

        wind_direction = (w.get("wind_direction") or w.get("wind_dir") or "").upper()
        wind_speed = _safe(w.get("wind_speed") or w.get("wind_mph"))
        temp = _safe(w.get("temperature") or w.get("temp_f"))
        park_tier = (p.get("tier") or "").upper()
        directional_leans = w.get("directional_leans") or []

        signals: Dict[str, int] = {}
        signals["WIND_BLOWING_OUT"] = 1 if "OUT" in wind_direction or any(
            "OUT" in str(l).upper() for l in directional_leans) else 0
        signals["WIND_SPEED_HIGH"] = 1 if wind_speed >= 12 else 0
        signals["HOMER_PARK"] = 1 if park_tier == "HOMER_FRIENDLY" else 0
        signals["HITTER_PARK"] = 1 if park_tier == "HITTER_FRIENDLY" else 0
        signals["HOT_TEMP"] = 1 if temp >= 75 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 2: continue

        if n_positive >= 4:
            tier = "WIND_HR_LOCK"
        elif n_positive >= 3:
            tier = "WIND_HR_STRONG"
        else:
            tier = "WIND_HR_LEAN"

        top_candidates = hr_candidates_by_matchup.get(matchup, [])[:3]

        alerts.append({
            "matchup": matchup,
            "wind_direction": wind_direction or None,
            "wind_speed_mph": wind_speed,
            "temp_f": temp,
            "park_tier": park_tier or None,
            "directional_leans": directional_leans,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "top_hr_candidates": top_candidates,
            "recommended_markets": [
                f"{matchup} game total OVER",
                f"{matchup} HR YES (game)",
                (f"{top_candidates[0]} HR YES" if top_candidates else ""),
                f"{matchup} both teams OVER team total",
            ],
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_wind_hr_lock": sum(1 for a in alerts if a["tier"] == "WIND_HR_LOCK"),
        "n_wind_hr_strong": sum(1 for a in alerts if a["tier"] == "WIND_HR_STRONG"),
        "method_note": "Weather + park HR alignment. Signals: WIND_BLOWING_OUT, "
                       "WIND_SPEED_HIGH (>=12 mph), HOMER_PARK, HITTER_PARK, "
                       "HOT_TEMP (>=75F). LOCK = 4+ signals; STRONG = 3; LEAN = 2.",
        "alerts": alerts,
        "locks_and_strong": [a for a in alerts
                             if a["tier"] in ("WIND_HR_LOCK", "WIND_HR_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-wind-hr] {o['n_alerts']} alerts "
          f"({o['n_wind_hr_lock']} LOCK, {o['n_wind_hr_strong']} STRONG) -> {OUT}")
