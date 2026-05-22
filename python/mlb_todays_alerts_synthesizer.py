"""
EdgeStat -- MLB Today's Alerts Synthesizer.

Aggregates ALL the per-game MLB context features into a single ranked alerts
feed, designed to be the "what should I bet tonight" digest:

Pulls from:
  - mlb_lineup_quality_index.json (lineup elite / bottom flags)
  - mlb_pitcher_edge_composite.json (elite_matchups / bad_spots)
  - mlb_bullpen_fatigue_index.json (gassed bullpens)
  - mlb_starter_pitch_count_alerts.json (RED / EMERGENCY starters)
  - mlb_park_weather_hr_index.json (HOMER_FRIENDLY / GRAVEYARD parks)
  - mlb_team_total_edge.json (STRONG_OVER / STRONG_UNDER team totals)
  - mlb_team_first_inning_run.json (STRONG_YES / STRONG_NO 1st-inning)
  - hot_streaks.json (hot/cold flags)

Output:
  - alerts: scored list of single-line actionable signals per game
  - top_5_action: highest-conviction picks for the bet slate

Output: data/mlb_todays_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_todays_alerts.json")


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
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    bp_fatigue = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    pitch_alerts = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    first_inn = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))

    alerts: List[Dict[str, Any]] = []

    # 1) Lineup tier alerts
    for g in (lineup_q.get("games") or []):
        m = g.get("matchup") or ""
        for side in ("home", "away"):
            s = g.get(side) or {}
            tier = s.get("tier")
            if tier == "elite":
                alerts.append({
                    "matchup": m,
                    "category": "LINEUP_ELITE",
                    "side": side.upper(),
                    "team": s.get("team"),
                    "priority": 8,
                    "message": f"{s.get('team')} elite lineup ({s.get('score')}/100) - "
                               f"team total OVER + HR/TB stack candidates",
                })
            elif tier == "bottom_tier":
                alerts.append({
                    "matchup": m,
                    "category": "LINEUP_WEAK",
                    "side": side.upper(),
                    "team": s.get("team"),
                    "priority": 5,
                    "message": f"{s.get('team')} bottom-tier lineup ({s.get('score')}/100) - "
                               f"opposing pitcher K_OVER + team total UNDER",
                })

    # 2) Pitcher edge composites
    for r in (pitcher_edge.get("elite_matchups") or []):
        alerts.append({
            "matchup": r.get("matchup") or "",
            "category": "PITCHER_ELITE_MATCHUP",
            "side": r.get("side"),
            "pitcher": r.get("pitcher"),
            "priority": 9,
            "message": f"{r.get('pitcher')} ELITE_MATCHUP "
                       f"({r.get('edge_score')}/100): {', '.join(r.get('directional_lean') or [])}",
        })
    for r in (pitcher_edge.get("bad_spots") or []):
        alerts.append({
            "matchup": r.get("matchup") or "",
            "category": "PITCHER_BAD_SPOT",
            "side": r.get("side"),
            "pitcher": r.get("pitcher"),
            "priority": 8,
            "message": f"{r.get('pitcher')} BAD_SPOT "
                       f"({r.get('edge_score')}/100): {', '.join(r.get('directional_lean') or [])}",
        })

    # 3) Pitch count alerts
    for r in (pitch_alerts.get("rows") or []):
        if r.get("status") in ("RED", "EMERGENCY"):
            alerts.append({
                "matchup": r.get("matchup") or "",
                "category": f"PITCH_COUNT_{r.get('status')}",
                "side": r.get("side"),
                "pitcher": r.get("pitcher"),
                "priority": 9 if r.get("status") == "EMERGENCY" else 7,
                "message": f"{r.get('pitcher')} {r.get('status')} workload "
                           f"(last: {r.get('pitches_last_start')}p) - "
                           f"{', '.join(r.get('leans') or [])}",
            })

    # 4) Bullpen fatigue
    for g in (bp_fatigue.get("games") or []):
        for side_key in ("home_pen", "away_pen"):
            pen = g.get(side_key) or {}
            if pen.get("tier") == "GASSED":
                alerts.append({
                    "matchup": g.get("matchup") or "",
                    "category": "BULLPEN_GASSED",
                    "side": side_key.replace("_pen", "").upper(),
                    "priority": 8,
                    "message": f"{side_key.replace('_pen', '').upper()} pen GASSED "
                               f"({pen.get('score')}/100) - opp_TT_OVER_LATE + INNINGS_7_9_OVER",
                })
            elif pen.get("tier") == "TIRED":
                alerts.append({
                    "matchup": g.get("matchup") or "",
                    "category": "BULLPEN_TIRED",
                    "side": side_key.replace("_pen", "").upper(),
                    "priority": 6,
                    "message": f"{side_key.replace('_pen', '').upper()} pen TIRED - "
                               f"opp_TT_OVER_LATE_LEAN",
                })

    # 5) Park / weather HR environment
    for g in (park_hr.get("games") or []):
        tier = g.get("tier")
        if tier == "HOMER_FRIENDLY":
            alerts.append({
                "matchup": g.get("matchup") or "",
                "category": "PARK_HOMER_FRIENDLY",
                "priority": 7,
                "message": f"{g.get('park')} HOMER_FRIENDLY env "
                           f"(idx {g.get('composite_index')}) - all HR/TB props OVER",
            })
        elif tier == "PITCHER_GRAVEYARD":
            alerts.append({
                "matchup": g.get("matchup") or "",
                "category": "PARK_GRAVEYARD",
                "priority": 8,
                "message": f"{g.get('park')} PITCHER_GRAVEYARD env "
                           f"(idx {g.get('composite_index')}) - HR_UNDER + TT_UNDER + F5_UNDER",
            })

    # 6) Team total edges
    for r in (tt_edge.get("strong_edges") or []):
        direction = r.get("direction") or ""
        if direction.startswith("STRONG"):
            alerts.append({
                "matchup": r.get("matchup") or "",
                "category": direction,
                "side": r.get("side"),
                "team": r.get("team"),
                "priority": 9,
                "message": f"{r.get('team')} TEAM_TOTAL {direction} "
                           f"(model {r.get('model_expected_runs_anchored')} vs book {r.get('book_team_total')})",
            })

    # 7) First-inning score signals
    for r in (first_inn.get("strong_edges") or []):
        alerts.append({
            "matchup": r.get("matchup") or "",
            "category": r.get("edge_class"),
            "side": r.get("side"),
            "team": r.get("team"),
            "priority": 7,
            "message": f"{r.get('team')} 1ST_INN {r.get('edge_class')} "
                       f"(p={r.get('p_score')}, fair {r.get('fair_yes_odds')})",
        })

    # Sort by priority desc, group by matchup
    alerts.sort(key=lambda a: -a["priority"])
    top_5 = alerts[:5]

    # Group by matchup for the digest
    by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in alerts:
        m = a.get("matchup") or "GLOBAL"
        by_matchup.setdefault(m, []).append(a)

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts_total": len(alerts),
        "n_high_priority": sum(1 for a in alerts if a["priority"] >= 8),
        "top_5_action": top_5,
        "by_matchup": by_matchup,
        "method_note": "Synthesizes lineup_quality + pitcher_edge + bullpen_fatigue + "
                       "pitch_count + park/weather + team_total + first_inning into one "
                       "priority-ranked alerts feed. Priority 9=must-bet, 5=lean only.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-alerts] {o['n_alerts_total']} alerts, "
          f"{o['n_high_priority']} high-priority -> {OUT}")
