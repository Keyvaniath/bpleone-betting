"""
EdgeStat -- weather feed.

Open-Meteo (free, no API key) for game-time temperature, wind, humidity at each
MLB park. Wind direction relative to park orientation matters: wind blowing OUT
to center vs IN over the plate moves expected HR rate by 5-15%.

For now we expose: temp_f, wind_mph, wind_dir_deg, precip_pct, is_indoor.
The model can use these to adjust park_factor / HR projections.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


# Static park coordinates + orientation. Bearing of CF from home plate (deg from N).
# Wind blowing TO this bearing = wind out to CF (carry); wind blowing AGAINST = wind in.
PARKS: Dict[str, Dict[str, Any]] = {
    "Dodger Stadium": {"lat": 34.0739, "lon": -118.2400, "cf_bearing": 25, "indoor": False},
    "Petco Park": {"lat": 32.7073, "lon": -117.1566, "cf_bearing": 0, "indoor": False},
    "Yankee Stadium": {"lat": 40.8296, "lon": -73.9262, "cf_bearing": 75, "indoor": False},
    "Fenway Park": {"lat": 42.3467, "lon": -71.0972, "cf_bearing": 45, "indoor": False},
    "Citizens Bank Park": {"lat": 39.9061, "lon": -75.1665, "cf_bearing": 10, "indoor": False},
    "Truist Park": {"lat": 33.8908, "lon": -84.4678, "cf_bearing": 50, "indoor": False},
    "Coors Field": {"lat": 39.7559, "lon": -104.9942, "cf_bearing": 0, "indoor": False},
    "Wrigley Field": {"lat": 41.9484, "lon": -87.6553, "cf_bearing": 35, "indoor": False},
    "Citi Field": {"lat": 40.7571, "lon": -73.8458, "cf_bearing": 25, "indoor": False},
    "Oracle Park": {"lat": 37.7786, "lon": -122.3893, "cf_bearing": 95, "indoor": False},
    "Globe Life Field": {"lat": 32.7475, "lon": -97.0828, "cf_bearing": 0, "indoor": True},
    "Minute Maid Park": {"lat": 29.7570, "lon": -95.3551, "cf_bearing": 350, "indoor": True},
    "Daikin Park": {"lat": 29.7570, "lon": -95.3551, "cf_bearing": 350, "indoor": True},  # renamed
    "Tropicana Field": {"lat": 27.7682, "lon": -82.6534, "cf_bearing": 0, "indoor": True},
    "Rogers Centre": {"lat": 43.6414, "lon": -79.3894, "cf_bearing": 0, "indoor": True},  # retractable
    "Great American Ball Park": {"lat": 39.0975, "lon": -84.5070, "cf_bearing": 145, "indoor": False},
    "Busch Stadium": {"lat": 38.6226, "lon": -90.1928, "cf_bearing": 60, "indoor": False},
    "Chase Field": {"lat": 33.4453, "lon": -112.0667, "cf_bearing": 30, "indoor": True},  # retractable
    "Nationals Park": {"lat": 38.8730, "lon": -77.0074, "cf_bearing": 30, "indoor": False},
    "Oriole Park at Camden Yards": {"lat": 39.2839, "lon": -76.6219, "cf_bearing": 0, "indoor": False},
    "Comerica Park": {"lat": 42.3390, "lon": -83.0485, "cf_bearing": 145, "indoor": False},
    "Progressive Field": {"lat": 41.4962, "lon": -81.6852, "cf_bearing": 0, "indoor": False},
    "American Family Field": {"lat": 43.0280, "lon": -87.9712, "cf_bearing": 30, "indoor": True},
    "Target Field": {"lat": 44.9817, "lon": -93.2789, "cf_bearing": 60, "indoor": False},
    "Kauffman Stadium": {"lat": 39.0517, "lon": -94.4803, "cf_bearing": 50, "indoor": False},
    "Angel Stadium": {"lat": 33.8003, "lon": -117.8827, "cf_bearing": 60, "indoor": False},
    "Oakland Coliseum": {"lat": 37.7516, "lon": -122.2005, "cf_bearing": 60, "indoor": False},
    "Sutter Health Park": {"lat": 38.5805, "lon": -121.5128, "cf_bearing": 80, "indoor": False},
    "T-Mobile Park": {"lat": 47.5914, "lon": -122.3326, "cf_bearing": 0, "indoor": True},  # retractable
    "Rate Field": {"lat": 41.8300, "lon": -87.6339, "cf_bearing": 35, "indoor": False},
    "loanDepot park": {"lat": 25.7781, "lon": -80.2197, "cf_bearing": 40, "indoor": True},
    "PNC Park": {"lat": 40.4469, "lon": -80.0058, "cf_bearing": 60, "indoor": False},
    "UNIQLO Field at Dodger Stadium": {"lat": 34.0739, "lon": -118.2400, "cf_bearing": 25, "indoor": False},  # branded
}


CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "weather")


def _wind_carry_index(wind_dir_deg: float, wind_mph: float, cf_bearing: float) -> float:
    """How much the wind helps carry to center field. +1 = full tailwind out, -1 = full headwind."""
    # Wind direction is "from", so we need the inverse (direction the wind is blowing TO).
    blow_to = (wind_dir_deg + 180) % 360
    angle = (blow_to - cf_bearing + 540) % 360 - 180  # signed delta in [-180, 180]
    import math
    cos_a = math.cos(math.radians(angle))
    # Scale by wind speed; 15+ mph aligned wind = ~1.0
    return round(cos_a * min(wind_mph, 25) / 15.0, 3)


def get_weather(venue: str, game_time_iso: Optional[str] = None) -> Dict[str, Any]:
    """Forecast for venue at game time. Returns dict or {} if not resolvable."""
    park = PARKS.get(venue)
    if park is None:
        return {}
    if park.get("indoor"):
        return {"venue": venue, "indoor": True, "temp_f": 72, "wind_mph": 0,
                "wind_dir_deg": None, "precip_pct": 0, "carry_index": 0.0,
                "note": "indoor / retractable -- weather neutral"}
    if requests is None:
        return {}
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{venue.replace(' ', '_').replace('/', '_')}.json")
    # Cache 1hr -- forecasts update slowly enough to amortize.
    import time as _t
    if os.path.exists(cache_file) and _t.time() - os.path.getmtime(cache_file) < 3600:
        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            pass
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": park["lat"], "longitude": park["lon"],
            "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation_probability",
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "forecast_days": 2, "timezone": "America/New_York",
        }, timeout=10)
        if not r.ok:
            return {}
        data = r.json()
    except Exception:
        return {}
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return {}
    # Pick hour closest to game_time_iso (default: current local hour at venue).
    target = None
    if game_time_iso:
        try:
            target = dt.datetime.fromisoformat(game_time_iso.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:00")
        except Exception:
            pass
    if target and target in times:
        idx = times.index(target)
    else:
        idx = 0
    out = {
        "venue": venue,
        "indoor": False,
        "temp_f": round(hourly["temperature_2m"][idx]),
        "wind_mph": round(hourly["wind_speed_10m"][idx]),
        "wind_dir_deg": hourly["wind_direction_10m"][idx],
        "precip_pct": hourly["precipitation_probability"][idx],
        "carry_index": _wind_carry_index(hourly["wind_direction_10m"][idx],
                                          hourly["wind_speed_10m"][idx],
                                          park["cf_bearing"]),
        "forecast_hour": times[idx],
    }
    with open(cache_file, "w") as f:
        json.dump(out, f)
    return out


if __name__ == "__main__":
    for v in ("Coors Field", "Yankee Stadium", "Tropicana Field", "Dodger Stadium"):
        w = get_weather(v)
        print(f"{v}: {w}")
