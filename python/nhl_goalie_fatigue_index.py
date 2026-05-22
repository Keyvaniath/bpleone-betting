"""
EdgeStat -- NHL goalie fatigue / workload index.

For each starting goalie tonight, computes a 0-100 fatigue index based on:
  - Games started in last 5 days
  - Total saves in last 5 days
  - Back-to-back start flag
  - Days since last appearance

Tiers:
  0-25:    FRESH         — Goalie rested 3+ days, prime starting condition
  25-50:   NORMAL        — Typical rotation usage
  50-70:   TIRED         — 3 starts in 5 days or 80+ saves in 5 days
  70-100:  GASSED        — 4 starts in 5 days or B2B with high save volume

Consumers:
  - nhl_goalie_saves_props: lean UNDER on TIRED/GASSED, OVER on FRESH
  - nhl_goalie_win_props: lean UNDER (opp goal-rate up vs tired goalie)
  - nhl_anytime_goal_props: opp skaters get HIGHER expected goals vs tired G
  - nhl_skater_2plus_points: same opponent boost

Output: data/nhl_goalie_fatigue_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _tier(score: float) -> str:
    if score >= 70: return "GASSED"
    if score >= 50: return "TIRED"
    if score >= 25: return "NORMAL"
    return "FRESH"


def _compute_fatigue(goalie: Dict[str, Any]) -> Dict[str, Any]:
    starts_5d = int(_safe(goalie.get("starts_last_5d"), 2))  # baseline ~2/5
    saves_5d = _safe(goalie.get("saves_last_5d"), 60)
    b2b = bool(goalie.get("back_to_back", False))
    days_since_last = int(_safe(goalie.get("days_since_last_start"), 2))

    score = 30.0  # NORMAL baseline
    # Starts: above 2 in 5 days = tired (4 starts is gassed)
    score += max(0, (starts_5d - 2)) * 18
    # Saves: above 70 in 5 days = workload spike
    score += max(0, (saves_5d - 70)) * 0.6
    # Back-to-back
    if b2b: score += 22
    # Days since last
    score -= (days_since_last - 2) * 6  # rested
    score = max(0.0, min(100.0, score))

    return {
        "score": round(score, 1),
        "tier": _tier(score),
        "starts_last_5d": starts_5d,
        "saves_last_5d": round(saves_5d, 0),
        "back_to_back": b2b,
        "days_since_last_start": days_since_last,
    }


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    goalie_logs = _load(os.path.join(DATA_DIR, "nhl_goalie_logs.json"))
    g_idx = {(g.get("name") or "").lower(): g
             for g in (goalie_logs.get("goalies") or [])
             if isinstance(g, dict)}

    games = state.get("games") or state.get("events") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home_team = (g.get("home_team") or g.get("home") or "").upper()
        away_team = (g.get("away_team") or g.get("away") or "").upper()
        if not home_team or not away_team: continue
        matchup = f"{away_team} @ {home_team}"

        sides_out: Dict[str, Any] = {}
        for side, goalie_field in (("home", "home_goalie"), ("away", "away_goalie")):
            goalie_raw = g.get(goalie_field)
            goalie_name = goalie_raw if isinstance(goalie_raw, str) else (goalie_raw or {}).get("name")
            if not goalie_name: continue
            goalie_row = g_idx.get(goalie_name.lower(), {})
            recent = goalie_row.get("recent") or {}
            # Merge recent stats into goalie row for unified access
            merged = {
                "starts_last_5d": recent.get("starts_l5d"),
                "saves_last_5d": recent.get("saves_l5d"),
                "back_to_back": recent.get("back_to_back"),
                "days_since_last_start": recent.get("days_since_last"),
            }
            fatigue = _compute_fatigue(merged)
            sides_out[side] = {
                "goalie": goalie_name,
                "team": (home_team if side == "home" else away_team),
                **fatigue,
            }

        # Cross-side leans
        leans: List[str] = []
        for side in ("home", "away"):
            s = sides_out.get(side)
            if not s: continue
            opp_team = away_team if side == "home" else home_team
            if s["tier"] == "GASSED":
                leans.append(f"{opp_team}_GOALS_OVER_AGGRESSIVE (vs gassed {s['goalie']})")
            elif s["tier"] == "TIRED":
                leans.append(f"{opp_team}_GOALS_OVER_LEAN (vs tired {s['goalie']})")
            elif s["tier"] == "FRESH":
                leans.append(f"{opp_team}_GOALS_UNDER_LEAN (vs fresh {s['goalie']})")

        out_games.append({
            "matchup": matchup,
            "home_goalie": sides_out.get("home"),
            "away_goalie": sides_out.get("away"),
            "leans": leans,
        })

    n_gassed = sum(1 for g in out_games for s in ("home_goalie", "away_goalie")
                   if (g.get(s) or {}).get("tier") == "GASSED")
    n_tired = sum(1 for g in out_games for s in ("home_goalie", "away_goalie")
                  if (g.get(s) or {}).get("tier") == "TIRED")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_gassed_goalies": n_gassed,
        "n_tired_goalies": n_tired,
        "method_note": "Goalie fatigue = 30 baseline + starts_5d_above_2*18 + "
                       "saves_5d_above_70*0.6 + b2b*22 - rest_bonus*6. "
                       "Drives opp GOALS_OVER leans and goalie_SAVES_UNDER.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goalie-fatigue] {o['n_games']} games, {o['n_gassed_goalies']} gassed, "
          f"{o['n_tired_goalies']} tired -> {OUT}")
