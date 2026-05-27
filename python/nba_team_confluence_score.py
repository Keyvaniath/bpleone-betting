"""
EdgeStat -- NBA team confluence score.

Composite per-team score combining team-level synthesizers:
  - nba_team_total_edge (team total direction)
  - nba_team_explosion_alerts (n_positive_signals)
  - nba_pace_adjusted (projected pace)
  - nba_race_to_points (race favorite lean)
  - nba_half_total_props (half total OVER lean)

Score formula:
  score = explosion_signals * 3 + tt_over_strength + pace_lean
        + race_lean + half_over_bonus

TEAM_LOCK = score >= 16 with explosion_signals >= 4;
TEAM_STRONG = 10-15 with tt OVER or explosion >= 2;
TEAM_FADE = score <= 2 or strong tt UNDER.

Output: data/nba_team_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_confluence_score.json")

LEAGUE_PACE = 100.0


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


def _key(matchup: str, side: str) -> str:
    return f"{matchup or ''}|{(side or '').upper()}"


def run() -> Dict[str, Any]:
    tt = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))
    expl = _load(os.path.join(DATA_DIR, "nba_team_explosion_alerts.json"))
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))
    race = _load(os.path.join(DATA_DIR, "nba_race_to_points.json"))
    half = _load(os.path.join(DATA_DIR, "nba_half_total_props.json"))

    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt.get("rows") or []):
        if not isinstance(r, dict): continue
        tt_idx[_key(r.get("matchup"), r.get("side"))] = r

    expl_idx: Dict[str, Dict[str, Any]] = {}
    for a in (expl.get("alerts") or []):
        if not isinstance(a, dict): continue
        expl_idx[_key(a.get("matchup"), a.get("side"))] = a

    pace_idx: Dict[str, float] = {}
    for g in (pace.get("games") or pace.get("rows") or []):
        if not isinstance(g, dict): continue
        pace_idx[g.get("matchup", "")] = _safe(
            g.get("projected_pace") or g.get("pace"), LEAGUE_PACE)

    race_fav: Dict[str, Dict[str, float]] = {}
    for r in (race.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup", "")
        team = r.get("team", "")
        p = _safe(r.get("p"))
        existing = race_fav.get(m)
        if not existing or p > existing.get("p", 0):
            race_fav[m] = {"team": team, "p": p}

    half_over: Dict[str, bool] = {}
    for r in (half.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            half_over[r.get("matchup", "")] = True

    all_keys = set(tt_idx) | set(expl_idx)

    rows: List[Dict[str, Any]] = []
    for k in all_keys:
        matchup, side = (k.split("|", 1) + [""])[:2]
        ttr = tt_idx.get(k, {})
        exr = expl_idx.get(k, {})
        team = ttr.get("team") or exr.get("team", "")

        explosion_signals = int(exr.get("n_positive_signals", 0) or 0)
        tt_dir = (ttr.get("direction") or "").upper()
        tt_over_strength = 0
        if tt_dir == "STRONG_OVER": tt_over_strength = 4
        elif tt_dir == "LEAN_OVER": tt_over_strength = 2
        elif tt_dir == "LEAN_UNDER": tt_over_strength = -2
        elif tt_dir == "STRONG_UNDER": tt_over_strength = -4

        proj_pace = pace_idx.get(matchup, LEAGUE_PACE)
        pace_lean = (proj_pace - LEAGUE_PACE) / 2  # +1 per 2 pace above league

        race_fav_for_team = race_fav.get(matchup, {})
        race_lean = 4 if race_fav_for_team.get("team") == team else 0

        half_over_bonus = 2 if half_over.get(matchup) else 0

        score = (explosion_signals * 3
                 + tt_over_strength
                 + pace_lean
                 + race_lean
                 + half_over_bonus)

        if score >= 16 and explosion_signals >= 4:
            tier = "TEAM_LOCK"
        elif score >= 10 and (tt_over_strength >= 2 or explosion_signals >= 2):
            tier = "TEAM_STRONG"
        elif score <= 2 or tt_over_strength <= -3:
            tier = "TEAM_FADE"
        else:
            tier = "TEAM_NEUTRAL"

        rows.append({
            "matchup": matchup,
            "side": side,
            "team": team,
            "explosion_signals": explosion_signals,
            "tt_direction": tt_dir or None,
            "projected_pace": round(proj_pace, 1),
            "race_favorite": race_fav_for_team.get("team") == team,
            "half_over": half_over.get(matchup, False),
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_teams": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "TEAM_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "TEAM_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "TEAM_FADE"),
        "method_note": "Composite NBA team score. explosion_signals*3 + "
                       "tt_over_strength + pace_lean + race_lean + half_over_bonus. "
                       "LOCK >= 16 with explosion>=4; STRONG 10-15 with tt OVER or "
                       "explosion>=2; FADE = score <=2 or strong tt UNDER.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "TEAM_LOCK"],
        "fades": [r for r in rows if r["tier"] == "TEAM_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-team-confluence] {o['n_teams']} teams "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
