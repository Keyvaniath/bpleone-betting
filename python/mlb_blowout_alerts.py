"""
EdgeStat -- MLB blowout alerts.

Surfaces games projected for 5+ run differential (one-sided blowouts):
  - Run line favorite cover probability >= 50%
  - Run line dominance LOCK/STRONG
  - Pitcher LOCK on favorite side
  - Opp lineup_score <= 35
  - Team confluence STRONG+ on favorite

Output: data/mlb_blowout_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_blowout_alerts.json")


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
    run_line = _load(os.path.join(DATA_DIR, "mlb_run_line_props.json"))
    rl_dom = _load(os.path.join(DATA_DIR, "mlb_run_line_dominance.json"))
    pitcher = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    team = _load(os.path.join(DATA_DIR, "mlb_team_confluence_score.json"))
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    diff = _load(os.path.join(DATA_DIR, "mlb_game_run_diff_props.json"))

    rl_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (run_line.get(k) or []):
            if isinstance(r, dict):
                key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
                p_cover = _safe(r.get("p_cover") or r.get("p_minus_1_5"))
                if key not in rl_idx or p_cover > rl_idx[key]:
                    rl_idx[key] = p_cover

    rl_dom_set: set = set()
    for a in (rl_dom.get("alerts") or rl_dom.get("rl_locks") or []):
        if isinstance(a, dict):
            rl_dom_set.add(f"{a.get('matchup','')}|{(a.get('team','') or '').upper()}")

    pitcher_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        pitcher_idx[key] = r

    team_idx: Dict[str, Dict[str, Any]] = {}
    for r in (team.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        team_idx[key] = r

    opp_lq_by_matchup_side: Dict[str, float] = {}
    for g in (lq.get("games") or []):
        m = g.get("matchup") or ""
        for side in ("home", "away"):
            sd = g.get(side) or {}
            opp_lq_by_matchup_side[f"{m}|{side.upper()}"] = _safe(sd.get("score"))

    diff_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (diff.get(k) or []):
            if isinstance(r, dict):
                key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
                p_5plus = _safe(r.get("p_5plus_diff") or r.get("p"))
                if key not in diff_idx or p_5plus > diff_idx[key]:
                    diff_idx[key] = p_5plus

    alerts: List[Dict[str, Any]] = []
    for key, p_cover in rl_idx.items():
        if p_cover < 0.50: continue

        matchup, team_name = (key.split("|", 1) + [""])[:2]
        pitcher_data = pitcher_idx.get(key, {})
        pitcher_tier = pitcher_data.get("tier") or ""

        # Find side
        side = ""
        for s in ("HOME", "AWAY"):
            t_data = team_idx.get(f"{matchup}|{s}", {})
            if (t_data.get("team") or "").upper() == team_name:
                side = s
                break

        opp_side = "AWAY" if side == "HOME" else ("HOME" if side == "AWAY" else "")
        opp_lq = opp_lq_by_matchup_side.get(f"{matchup}|{opp_side}", 50)
        team_data = team_idx.get(f"{matchup}|{side}", {}) if side else {}
        team_tier = team_data.get("tier") or ""

        signals: Dict[str, int] = {}
        signals["RL_COVER_LIVE"] = 1 if p_cover >= 0.50 else 0
        signals["RL_DOM_LOCK"] = 1 if key in rl_dom_set else 0
        signals["PITCHER_LOCK"] = 1 if "LOCK" in pitcher_tier else 0
        signals["WEAK_OPP_LINEUP"] = 1 if 0 < opp_lq <= 35 else 0
        signals["TEAM_STRONG_OR_LOCK"] = 1 if "LOCK" in team_tier or "STRONG" in team_tier else 0
        signals["RUN_DIFF_5PLUS_LIVE"] = 1 if diff_idx.get(key, 0) >= 0.30 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 5:
            tier = "BLOWOUT_LOCK"
        else:
            tier = "BLOWOUT_LEAN"

        alerts.append({
            "matchup": matchup,
            "team": team_name,
            "side": side,
            "pitcher": pitcher_data.get("pitcher"),
            "pitcher_tier": pitcher_tier or None,
            "p_rl_cover": round(p_cover, 3),
            "opp_lineup_score": opp_lq,
            "team_confluence_tier": team_tier or None,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                f"{team_name} -1.5 run line",
                f"{team_name} ML",
                f"{team_name} team total OVER",
                "Run diff 5+ YES (long shot)",
            ],
        })

    alerts.sort(key=lambda a: (-a["n_positive_signals"], -a["p_rl_cover"]))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_blowout_lock": sum(1 for a in alerts if a["tier"] == "BLOWOUT_LOCK"),
        "method_note": "MLB blowout alerts. 3+ signals: RL_COVER_LIVE (>=50%), "
                       "RL_DOM_LOCK, PITCHER_LOCK, WEAK_OPP_LINEUP (<=35), "
                       "TEAM_STRONG_OR_LOCK, RUN_DIFF_5PLUS_LIVE (>=30%). "
                       "BLOWOUT_LOCK = 5+; BLOWOUT_LEAN = 3-4.",
        "alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-blowout] {o['n_alerts']} alerts ({o['n_blowout_lock']} LOCK) -> {OUT}")
