"""
EdgeStat -- NFL desk stub.

Scaffolding for an NFL pipeline. Smaller weekly cadence than MLB but each
game has heavier sample-size implications and richer prop markets
(passing yards, rushing TDs, anytime TD scorer, etc.). When activated will
reuse the calibration loop with weekly windowing instead of daily.

Output: data/nfl_state.json
"""
from __future__ import annotations
import os, json, datetime as dt

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "nfl_state.json")

try:
    import config as _cfg
    ENABLED = _cfg.get("nfl.enabled", False)
except Exception:
    ENABLED = False


def run():
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "enabled": ENABLED,
        "season_status": "off-season",
        "week": None,
        "next_games_count": 0,
        "note": "NFL desk scaffolded; reuses calibration loop with weekly windowing.",
        "planned_features": [
            "DVOA-style team strength + opponent adjustments",
            "Weather + dome bias",
            "QB-specific yardage / TD / pick projections",
            "Anytime TD scorer model (Poisson on usage_pct)",
            "Live in-game possession-based win prob",
            "Sunday morning injury alerts",
        ],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: NFL stub (enabled={p['enabled']})")
