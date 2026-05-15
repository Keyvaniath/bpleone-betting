"""
EdgeStat -- NRFI / YRFI projections.

NRFI = No Runs in First Inning (both teams score 0 in the top + bottom of 1st)
YRFI = Yes Runs in First Inning (>= 1 run scored)

For each game in today's slate, model:
  P(NRFI) = P(home SP holds top of 1st) * P(away SP holds bottom of 1st)
  P(YRFI) = 1 - P(NRFI)

Per-pitcher P(scoreless inning) blend:
  - Season ERA/9 -> Poisson rate per inning -> exp(-rate)
  - Blended 60% recent / 40% season for responsiveness
  - Park factor scales the rate
  - 1st-inning historical splits if available

Writes data/nrfi.json keyed by gamePk + matchup.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "nrfi.json")

LEAGUE_ERA = 4.10
NRFI_LEAGUE_AVG = 0.54   # ~54% of MLB games are NRFI historically


def _p_scoreless_inning(era: float, park_factor: float = 1.0) -> float:
    """P(0 runs allowed in 1 inning) ~= exp(-runs_per_inning). Park-adjusted."""
    if era <= 0 or era > 12:
        era = LEAGUE_ERA
    rate_per_inn = (era / 9.0) * park_factor
    return math.exp(-rate_per_inn)


def project_nrfi(home_pid: Optional[int], away_pid: Optional[int],
                 park_factor: float = 1.0) -> Dict[str, Any]:
    """Return {p_nrfi, p_yrfi, debug}."""
    def pitcher_era(pid):
        if not pid:
            return LEAGUE_ERA, "league_default"
        season = sr.pitcher_season(pid) or {}
        era = season.get("era")
        if era is None or era == 0:
            return LEAGUE_ERA, "no_data"
        # Recent-form blend
        recent = sr.pitcher_recent_form(pid, n=3) or {}
        recent_era = recent.get("era") if recent.get("starts", 0) >= 2 else None
        if recent_era is not None:
            return 0.6 * recent_era + 0.4 * era, "blended"
        return era, "season_only"

    home_era, home_src = pitcher_era(home_pid)
    away_era, away_src = pitcher_era(away_pid)
    p_top_scoreless = _p_scoreless_inning(away_era, park_factor)
    p_bot_scoreless = _p_scoreless_inning(home_era, park_factor)
    p_nrfi = p_top_scoreless * p_bot_scoreless
    return {
        "p_nrfi": round(p_nrfi, 4),
        "p_yrfi": round(1 - p_nrfi, 4),
        "fair_yrfi_price": _fair_american(1 - p_nrfi),
        "fair_nrfi_price": _fair_american(p_nrfi),
        "debug": {
            "home_era": round(home_era, 2), "home_src": home_src,
            "away_era": round(away_era, 2), "away_src": away_src,
            "park_factor": park_factor,
            "p_top_scoreless": round(p_top_scoreless, 4),
            "p_bot_scoreless": round(p_bot_scoreless, 4),
        },
    }


def _fair_american(prob: float) -> int:
    """Convert probability to fair American odds (no vig)."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return -int(round(prob / (1 - prob) * 100))
    return int(round((1 - prob) / prob * 100))


def build_all() -> Dict[str, Any]:
    """Read today.json's slate metadata + matchups for IDs, project NRFI per game."""
    # Need pitcher IDs which live in matchups.json (today.json strips _meta)
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)

    try:
        from pipeline import PARK_FACTORS
    except Exception:
        PARK_FACTORS = {}

    out_games = []
    for g in m.get("games", []):
        venue = g.get("venue") or g.get("park")
        pf = PARK_FACTORS.get(venue, 1.0)
        home_p = (g.get("home_pitcher") or {})
        away_p = (g.get("away_pitcher") or {})
        proj = project_nrfi(home_p.get("id"), away_p.get("id"), pf)
        out_games.append({
            "matchup": g.get("matchup"),
            "time": g.get("time"),
            "park": venue,
            "home_pitcher": home_p.get("name"),
            "away_pitcher": away_p.get("name"),
            **proj,
        })
    # Sort by absolute distance from league avg = "biggest market vs reality gaps"
    out_games.sort(key=lambda x: abs((x.get("p_nrfi") or NRFI_LEAGUE_AVG) - NRFI_LEAGUE_AVG),
                   reverse=True)
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "league_nrfi_baseline": NRFI_LEAGUE_AVG,
        "games": out_games,
    }


def write_nrfi(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote nrfi -> {path}")
    print(f"  Games projected: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        print(f"  {g['matchup']:14} | P(NRFI) {g.get('p_nrfi')} (fair {g.get('fair_nrfi_price'):+d}) | "
              f"P(YRFI) {g.get('p_yrfi')} (fair {g.get('fair_yrfi_price'):+d})")


if __name__ == "__main__":
    write_nrfi(build_all())
