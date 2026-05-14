"""
EdgeStat - Feature engineering pipeline.

Feature engineering is 80% of what makes an ML model good.  This module
documents every feature we extract from raw inputs and how each one is
computed, transformed, and validated.

Feature families:
  1. Team strength       (wRC+, ELO, Glicko, Pythag pct, last-N form)
  2. Starting pitcher    (xFIP, K/9, BB/9, HR/9, recent velocity, TTO penalty)
  3. Bullpen             (ERA-FIP gap, fatigue index, high-leverage availability)
  4. Park & weather      (park factor, wind, temp, humidity, indoor flag)
  5. Umpire              (zone size, called-strike rate, run environment)
  6. Schedule context    (rest days, travel miles, day-after-night, getaway day)
  7. Lineup              (handedness platoon split, slot weighted PAs)
  8. Market signal       (opening line, current line, public/sharp split)

The output is a flat feature vector ready for any of our models.
"""
from __future__ import annotations

import math
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# --------------------------- Raw inputs ---------------------------

@dataclass
class RawGame:
    home: str
    away: str
    home_team_stats: Dict[str, float] = field(default_factory=dict)
    away_team_stats: Dict[str, float] = field(default_factory=dict)
    home_pitcher: Dict[str, float] = field(default_factory=dict)
    away_pitcher: Dict[str, float] = field(default_factory=dict)
    home_bullpen: Dict[str, float] = field(default_factory=dict)
    away_bullpen: Dict[str, float] = field(default_factory=dict)
    home_ratings: Dict[str, float] = field(default_factory=dict)
    away_ratings: Dict[str, float] = field(default_factory=dict)
    park: Dict[str, float] = field(default_factory=dict)
    weather: Dict[str, float] = field(default_factory=dict)
    umpire: Dict[str, float] = field(default_factory=dict)
    schedule: Dict[str, float] = field(default_factory=dict)
    market: Dict[str, float] = field(default_factory=dict)


# --------------------------- Single-feature transformers ---------------------------

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def _zscore(x: float, mean: float, std: float) -> float:
    return (x - mean) / std if std > 0 else 0.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# League constants (refresh once per season).
LEAGUE = {
    "wrc_plus_mean": 100, "wrc_plus_std": 22,
    "xfip_mean": 4.00, "xfip_std": 0.7,
    "k9_mean": 9.2, "k9_std": 1.8,
    "bb9_mean": 3.0, "bb9_std": 0.9,
    "hr9_mean": 1.1, "hr9_std": 0.4,
    "bullpen_eraf_mean": 0.0, "bullpen_eraf_std": 0.4,
    "park_factor_mean": 1.0, "park_factor_std": 0.06,
    "elo_mean": 1500, "elo_std": 50,
}


@dataclass
class FeatureSpec:
    name: str
    family: str
    description: str


# Master registry. The order here is also the model input order.
FEATURE_SPECS: List[FeatureSpec] = [
    # ----- Team strength -----
    FeatureSpec("wrc_diff",       "team",     "Home wRC+ minus away wRC+ (z-scored)"),
    FeatureSpec("pythag_diff",    "team",     "Home Pythag win pct minus away (centered)"),
    FeatureSpec("form_diff_L10",  "team",     "Home L10 wins minus away L10 wins"),
    FeatureSpec("elo_diff",       "team",     "Home Elo - away Elo (z-scored)"),
    FeatureSpec("glicko_diff",    "team",     "Home Glicko - away Glicko"),

    # ----- Starting pitcher -----
    FeatureSpec("xfip_diff",      "pitcher",  "Away starter xFIP - home starter xFIP (positive = home better)"),
    FeatureSpec("k9_diff",        "pitcher",  "Home K/9 - away K/9"),
    FeatureSpec("bb9_diff",       "pitcher",  "Away BB/9 - home BB/9"),
    FeatureSpec("hr9_diff",       "pitcher",  "Away HR/9 - home HR/9"),
    FeatureSpec("velocity_trend", "pitcher",  "Home pitcher 5-start velocity Z-score"),
    FeatureSpec("tto_diff",       "pitcher",  "Home pitcher TTO penalty (lower = better)"),

    # ----- Bullpen -----
    FeatureSpec("bullpen_eraf_diff", "bullpen", "Home bullpen ERA-FIP - away (negative = home better)"),
    FeatureSpec("bullpen_rest",      "bullpen", "Home high-leverage reliever rest days"),
    FeatureSpec("bullpen_avail",     "bullpen", "Available bullpen IP cushion vs opp"),

    # ----- Park / weather -----
    FeatureSpec("park_factor",       "park",   "3-yr run factor"),
    FeatureSpec("park_hr_factor",    "park",   "3-yr HR factor"),
    FeatureSpec("wind_mph",          "weather", "Signed wind speed (+ = out, - = in)"),
    FeatureSpec("temp_norm",         "weather", "Normalized temperature"),
    FeatureSpec("humidity",          "weather", "Relative humidity (0-1)"),
    FeatureSpec("indoor",            "weather", "1 if roof closed, 0 otherwise"),

    # ----- Umpire -----
    FeatureSpec("ump_zone_size",     "umpire",  "Plate ump zone size delta vs league"),
    FeatureSpec("ump_k_pct",         "umpire",  "Plate ump strikeout pct"),

    # ----- Schedule -----
    FeatureSpec("rest_diff",         "schedule", "Home rest days - away rest days"),
    FeatureSpec("travel_diff",       "schedule", "Away travel miles - home travel miles"),
    FeatureSpec("day_after_night",   "schedule", "1 if day game following night game (away)"),
    FeatureSpec("getaway",           "schedule", "1 if getaway day for away team"),

    # ----- Lineup -----
    FeatureSpec("platoon_advantage", "lineup",  "Home batters w/ platoon adv vs starting pitcher"),
    FeatureSpec("lineup_continuity", "lineup",  "Lineup match vs. season norm (1.0 = ideal)"),

    # ----- Market -----
    FeatureSpec("line_move_pct",     "market",  "Line implied prob delta from open to current"),
    FeatureSpec("sharp_handle_pct",  "market",  "Pct of total handle on home team"),
]


# --------------------------- Extraction ---------------------------

def extract_features(g: RawGame) -> Dict[str, float]:
    """Take a RawGame and produce a flat feature dictionary."""
    f: Dict[str, float] = {}

    # Team strength
    f["wrc_diff"] = _zscore(g.home_team_stats.get("wrc_plus", 100) - g.away_team_stats.get("wrc_plus", 100),
                            0, LEAGUE["wrc_plus_std"])
    f["pythag_diff"] = g.home_team_stats.get("pythag_pct", 0.5) - g.away_team_stats.get("pythag_pct", 0.5)
    f["form_diff_L10"] = g.home_team_stats.get("L10_wins", 5) - g.away_team_stats.get("L10_wins", 5)
    f["elo_diff"] = _zscore(g.home_ratings.get("elo", 1500) - g.away_ratings.get("elo", 1500),
                            0, LEAGUE["elo_std"])
    f["glicko_diff"] = g.home_ratings.get("glicko", 1500) - g.away_ratings.get("glicko", 1500)

    # Pitching
    f["xfip_diff"] = g.away_pitcher.get("xfip", 4.0) - g.home_pitcher.get("xfip", 4.0)
    f["k9_diff"]   = g.home_pitcher.get("k9", 9.2) - g.away_pitcher.get("k9", 9.2)
    f["bb9_diff"]  = g.away_pitcher.get("bb9", 3.0) - g.home_pitcher.get("bb9", 3.0)
    f["hr9_diff"]  = g.away_pitcher.get("hr9", 1.1) - g.home_pitcher.get("hr9", 1.1)
    f["velocity_trend"] = g.home_pitcher.get("velo_z", 0)
    f["tto_diff"]  = g.home_pitcher.get("tto_penalty", 1.0) - g.away_pitcher.get("tto_penalty", 1.0)

    # Bullpen
    f["bullpen_eraf_diff"] = g.home_bullpen.get("era_fip", 0) - g.away_bullpen.get("era_fip", 0)
    f["bullpen_rest"] = g.home_bullpen.get("rest_days", 1)
    f["bullpen_avail"] = g.home_bullpen.get("available_ip", 5) - g.away_bullpen.get("available_ip", 5)

    # Park & weather
    f["park_factor"] = g.park.get("run_factor", 1.0)
    f["park_hr_factor"] = g.park.get("hr_factor", 1.0)
    f["wind_mph"] = g.weather.get("wind_mph", 0)
    f["temp_norm"] = _zscore(g.weather.get("temp_f", 70), 70, 12)
    f["humidity"]  = g.weather.get("humidity", 0.5)
    f["indoor"]    = 1.0 if g.weather.get("is_indoor", False) else 0.0

    # Umpire
    f["ump_zone_size"] = g.umpire.get("zone_size", 0)
    f["ump_k_pct"]     = g.umpire.get("k_pct", 0.22)

    # Schedule
    f["rest_diff"]      = g.schedule.get("home_rest", 1) - g.schedule.get("away_rest", 1)
    f["travel_diff"]    = g.schedule.get("away_travel_miles", 500) - g.schedule.get("home_travel_miles", 0)
    f["day_after_night"] = 1.0 if g.schedule.get("day_after_night", False) else 0.0
    f["getaway"]         = 1.0 if g.schedule.get("getaway", False) else 0.0

    # Lineup
    f["platoon_advantage"] = g.home_team_stats.get("platoon_adv_count", 4) - g.away_team_stats.get("platoon_adv_count", 4)
    f["lineup_continuity"] = g.home_team_stats.get("lineup_continuity", 1.0)

    # Market
    open_p  = g.market.get("open_implied_home", 0.55)
    curr_p  = g.market.get("current_implied_home", 0.55)
    f["line_move_pct"]    = (curr_p - open_p) * 100
    f["sharp_handle_pct"] = g.market.get("home_handle_pct", 50.0) / 100.0

    return f


def to_vector(features: Dict[str, float]) -> List[float]:
    """Flatten a feature dict into the canonical order defined by FEATURE_SPECS."""
    return [features.get(spec.name, 0.0) for spec in FEATURE_SPECS]


def describe_features() -> List[Dict]:
    """Self-describing schema for the front-end / docs."""
    return [
        {"name": s.name, "family": s.family, "description": s.description}
        for s in FEATURE_SPECS
    ]


# --------------------------- Demo / artifact writer ---------------------------

def example_raw_game() -> RawGame:
    return RawGame(
        home="LAD", away="SDP",
        home_team_stats={"wrc_plus": 124, "pythag_pct": 0.62, "L10_wins": 8,
                         "platoon_adv_count": 6, "lineup_continuity": 0.96},
        away_team_stats={"wrc_plus": 104, "pythag_pct": 0.49, "L10_wins": 4,
                         "platoon_adv_count": 3, "lineup_continuity": 0.92},
        home_pitcher={"xfip": 2.89, "k9": 10.4, "bb9": 2.1, "hr9": 0.7,
                      "velo_z": 0.4, "tto_penalty": 1.04},
        away_pitcher={"xfip": 4.12, "k9": 9.1, "bb9": 2.8, "hr9": 1.3,
                      "velo_z": -0.2, "tto_penalty": 1.08},
        home_bullpen={"era_fip": -0.46, "rest_days": 2, "available_ip": 9.0},
        away_bullpen={"era_fip": +0.41, "rest_days": 1, "available_ip": 6.5},
        home_ratings={"elo": 1592, "glicko": 1584},
        away_ratings={"elo": 1521, "glicko": 1525},
        park={"run_factor": 0.91, "hr_factor": 0.88},
        weather={"wind_mph": -6, "temp_f": 62, "humidity": 0.68, "is_indoor": False},
        umpire={"zone_size": 0.018, "k_pct": 0.234},
        schedule={"home_rest": 1, "away_rest": 1,
                  "home_travel_miles": 0, "away_travel_miles": 120,
                  "day_after_night": False, "getaway": True},
        market={"open_implied_home": 0.582, "current_implied_home": 0.617,
                "home_handle_pct": 71.0},
    )


if __name__ == "__main__":
    g = example_raw_game()
    feats = extract_features(g)
    vec = to_vector(feats)
    print("=== Extracted Feature Vector (LAD/SDP example) ===")
    for spec in FEATURE_SPECS:
        v = feats[spec.name]
        print(f"  {spec.name:24s} [{spec.family:9s}] = {v:+.4f}")
    print(f"\nVector length: {len(vec)}")

    out = {
        "schema":      describe_features(),
        "example_game": {
            "home": g.home, "away": g.away,
            "features": {k: round(v, 4) for k, v in feats.items()},
            "vector":   [round(v, 4) for v in vec],
        },
        "league_constants": LEAGUE,
    }
    os.makedirs("../data", exist_ok=True)
    with open("../data/features.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote ../data/features.json")
