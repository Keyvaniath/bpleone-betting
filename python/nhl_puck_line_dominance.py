"""
EdgeStat -- NHL puck line dominance alerts.

NHL counterpart to mlb_run_line_dominance. Surfaces puck line favorites
(-1.5) with multiple positive signals to cover:
  - Goalie LOCK or STRONG
  - Opp team total UNDER
  - Puck line cover probability >= 42%
  - Team confluence STRONG+
  - Opp goalie fatigued

When 3+ signals align, recommend PL -1.5.

Output: data/nhl_puck_line_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_puck_line_dominance.json")


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


def run() -> Dict[str, Any]:
    goalie = _load(os.path.join(DATA_DIR, "nhl_goalie_confluence_score.json"))
    team = _load(os.path.join(DATA_DIR, "nhl_team_confluence_score.json"))
    puck_line = _load(os.path.join(DATA_DIR, "nhl_puck_line_props.json"))
    team_total = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))

    # Goalie by team
    goalie_by_team: Dict[str, Dict[str, Any]] = {}
    for r in (goalie.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        goalie_by_team[key] = r

    # Team confluence
    team_idx: Dict[str, Dict[str, Any]] = {}
    for r in (team.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        team_idx[key] = r

    # Puck line cover by (matchup, team)
    pl_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (puck_line.get(k) or []):
            if isinstance(r, dict):
                key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
                p_cover = _safe(r.get("p_cover") or r.get("p_minus_1_5"))
                if key not in pl_idx or p_cover > pl_idx[key]:
                    pl_idx[key] = p_cover

    # Opp team total UNDER
    tt_under_idx: Dict[str, bool] = {}
    for r in (team_total.get("rows") or []):
        if not isinstance(r, dict): continue
        dir = (r.get("direction") or "").upper()
        if "UNDER" in dir:
            key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
            tt_under_idx[key] = True

    # Fatigued teams
    fatigued_teams: set = set()
    for r in (fatigue.get("rows") or []):
        if not isinstance(r, dict): continue
        team_name = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("flag") or "").upper()
        if status in ("FATIGUED", "TIRED", "BACK_TO_BACK"):
            fatigued_teams.add(team_name)

    alerts: List[Dict[str, Any]] = []
    for key, g_row in goalie_by_team.items():
        matchup, team_name = (key.split("|", 1) + [""])[:2]
        if not team_name: continue

        goalie_tier = g_row.get("tier") or ""
        if "LOCK" not in goalie_tier and "STRONG" not in goalie_tier: continue

        # Side
        side = ""
        for s in ("HOME", "AWAY"):
            t_data = team_idx.get(f"{matchup}|{s}", {})
            if (t_data.get("team") or "").upper() == team_name:
                side = s
                break
        if not side: continue
        opp_side = "AWAY" if side == "HOME" else "HOME"

        # Opp team
        opp_t_data = team_idx.get(f"{matchup}|{opp_side}", {})
        opp_team = (opp_t_data.get("team") or "").upper()

        # Signals
        signals: Dict[str, int] = {}
        signals["GOALIE_LOCK_OR_STRONG"] = 1
        signals["OPP_TT_UNDER"] = 1 if tt_under_idx.get(f"{matchup}|{opp_side}") else 0

        pl_p = pl_idx.get(key, 0)
        signals["PL_COVER_LIVE"] = 1 if pl_p >= 0.42 else 0

        team_data = team_idx.get(f"{matchup}|{side}", {})
        team_tier = team_data.get("tier") or ""
        signals["TEAM_STRONG_OR_LOCK"] = 1 if "LOCK" in team_tier or "STRONG" in team_tier else 0

        signals["OPP_GOALIE_FATIGUED"] = 1 if opp_team in fatigued_teams else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "PL_LOCK"
        else:
            tier = "PL_STRONG"

        alerts.append({
            "matchup": matchup,
            "team": team_name,
            "side": side,
            "goalie": g_row.get("goalie"),
            "goalie_tier": goalie_tier,
            "opp_team": opp_team or None,
            "p_pl_cover": round(pl_p, 3),
            "opp_tt_under": tt_under_idx.get(f"{matchup}|{opp_side}", False),
            "team_confluence_tier": team_tier or None,
            "opp_goalie_fatigued": opp_team in fatigued_teams,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_market": f"{team_name} -1.5 puck line",
        })

    alerts.sort(key=lambda a: (-a["n_positive_signals"], -a["p_pl_cover"]))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_pl_lock": sum(1 for a in alerts if a["tier"] == "PL_LOCK"),
        "n_pl_strong": sum(1 for a in alerts if a["tier"] == "PL_STRONG"),
        "method_note": "NHL puck line dominance. 3+ signals from "
                       "GOALIE_LOCK_OR_STRONG + OPP_TT_UNDER + PL_COVER_LIVE "
                       "(>=42%) + TEAM_STRONG_OR_LOCK + OPP_GOALIE_FATIGUED. "
                       "PL_LOCK = 4+ signals; STRONG = 3.",
        "alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-pl] {o['n_alerts']} alerts ({o['n_pl_lock']} LOCK, "
          f"{o['n_pl_strong']} STRONG) -> {OUT}")
