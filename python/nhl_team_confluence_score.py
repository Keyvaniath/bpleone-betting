"""
EdgeStat -- NHL team confluence score.

Composite per-team score combining team-level synthesizers:
  - nhl_team_total_edge (team total direction)
  - nhl_team_explosion_alerts (n_positive_signals)
  - nhl_team_4plus_goals (p_4plus)
  - nhl_goalie_fatigue_index (opp goalie fatigued = team boost)
  - nhl_puck_line_props (run line covering favorite)

Score formula:
  score = explosion_signals * 3 + tt_over_strength + p_4plus * 20
        + opp_fatigue_bonus + puck_line_lean

TEAM_LOCK = score >= 16 with explosion >= 4
TEAM_STRONG = 10-15 with tt OVER or explosion >= 2
TEAM_FADE = score <= 2 or strong tt UNDER

Output: data/nhl_team_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_confluence_score.json")


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
    tt = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    expl = _load(os.path.join(DATA_DIR, "nhl_team_explosion_alerts.json"))
    four_plus = _load(os.path.join(DATA_DIR, "nhl_team_4plus_goals.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))
    puck_line = _load(os.path.join(DATA_DIR, "nhl_puck_line_props.json"))

    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt.get("rows") or []):
        if not isinstance(r, dict): continue
        tt_idx[_key(r.get("matchup"), r.get("side"))] = r

    expl_idx: Dict[str, Dict[str, Any]] = {}
    for a in (expl.get("alerts") or []):
        if not isinstance(a, dict): continue
        expl_idx[_key(a.get("matchup"), a.get("side"))] = a

    four_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (four_plus.get(k) or []):
            if isinstance(r, dict):
                key = _key(r.get("matchup"), r.get("side"))
                p_4 = _safe(r.get("p_4plus") or r.get("p"))
                if key not in four_idx or p_4 > four_idx[key]:
                    four_idx[key] = p_4

    fatigued_teams: set = set()
    for r in (fatigue.get("rows") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("flag") or "").upper()
        if status in ("FATIGUED", "TIRED", "BACK_TO_BACK"):
            fatigued_teams.add(team)

    puck_cover: Dict[str, Dict[str, float]] = {}
    for k in ("rows", "strong_edges"):
        for r in (puck_line.get(k) or []):
            if isinstance(r, dict):
                m = r.get("matchup", "")
                p_cover = _safe(r.get("p_cover"))
                if p_cover >= 0.45:
                    puck_cover[m] = {"team": r.get("team", ""), "p": p_cover}

    all_keys = set(tt_idx) | set(expl_idx)

    rows: List[Dict[str, Any]] = []
    for k in all_keys:
        matchup, side = (k.split("|", 1) + [""])[:2]
        ttr = tt_idx.get(k, {})
        exr = expl_idx.get(k, {})
        team = ttr.get("team") or exr.get("team", "")
        opp_team = (ttr.get("opp_team") or exr.get("opp_team") or "").upper()

        explosion_signals = int(exr.get("n_positive_signals", 0) or 0)
        tt_dir = (ttr.get("direction") or "").upper()
        tt_over_strength = 0
        if tt_dir == "STRONG_OVER": tt_over_strength = 4
        elif tt_dir == "LEAN_OVER": tt_over_strength = 2
        elif tt_dir == "LEAN_UNDER": tt_over_strength = -2
        elif tt_dir == "STRONG_UNDER": tt_over_strength = -4

        p_4 = four_idx.get(k, 0)
        opp_fatigue_bonus = 3 if opp_team in fatigued_teams else 0
        pl_lean = puck_cover.get(matchup, {})
        puck_line_lean = 2 if pl_lean.get("team") == team else 0

        score = (explosion_signals * 3
                 + tt_over_strength
                 + p_4 * 20
                 + opp_fatigue_bonus
                 + puck_line_lean)

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
            "opp_team": opp_team or None,
            "explosion_signals": explosion_signals,
            "tt_direction": tt_dir or None,
            "p_4plus_goals": round(p_4, 3),
            "opp_goalie_fatigued": opp_team in fatigued_teams,
            "puck_line_covering": pl_lean.get("team") == team,
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
        "method_note": "Composite NHL team score. explosion_signals*3 + "
                       "tt_over_strength + p_4plus*20 + opp_fatigue_bonus(3) + "
                       "puck_line_lean(2). LOCK >= 16 with explosion>=4; "
                       "STRONG 10-15 with tt OVER or explosion>=2.",
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
    print(f"[nhl-team-confluence] {o['n_teams']} teams "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
