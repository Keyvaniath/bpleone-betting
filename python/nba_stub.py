"""
EdgeStat -- NBA desk stub.

Scaffolding for an NBA pipeline. When activated (config knob nba.enabled=true)
will pull team true-talent, per-game prop projections, and run through the
same calibration loop as MLB. Until then, just writes a placeholder data
file so /nba.html can render the "coming soon" state.

Output: data/nba_state.json
  {
    "enabled": false,
    "season_status": "off-season" | "regular" | "playoffs",
    "next_games_count": 0,
    "note": "Activate by setting nba.enabled=true in runtime_config.json"
  }
"""
from __future__ import annotations
import os, json, datetime as dt

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "nba_state.json")

try:
    import config as _cfg
    ENABLED = _cfg.get("nba.enabled", False)
except Exception:
    ENABLED = False


def run():
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "enabled": ENABLED,
        "season_status": "off-season",
        "next_games_count": 0,
        "note": ("NBA desk scaffolded but not yet activated. When enabled, "
                  "will reuse calibration loop + recommender + bet tracker "
                  "infrastructure with NBA-specific feature engineering."),
        "planned_features": [
            "Per-team Net Rating + pace",
            "Player usage rate + minutes projection",
            "Rest-day splits",
            "Back-to-back fatigue",
            "Live in-game pace tracker",
            "Playoff seeding scenarios",
        ],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: NBA stub (enabled={p['enabled']})")
