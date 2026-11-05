"""
EdgeStat -- KBO starting pitcher matchup adjustment.

KBO starting pitchers have material impact on game outcomes. We maintain
a static rotation snapshot (mid-season May 2026) with each team's top
3 starters + season ERA. When kbo_pipeline scrapes today's matchups,
we look up the projected starter and apply ERA-based runs adjustment.

For each KBO game, computes:
  - Expected starter for home/away
  - Pitcher quality adjustment (+/- expected runs allowed)
  - Adjusted home/away run lambdas (factored into Poisson MC)

Output: data/kbo_pitcher_adj.json (feeds into kbo_model via env var)

STARTERS REMOVED (2026-11-03): the "projected starter" was picked by
day_of_year % 3 from a static, hand-entered May-2026 3-man rotation -- a
fabricated input, not a probable-pitcher feed. That produced fake named
matchups on the page and a fake runs adjustment in kbo_model. Until a real
probable-starter source exists this module emits NO starters and NO
adjustment (no adjustment is honest; a fake one is not).
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "kbo_state.json")
OUT_PATH = os.path.join(DATA_DIR, "kbo_pitcher_adj.json")

# (2026-11-03) KBO_ROTATIONS (static May-2026 3-man rotations) deleted -- see
# the module docstring. No probable-starter source is wired.

KBO_LEAGUE_AVG_ERA = 4.30   # KBO league average ERA in recent seasons


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _runs_adjustment(starter_era: float) -> float:
    """Convert ERA delta from league average to expected runs allowed delta
    per 9 innings. KBO starters typically pitch ~6 IP, so prorate."""
    delta_era = starter_era - KBO_LEAGUE_AVG_ERA
    # 6 innings = 2/3 of 9, so multiply by 6/9 = 0.667
    return round(delta_era * (6.0 / 9.0), 2)


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    matches = state.get("matches") or []

    # (2026-11-03) no fabricated starters: no probable-pitcher source is
    # wired, so no game gets a starter or a runs adjustment.
    adjustments: List[Dict[str, Any]] = []

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": 0,
        "n_games_on_slate": len(matches),
        "league_avg_era": KBO_LEAGUE_AVG_ERA,
        "starter_source": None,
        "note": ("No verified probable-starter data; no starter adjustment is "
                 "applied. (The former day-of-year rotation guess was removed "
                 "2026-11-03.)"),
        "adjustments": adjustments,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"KBO pitcher adjustments: {p['n_games']} games -- {p['note']}")
