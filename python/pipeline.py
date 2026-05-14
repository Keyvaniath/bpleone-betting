"""
EdgeStat - daily pipeline.

End-to-end:
  1. Pull schedule + odds from APIs.
  2. Hydrate per-game context (pitchers, parks, weather, umpire).
  3. Run mlb_model.project_game() on each.
  4. Filter to +EV plays above edge threshold.
  5. Pick Play of the Day (highest-confidence, highest-edge).
  6. Write a JSON manifest the front-end can hot-reload.

Cron it at 7:00 ET every morning and re-run hourly to catch line moves.
"""
from __future__ import annotations

import json
import os
import datetime as dt
from typing import Any, Dict, List

from mlb_model import project_game, GameInput, TeamFactor, PitcherFactor, GameContext


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "today.json")


# --- Static lookup tables. In production these come from your DB / nightly refresh ---

PARK_FACTORS = {
    "Dodger Stadium": 0.96, "Petco Park": 0.91, "Yankee Stadium": 1.08,
    "Fenway Park": 1.05, "Citizens Bank Park": 1.06, "Truist Park": 1.02,
    "Coors Field": 1.20, "Wrigley Field": 1.00, "Citi Field": 0.95,
    "Oracle Park": 0.89, "Globe Life Field": 1.04, "Minute Maid Park": 1.01,
    "Tropicana Field": 0.93, "Rogers Centre": 1.03, "Great American Ball Park": 1.12,
    "Busch Stadium": 0.98, "Chase Field": 1.02, "Nationals Park": 0.99,
}


def run_pipeline(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a list of game dicts into a daily manifest."""
    out_games = []
    best = None
    for g in games:
        proj = project_game(_to_input(g))
        record = {
            "matchup": f"{g['away']['code']} @ {g['home']['code']}",
            "time": g.get("time", "TBD"),
            "park": g.get("park", "Unknown"),
            "model": {
                "fair_home_ml": proj.fair_ml_home,
                "fair_away_ml": proj.fair_ml_away,
                "fair_total": round(proj.fair_total, 2),
                "p_home_win": round(proj.p_home_win, 4),
                "p_away_win": round(proj.p_away_win, 4),
                "p_over_market": round(proj.p_over.get(g.get("market_total", 8.5), 0), 4),
            },
            "market": {
                "home_ml": g.get("market_ml_home"),
                "away_ml": g.get("market_ml_away"),
                "total": g.get("market_total"),
            },
            "recommendations": proj.recommendations,
        }
        out_games.append(record)
        # Track the highest-edge play in the slate.
        for r in proj.recommendations:
            if best is None or r["edge_pct"] > best["edge_pct"]:
                best = {**r, "matchup": record["matchup"], "time": record["time"]}
    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
        "play_of_day": best,
    }
    return manifest


def _to_input(g: Dict[str, Any]) -> GameInput:
    return GameInput(
        away=TeamFactor(**g["away"]),
        home=TeamFactor(**g["home"]),
        away_pitcher=PitcherFactor(**g["away_pitcher"]),
        home_pitcher=PitcherFactor(**g["home_pitcher"]),
        ctx=GameContext(**g["ctx"]),
        market_total=g.get("market_total", 8.5),
        market_ml_away=g.get("market_ml_away", 100),
        market_ml_home=g.get("market_ml_home", -110),
    )


def write_manifest(manifest: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest → {path}")
    print(f"  Games: {len(manifest['games'])}")
    if manifest.get("play_of_day"):
        pod = manifest["play_of_day"]
        print(f"  Play of Day: {pod['matchup']} | {pod['label']} | "
              f"edge +{pod['edge_pct']:.2f}% | {pod['kelly_units']:.1f}u")


# --- Demo: hard-coded slate from data.js, fully self-contained ---

DEMO_SLATE = [
    {
        "time": "7:05p ET", "park": "Petco Park", "market_total": 8.0,
        "market_ml_away": +126, "market_ml_home": -148,
        "away": {"code": "SDP", "offensive_wrc_plus": 104, "bullpen_era_fip_delta": +0.41, "rest_days": 1},
        "home": {"code": "LAD", "offensive_wrc_plus": 124, "bullpen_era_fip_delta": -0.46, "rest_days": 1},
        "away_pitcher": {"name": "Darvish", "xfip": 4.12, "k_per_9": 9.1, "bb_per_9": 2.8, "hand": "R"},
        "home_pitcher": {"name": "Yamamoto", "xfip": 2.89, "k_per_9": 10.4, "bb_per_9": 2.1, "hand": "R"},
        "ctx": {"park_factor": 0.91, "temp_f": 62, "wind_mph": -6, "umpire_zone_size": 0.018, "is_indoor": False},
    },
    {
        "time": "6:45p ET", "park": "Yankee Stadium", "market_total": 9.0,
        "market_ml_away": +115, "market_ml_home": -128,
        "away": {"code": "BOS", "offensive_wrc_plus": 109, "bullpen_era_fip_delta": +0.18, "rest_days": 1},
        "home": {"code": "NYY", "offensive_wrc_plus": 119, "bullpen_era_fip_delta": -0.22, "rest_days": 1},
        "away_pitcher": {"name": "Crochet", "xfip": 3.05, "k_per_9": 11.8, "bb_per_9": 2.0, "hand": "L"},
        "home_pitcher": {"name": "Cole", "xfip": 3.18, "k_per_9": 11.2, "bb_per_9": 2.4, "hand": "R"},
        "ctx": {"park_factor": 1.08, "temp_f": 71, "wind_mph": 12, "umpire_zone_size": -0.01, "is_indoor": False},
    },
    {
        "time": "9:40p ET", "park": "Coors Field", "market_total": 10.5,
        "market_ml_away": -110, "market_ml_home": +100,
        "away": {"code": "CIN", "offensive_wrc_plus": 105, "bullpen_era_fip_delta": -0.05, "rest_days": 1},
        "home": {"code": "COL", "offensive_wrc_plus": 92,  "bullpen_era_fip_delta": +0.55, "rest_days": 1},
        "away_pitcher": {"name": "Greene", "xfip": 3.40, "k_per_9": 11.0, "bb_per_9": 3.0, "hand": "R"},
        "home_pitcher": {"name": "Freeland", "xfip": 4.80, "k_per_9": 6.3, "bb_per_9": 2.7, "hand": "L"},
        "ctx": {"park_factor": 1.20, "temp_f": 74, "wind_mph": 4, "umpire_zone_size": 0.0, "is_indoor": False},
    },
]


if __name__ == "__main__":
    manifest = run_pipeline(DEMO_SLATE)
    write_manifest(manifest)
    print(json.dumps(manifest["play_of_day"], indent=2))
