"""
EdgeStat -- NHL team explosion alerts.

NHL analog to nba_team_explosion_alerts. Surfaces teams projecting for
a high-scoring outburst:
  - TT_OVER (team total STRONG_OVER lean from nhl_team_total_edge)
  - 4PLUS_GOALS_YES (p_4plus >= 35%)
  - OPP_GOALIE_FATIGUED (opp goalie fatigue flag)
  - SOG_VOLUME (game total SOG OVER lean)
  - PERIOD_OVER (period totals lean OVER)
  - PUCK_LINE_FAVORED (covering puck line -1.5)

EXPLOSION_ELITE = 5+ signals; STRONG = 3-4.

Output: data/nhl_team_explosion_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_explosion_alerts.json")


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
    tt_edge = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    four_plus = _load(os.path.join(DATA_DIR, "nhl_team_4plus_goals.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))
    sog_total = _load(os.path.join(DATA_DIR, "nhl_game_total_sog.json"))
    period_total = _load(os.path.join(DATA_DIR, "nhl_period_totals_props.json"))
    puck_line = _load(os.path.join(DATA_DIR, "nhl_puck_line_props.json"))

    # 4+ goals YES by (matchup, side)
    four_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (four_plus.get(k) or []):
            if not isinstance(r, dict): continue
            key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
            p_4 = _safe(r.get("p_4plus") or r.get("p"))
            if key not in four_idx or p_4 > four_idx[key]:
                four_idx[key] = p_4

    # Goalie fatigue by team (the OPP team in matchup)
    fatigue_by_team: Dict[str, str] = {}
    for r in (fatigue.get("rows") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("flag") or "").upper()
        if status in ("FATIGUED", "TIRED", "BACK_TO_BACK"):
            fatigue_by_team[team] = status

    # SOG total OVER by matchup
    sog_over: Dict[str, bool] = {}
    for r in (sog_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            sog_over[r.get("matchup", "")] = True

    # Period totals OVER by matchup
    period_over: Dict[str, bool] = {}
    for r in (period_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            period_over[r.get("matchup", "")] = True

    # Puck line favored (covering -1.5)
    pl_fav: Dict[str, str] = {}  # matchup -> team covering
    for k in ("rows", "strong_edges"):
        for r in (puck_line.get(k) or []):
            if not isinstance(r, dict): continue
            p_cover = _safe(r.get("p_cover") or r.get("p_minus_1_5"))
            if p_cover >= 0.45:
                pl_fav[r.get("matchup", "")] = r.get("team", "")

    # Build alerts
    alerts: List[Dict[str, Any]] = []
    seen: set = set()
    for r in (tt_edge.get("rows") or []):
        if not isinstance(r, dict): continue
        matchup = r.get("matchup", "")
        side = (r.get("side", "") or "").upper()
        team = r.get("team", "")
        if not matchup or not side: continue
        key = f"{matchup}|{side}|{team}"
        if key in seen: continue
        seen.add(key)

        signals: Dict[str, int] = {}

        # TT direction
        tt_dir = (r.get("direction") or "").upper()
        signals["TT_OVER"] = 1 if tt_dir in ("STRONG_OVER", "LEAN_OVER") else 0

        # 4+ goals
        p_4 = four_idx.get(key, 0)
        signals["4PLUS_GOALS_YES"] = 1 if p_4 >= 0.35 else 0

        # Opp goalie fatigued
        # Side OPPOSITE of current team
        opp_side = "AWAY" if side == "HOME" else "HOME"
        opp_team = (r.get("opp_team") or "").upper()
        signals["OPP_GOALIE_FATIGUED"] = 1 if opp_team in fatigue_by_team else 0

        # SOG volume
        signals["SOG_VOLUME"] = 1 if sog_over.get(matchup) else 0

        # Period over
        signals["PERIOD_OVER"] = 1 if period_over.get(matchup) else 0

        # Puck line favored
        signals["PUCK_LINE_FAVORED"] = 1 if pl_fav.get(matchup) == team else 0

        positive_count = sum(1 for v in signals.values() if v == 1)
        if positive_count < 3: continue

        tier = "EXPLOSION_ELITE" if positive_count >= 5 else "EXPLOSION_STRONG"

        alerts.append({
            "matchup": matchup,
            "team": team,
            "side": side,
            "tt_direction": tt_dir,
            "p_4plus_goals": round(p_4, 3),
            "opp_team": opp_team or None,
            "opp_goalie_fatigue": fatigue_by_team.get(opp_team) or None,
            "n_positive_signals": positive_count,
            "signals": signals,
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "EXPLOSION_ELITE"),
        "method_note": "NHL team-level explosion alerts. 3+ aligned signals: "
                       "TT_OVER, 4PLUS_GOALS_YES (>=35%), OPP_GOALIE_FATIGUED, "
                       "SOG_VOLUME, PERIOD_OVER, PUCK_LINE_FAVORED. "
                       "EXPLOSION_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_explosions": [a for a in alerts if a["tier"] == "EXPLOSION_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-team-explosion] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
