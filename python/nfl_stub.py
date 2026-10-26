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
    # NEVER CLOBBER THE REAL FEED (2026-10-22). nfl_pipeline.py writes the live
    # NFL state (season_status 'regular', games, upcoming) earlier in
    # daily-pipeline; this scaffold ran ~140 steps LATER and overwrote it with
    # 'off-season / 0 games' on every run all season. nfl_player_props only
    # worked because it happens to run in between -- every other reader (the
    # NFL page, sport_coverage, NFL DFS receipts' DST scoring, the heartbeat)
    # saw the stub. If a real state is on disk, leave it alone.
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            cur = json.load(f)
        if cur.get("games") or cur.get("active_season") or cur.get("league") == "NFL":
            return cur
    except Exception:
        pass
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
    print(f"Wrote {OUT_PATH}: NFL stub (enabled={p.get('enabled', 'kept real feed')})")
