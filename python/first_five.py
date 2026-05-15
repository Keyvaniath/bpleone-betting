"""
EdgeStat -- First-5 (F5) totals.

F5 totals + F5 moneylines are popular markets that cleanly isolate the
starting-pitcher edge (no bullpen variance). The model:

  expected_F5_total = (home_SP_ERA/9 + away_SP_ERA/9) * 5 * park_factor
                       * weather_mult
  P(over X.5) = 1 - Poisson_CDF(X, expected_F5_total)

Writes data/first_five.json keyed by gamePk.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "first_five.json")
LEAGUE_ERA = 4.10


def _poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0
    s = 0.0
    term = math.exp(-lam)
    s += term
    for i in range(1, k + 1):
        term *= lam / i
        s += term
    return min(1.0, s)


def project_f5(home_pid: Optional[int], away_pid: Optional[int],
               park_factor: float = 1.0, env_mult: float = 1.0) -> Dict[str, Any]:
    """Return {fair_total, p_over_4_5, p_over_5_5, p_over_6_5, ...}."""
    def pitcher_era(pid):
        if not pid:
            return LEAGUE_ERA
        season = sr.pitcher_season(pid) or {}
        era = season.get("era")
        if era is None or era == 0:
            return LEAGUE_ERA
        recent = sr.pitcher_recent_form(pid, n=3) or {}
        recent_era = recent.get("era") if recent.get("starts", 0) >= 2 else None
        if recent_era is not None:
            return 0.6 * recent_era + 0.4 * era
        return era

    home_era = pitcher_era(home_pid)
    away_era = pitcher_era(away_pid)
    # Both starters pitch ~5 innings on average; runs per inning = ERA/9
    expected_runs_h_against_away = (away_era / 9.0) * 5
    expected_runs_a_against_home = (home_era / 9.0) * 5
    expected_total = (expected_runs_h_against_away + expected_runs_a_against_home) * park_factor * env_mult
    # Probabilities over common lines
    lines = [3.5, 4.5, 5.5, 6.5]
    p_over = {f"over_{int(L)}_5": round(1 - _poisson_cdf(int(L), expected_total), 4)
              for L in lines}
    return {
        "fair_total": round(expected_total, 2),
        "home_sp_era": round(home_era, 2),
        "away_sp_era": round(away_era, 2),
        "park_factor": park_factor,
        "env_mult": round(env_mult, 3),
        **p_over,
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    today_path = os.path.join(DATA_DIR, "today.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    # Also need weather + park from today.json
    today = {}
    if os.path.exists(today_path):
        with open(today_path) as f:
            today = json.load(f)
    today_by_match = {g["matchup"]: g for g in (today.get("games") or [])}

    try:
        from pipeline import PARK_FACTORS
    except Exception:
        PARK_FACTORS = {}

    out_games = []
    for g in m.get("games", []):
        venue = g.get("venue") or g.get("park")
        pf = PARK_FACTORS.get(venue, 1.0)
        wx = (today_by_match.get(g.get("matchup")) or {}).get("weather") or {}
        carry = wx.get("carry_index")
        env_mult = 1.0
        if carry is not None and not wx.get("is_indoor"):
            env_mult *= 1.0 + 0.10 * carry   # wind-carry affects F5 totals a bit less than full HR projections
        home_p = (g.get("home_pitcher") or {})
        away_p = (g.get("away_pitcher") or {})
        proj = project_f5(home_p.get("id"), away_p.get("id"), pf, env_mult)
        out_games.append({
            "matchup": g.get("matchup"),
            "time": g.get("time"),
            "park": venue,
            "home_pitcher": home_p.get("name"),
            "away_pitcher": away_p.get("name"),
            **proj,
        })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
    }


def write_first_five(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote first_five -> {path}")
    print(f"  Games projected: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        print(f"  {g['matchup']:14} | F5 fair total {g.get('fair_total')} | "
              f"P(O4.5)={g.get('over_4_5')} P(O5.5)={g.get('over_5_5')}")


if __name__ == "__main__":
    write_first_five(build_all())
