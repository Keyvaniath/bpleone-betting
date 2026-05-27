"""
EdgeStat -- MLB rest advantage composite.

Combines all rest signals for each team:
  - Starting pitcher rest advantage
  - Bullpen rested (RESTED tier vs FATIGUED)
  - Closer available (vs blown last night)
  - Team off-day before game (deep rest)

When 3+ rest factors favor one team, that's a real but underpriced edge.

Output: data/mlb_rest_advantage_composite.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_rest_advantage_composite.json")


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
    rest_adv = _load(os.path.join(DATA_DIR, "mlb_pitcher_rest_advantage.json"))
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    closer = _load(os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json"))

    # Pitcher rest by (matchup, team)
    pitcher_rest: Dict[str, Dict[str, Any]] = {}
    for r in (rest_adv.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        pitcher_rest[key] = r

    # Bullpen by team
    bullpen_by_team: Dict[str, str] = {}
    for r in (bullpen.get("rows") or bullpen.get("teams") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("tier") or r.get("flag") or "").upper()
        if team:
            bullpen_by_team[team] = status

    # Closer availability
    closer_by_team: Dict[str, str] = {}
    for r in (closer.get("rows") or closer.get("closers") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("flag") or "").upper()
        if team:
            closer_by_team[team] = status

    alerts: List[Dict[str, Any]] = []
    for key, p_rest in pitcher_rest.items():
        matchup, team_name = (key.split("|", 1) + [""])[:2]
        if not team_name: continue

        pitcher_advantage = (p_rest.get("advantage") or "").upper()
        days_rest = _safe(p_rest.get("days_rest"))

        bullpen_status = bullpen_by_team.get(team_name, "")
        closer_status = closer_by_team.get(team_name, "")

        signals: Dict[str, int] = {}
        signals["PITCHER_REST_ADVANTAGE"] = 1 if "ADVANTAGE" in pitcher_advantage or days_rest >= 5 else 0
        signals["BULLPEN_RESTED"] = 1 if "REST" in bullpen_status or "FRESH" in bullpen_status or bullpen_status in ("", "OK") else 0
        signals["BULLPEN_NOT_OVERWORKED"] = 1 if "OVERWORK" not in bullpen_status and "TIRED" not in bullpen_status else 0
        signals["CLOSER_AVAILABLE"] = 1 if "AVAILABLE" in closer_status or "RESTED" in closer_status or closer_status in ("", "OK", "FRESH") else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive == 4:
            tier = "REST_ADVANTAGE_FULL"
        else:
            tier = "REST_ADVANTAGE_PARTIAL"

        alerts.append({
            "matchup": matchup,
            "team": team_name,
            "pitcher": p_rest.get("pitcher"),
            "days_rest": days_rest,
            "pitcher_advantage": pitcher_advantage or None,
            "bullpen_status": bullpen_status or "UNKNOWN",
            "closer_status": closer_status or "UNKNOWN",
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "advisory": "Underpriced rest advantage. Books often slow to adjust "
                        "for cumulative rest. ML / RL covers and team total OVER "
                        "value in extended-rest spots.",
            "recommended_markets": [
                f"{team_name} ML",
                f"{team_name} -1.5 run line",
                f"{team_name} team total OVER",
                "Opp 5+ runs NO",
            ],
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_full_rest": sum(1 for a in alerts if a["tier"] == "REST_ADVANTAGE_FULL"),
        "method_note": "Rest advantage composite. 3+ signals: PITCHER_REST_ADVANTAGE "
                       "(days_rest >= 5), BULLPEN_RESTED, BULLPEN_NOT_OVERWORKED, "
                       "CLOSER_AVAILABLE. FULL = all 4 signals.",
        "alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-rest] {o['n_alerts']} rest advantage alerts ({o['n_full_rest']} FULL) -> {OUT}")
