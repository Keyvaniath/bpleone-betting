"""
EdgeStat -- MLB run line dominance alerts.

Surfaces games where the run line favorite has multiple positive signals
to cover -1.5:
  - Favored pitcher LOCK or STRONG
  - Opp team total UNDER lean
  - Run line cover probability >= 45%
  - Favored team confluence STRONG+
  - Favored team is in HITTER_FRIENDLY park

When 3+ signals align on the same side, recommend RL -1.5.

Output: data/mlb_run_line_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_run_line_dominance.json")


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
    pitcher = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    team = _load(os.path.join(DATA_DIR, "mlb_team_confluence_score.json"))
    run_line = _load(os.path.join(DATA_DIR, "mlb_run_line_props.json"))
    team_total = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    park = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))

    # Pitcher confluence by (matchup, team)
    pitcher_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        pitcher_idx[key] = r

    # Team confluence by (matchup, side)
    team_idx: Dict[str, Dict[str, Any]] = {}
    for r in (team.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        team_idx[key] = r

    # Run line probabilities by (matchup, team)
    rl_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (run_line.get(k) or []):
            if isinstance(r, dict):
                key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
                p_cover = _safe(r.get("p_cover") or r.get("p_minus_1_5"))
                if key not in rl_idx or p_cover > rl_idx[key]:
                    rl_idx[key] = p_cover

    # Team total UNDER by (matchup, side) — for opp team
    tt_under_idx: Dict[str, bool] = {}
    for r in (team_total.get("rows") or []):
        if not isinstance(r, dict): continue
        dir = (r.get("direction") or "").upper()
        if "UNDER" in dir:
            key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
            tt_under_idx[key] = True

    # Park tiers
    park_by_matchup: Dict[str, str] = {}
    for g in (park.get("games") or []):
        if isinstance(g, dict):
            park_by_matchup[g.get("matchup", "")] = (g.get("tier") or "").upper()

    alerts: List[Dict[str, Any]] = []
    for key, p_row in pitcher_idx.items():
        matchup, team_name = (key.split("|", 1) + [""])[:2]
        if not team_name: continue

        pitcher_tier = p_row.get("tier") or ""
        if "LOCK" not in pitcher_tier and "STRONG" not in pitcher_tier: continue

        # Side
        side = ""
        for s in ("HOME", "AWAY"):
            t_data = team_idx.get(f"{matchup}|{s}", {})
            if (t_data.get("team") or "").upper() == team_name:
                side = s
                break
        if not side: continue
        opp_side = "AWAY" if side == "HOME" else "HOME"

        # Signals
        signals: Dict[str, int] = {}
        signals["PITCHER_LOCK_OR_STRONG"] = 1

        opp_tt_under = tt_under_idx.get(f"{matchup}|{opp_side}", False)
        signals["OPP_TT_UNDER"] = 1 if opp_tt_under else 0

        rl_p = rl_idx.get(key, 0)
        signals["RL_COVER_LIVE"] = 1 if rl_p >= 0.45 else 0

        team_data = team_idx.get(f"{matchup}|{side}", {})
        team_tier = team_data.get("tier") or ""
        signals["TEAM_STRONG_OR_LOCK"] = 1 if "LOCK" in team_tier or "STRONG" in team_tier else 0

        park_tier = park_by_matchup.get(matchup, "")
        signals["PARK_HITTER_FAV"] = 1 if park_tier in ("HITTER_FRIENDLY", "HOMER_FRIENDLY") else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "RL_LOCK"
        else:
            tier = "RL_STRONG"

        alerts.append({
            "matchup": matchup,
            "team": team_name,
            "side": side,
            "pitcher": p_row.get("pitcher"),
            "pitcher_tier": pitcher_tier,
            "p_rl_cover": round(rl_p, 3),
            "opp_tt_under": opp_tt_under,
            "team_confluence_tier": team_tier or None,
            "park_tier": park_tier or None,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_market": f"{team_name} -1.5 run line",
        })

    alerts.sort(key=lambda a: (-a["n_positive_signals"], -a["p_rl_cover"]))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_rl_lock": sum(1 for a in alerts if a["tier"] == "RL_LOCK"),
        "n_rl_strong": sum(1 for a in alerts if a["tier"] == "RL_STRONG"),
        "method_note": "Run line dominance. 3+ signals from PITCHER_LOCK_OR_STRONG "
                       "+ OPP_TT_UNDER + RL_COVER_LIVE (>=45%) + "
                       "TEAM_STRONG_OR_LOCK + PARK_HITTER_FAV. RL_LOCK = 4+ "
                       "signals; STRONG = 3.",
        "alerts": alerts,
        "rl_locks": [a for a in alerts if a["tier"] == "RL_LOCK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-rl] {o['n_alerts']} alerts ({o['n_rl_lock']} LOCK, "
          f"{o['n_rl_strong']} STRONG) -> {OUT}")
