"""
EdgeStat -- MLB bullpen fatigue index.

For each game on tonight's slate, computes a 0-100 fatigue index per
bullpen based on:
  - Total bullpen appearances over last 3 days
  - Total bullpen IP over last 3 days
  - Number of relievers who threw 25+ pitches in last 24 hours
  - Closer availability (was the closer used yesterday?)

Tier:
  0-25:    FRESH       — Bullpen rested, bias UNDER on innings 7-9 total
  25-50:   NORMAL      — No directional bias
  50-70:   TIRED       — Lean OVER on innings 7-9, opp team total OVER late
  70-100:  GASSED      — Aggressive OVER on late-inning totals; closer often
                          unavailable, leading to blown-save risk

Consumed by:
  - mlb_innings_7_9_totals (late-game adjustment)
  - mlb_pitcher_outs_props (if starter goes 6+, bullpen carries less weight)
  - mlb_team_total_edge (opposing team OVER bias if facing tired pen)

Output: data/mlb_bullpen_fatigue_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json")


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


def _compute_fatigue(team_abbr: str, pen_logs: Dict[str, Any]) -> Dict[str, Any]:
    """Compute fatigue from team bullpen recent-usage logs.

    Falls back gracefully to NORMAL (35) when logs unavailable.
    """
    team_pen = pen_logs.get(team_abbr) or pen_logs.get((team_abbr or "").upper()) or {}
    appearances_3d = int(_safe(team_pen.get("appearances_last_3d"), 12))  # league avg ~12
    pen_ip_3d = _safe(team_pen.get("pen_ip_last_3d"), 9.0)  # ~9 IP league avg
    pitchers_25plus_24h = int(_safe(team_pen.get("pitchers_25plus_last_24h"), 0))
    closer_used_yesterday = bool(team_pen.get("closer_used_yesterday", False))

    # Score components
    score = 35.0  # NORMAL baseline
    # Appearances: above 14 in 3 days = tired
    score += max(0, (appearances_3d - 12)) * 4
    # Pen IP: above 11 IP = tired
    score += max(0, (pen_ip_3d - 9)) * 3
    # 25+pitch outings hurt more
    score += pitchers_25plus_24h * 8
    # Closer unavailable
    if closer_used_yesterday: score += 12

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "tier": _tier(score),
        "appearances_3d": appearances_3d,
        "pen_ip_3d": round(pen_ip_3d, 1),
        "pitchers_25plus_24h": pitchers_25plus_24h,
        "closer_used_yesterday": closer_used_yesterday,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    # Pull per-team bullpen usage from pitcher_logs if available
    pen_logs: Dict[str, Any] = {}
    for p in (pitcher_logs.get("pitchers") or []):
        team = (p.get("team_abbr") or "").upper()
        if not team: continue
        # Aggregate: count appearances in last 3 days from per-pitcher logs
        # Bullpen pitchers identified by role flag or last_role
        role = (p.get("role") or "").lower()
        if "starter" in role or "sp" in role: continue
        # Simple aggregation
        team_entry = pen_logs.setdefault(team, {
            "appearances_last_3d": 0,
            "pen_ip_last_3d": 0.0,
            "pitchers_25plus_last_24h": 0,
        })
        recent = p.get("recent") or {}
        team_entry["appearances_last_3d"] += int(_safe(recent.get("games_l3"), 0))
        team_entry["pen_ip_last_3d"] += _safe(recent.get("ip_l3"), 0.0)
        if _safe(recent.get("pitches_l24h"), 0) >= 25:
            team_entry["pitchers_25plus_last_24h"] += 1

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        home_team = ((g.get("home") or {}) if isinstance(g.get("home"), dict) else {}).get("team") or g.get("home_team")
        away_team = ((g.get("away") or {}) if isinstance(g.get("away"), dict) else {}).get("team") or g.get("away_team")
        # Fallback: parse from matchup string "AWAY @ HOME"
        if not home_team or not away_team:
            parts = matchup.split("@")
            if len(parts) == 2:
                away_team = away_team or parts[0].strip()
                home_team = home_team or parts[1].strip()

        home_fatigue = _compute_fatigue(home_team, pen_logs)
        away_fatigue = _compute_fatigue(away_team, pen_logs)

        # Recommend leans
        leans: List[str] = []
        if home_fatigue["tier"] in ("TIRED", "GASSED"):
            leans.append(f"AWAY_TT_OVER_LATE (home pen {home_fatigue['tier'].lower()})")
        if away_fatigue["tier"] in ("TIRED", "GASSED"):
            leans.append(f"HOME_TT_OVER_LATE (away pen {away_fatigue['tier'].lower()})")
        if home_fatigue["tier"] == "FRESH" and away_fatigue["tier"] == "FRESH":
            leans.append("INNINGS_7_9_UNDER")

        out_games.append({
            "matchup": matchup,
            "home_team": home_team,
            "away_team": away_team,
            "home_pen": home_fatigue,
            "away_pen": away_fatigue,
            "leans": leans,
        })

    n_gassed = sum(1 for g in out_games for side in ("home_pen", "away_pen")
                   if g[side]["tier"] == "GASSED")
    n_tired = sum(1 for g in out_games for side in ("home_pen", "away_pen")
                  if g[side]["tier"] == "TIRED")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_gassed_bullpens": n_gassed,
        "n_tired_bullpens": n_tired,
        "method_note": "Fatigue = 35 baseline + appearances_3d_above_12*4 + "
                       "ip_3d_above_9*3 + 25pitch_24h*8 + closer_used_yesterday*12. "
                       "GASSED 70+ / TIRED 50-70 / NORMAL 25-50 / FRESH <25. "
                       "Drives late-innings OVER and opp team total OVER leans.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bp-fatigue] {o['n_games']} games, {o['n_gassed_bullpens']} gassed, "
          f"{o['n_tired_bullpens']} tired -> {OUT}")
