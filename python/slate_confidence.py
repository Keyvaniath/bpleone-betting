"""
EdgeStat -- pre-game slate confidence forecast.

Before games start, rate tonight's slate on factors that drive variance:
  - Lineup confirmation rate (more confirmed = less noise)
  - Weather predictability (calm vs windy/storms = noisier projections)
  - Pitcher experience (rookie SPs = noisier)
  - Weather-driven HR variance (high mult shifts = swingy slate)
  - Number of bullpen days (no real SP = swingy)

Output: data/slate_confidence.json
  {
    "generated_at": "...",
    "score": 78,                       # 0-100 composite
    "tier": "high" | "medium" | "low",
    "components": {
      "lineup_confirmed_pct": 0.92,
      "weather_stability": 0.85,
      "rookie_sp_count": 1,
      "bullpen_game_count": 0,
      "extreme_weather_count": 2
    },
    "summary": "...",
    "recommendation": "play normal sizing" | "smaller bets tonight" | "...",
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
WX_PATH = os.path.join(DATA_DIR, "weather_conditional.json")
FATIGUE_PATH = os.path.join(DATA_DIR, "pitcher_fatigue.json")
OUT_PATH = os.path.join(DATA_DIR, "slate_confidence.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    matchups = _load(MATCHUPS_PATH)
    wx = _load(WX_PATH)
    fatigue = _load(FATIGUE_PATH)

    games = today.get("games") or []
    matchup_games = matchups.get("games") or []
    n_games = len(games) or 1

    # Lineup confirmation rate
    confirmed = 0
    total_sides = 0
    for g in matchup_games:
        l = g.get("lineups") or {}
        for side in ("home", "away"):
            total_sides += 1
            sd = l.get(side) or []
            if isinstance(sd, list) and len(sd) >= 8:
                confirmed += 1
    lineup_pct = round(confirmed / total_sides, 3) if total_sides else 0

    # Weather stability: fraction of games with |hr_mult_delta_pct| < 5
    wx_games = wx.get("by_game") or []
    stable = sum(1 for g in wx_games if abs(g.get("hr_mult_delta_pct", 0)) < 5)
    weather_stability = round(stable / len(wx_games), 3) if wx_games else 1.0
    extreme_weather = sum(1 for g in wx_games if abs(g.get("hr_mult_delta_pct", 0)) >= 10)

    # Rookie SPs (career < 50 starts)
    rookie_sp = 0
    bullpen_games = 0
    for g in matchup_games:
        for side in ("home_pitcher", "away_pitcher"):
            p = g.get(side) or {}
            career = p.get("career") or {}
            starts = career.get("starts")
            if starts is None or starts < 50:
                if p.get("id"):
                    rookie_sp += 1
            elif starts == 0 or not p.get("id"):
                bullpen_games += 1

    # High-risk early hooks (from pitcher_fatigue)
    high_risk_hooks = len(fatigue.get("high_risk") or [])

    # Compose score 0-100
    score = 100
    score -= int((1 - lineup_pct) * 30)           # full unconfirmed slate -> -30
    score -= int((1 - weather_stability) * 25)     # variable weather -> -25
    score -= min(rookie_sp * 3, 15)                # rookies add noise -> -15 max
    score -= min(bullpen_games * 4, 12)            # bullpen days -> -12 max
    score -= min(high_risk_hooks * 2, 10)          # early-hook SPs -> -10 max
    score = max(0, min(100, score))

    tier = "high" if score >= 75 else "medium" if score >= 55 else "low"
    rec = ({"high":   "Play normal Kelly sizing.",
            "medium": "Slightly smaller bets; skip pre-cal edges (>15%).",
            "low":    "Defensive sizing tonight; stick to highest-confidence plays."})[tier]

    summary_parts = []
    summary_parts.append(f"{int(lineup_pct*100)}% lineups confirmed")
    if extreme_weather:
        summary_parts.append(f"{extreme_weather} extreme-weather games")
    if rookie_sp:
        summary_parts.append(f"{rookie_sp} rookie SPs")
    if bullpen_games:
        summary_parts.append(f"{bullpen_games} bullpen-day games")
    if high_risk_hooks:
        summary_parts.append(f"{high_risk_hooks} high early-hook risk SPs")
    summary = " · ".join(summary_parts)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "score": score,
        "tier": tier,
        "n_games": n_games,
        "components": {
            "lineup_confirmed_pct": lineup_pct,
            "weather_stability": weather_stability,
            "extreme_weather_games": extreme_weather,
            "rookie_sp_count": rookie_sp,
            "bullpen_game_count": bullpen_games,
            "high_risk_hooks": high_risk_hooks,
        },
        "summary": summary,
        "recommendation": rec,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Score: {p['score']}/100 ({p['tier']})")
    print(f"  {p['summary']}")
    print(f"  Rec: {p['recommendation']}")
