"""
EdgeStat -- cross-sport heat / cold alert aggregator.

Pulls from team_form_<sport>.json + player_trends_<sport>.json and
flags actionable trends:

  TEAMS:
    - HOT: L10 win% >= 0.75 AND streak >= W3
    - COLD: L10 win% <= 0.30 AND streak >= L3
    - HIGH_OVER: over_pct >= 0.65 in L10
    - LOW_OVER:  over_pct <= 0.35 in L10

  PLAYERS:
    - HEATING_UP: L5 pts >= 1.15x L20 (already classified)
    - COOLING_DOWN: L5 pts <= 0.85x L20

Output: data/heat_cold_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "heat_cold_alerts.json")
TEAM_SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "cws"]
PLAYER_SPORTS = ["nba", "nhl"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    alerts: List[Dict[str, Any]] = []

    for sport in TEAM_SPORTS:
        tf = _load(os.path.join(DATA_DIR, f"team_form_{sport}.json"))
        teams = (tf.get("teams") or {})
        for name, t in teams.items():
            l10 = t.get("L10", {})
            wpct = l10.get("win_pct", 0)
            streak = t.get("current_streak", "")
            over_pct = t.get("over_pct", 0)
            if wpct >= 0.75 and streak.startswith("W") and int(streak[1:] or 0) >= 3:
                alerts.append({"type": "TEAM_HOT", "sport": sport, "team": name,
                                "detail": f"L10 {l10.get('record')} ({wpct*100:.0f}%), streak {streak}"})
            if wpct <= 0.30 and streak.startswith("L") and int(streak[1:] or 0) >= 3:
                alerts.append({"type": "TEAM_COLD", "sport": sport, "team": name,
                                "detail": f"L10 {l10.get('record')} ({wpct*100:.0f}%), streak {streak}"})
            if over_pct >= 0.65:
                alerts.append({"type": "TEAM_HIGH_OVER", "sport": sport, "team": name,
                                "detail": f"L10 over% {over_pct*100:.0f}%"})
            if over_pct <= 0.35 and l10.get("n", 0) >= 5:
                alerts.append({"type": "TEAM_LOW_OVER", "sport": sport, "team": name,
                                "detail": f"L10 over% {over_pct*100:.0f}%"})

    for sport in PLAYER_SPORTS:
        pt = _load(os.path.join(DATA_DIR, f"player_trends_{sport}.json"))
        for p in (pt.get("heating_up_top10") or []):
            alerts.append({
                "type": "PLAYER_HEATING_UP", "sport": sport,
                "player": p["name"], "team": p.get("team_abbr"),
                "detail": f"L5 {p.get('pts_l5')} vs L20 {p.get('pts_l20')} "
                           f"({p.get('pts_delta_pct'):+.0f}%)"
            })
        for p in (pt.get("cooling_down_top10") or []):
            alerts.append({
                "type": "PLAYER_COOLING_DOWN", "sport": sport,
                "player": p["name"], "team": p.get("team_abbr"),
                "detail": f"L5 {p.get('pts_l5')} vs L20 {p.get('pts_l20')} "
                           f"({p.get('pts_delta_pct'):+.0f}%)"
            })

    by_type = {}
    for a in alerts:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "by_type": by_type,
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Heat/Cold alerts: {p['n_alerts']} total")
    for t, n in p["by_type"].items():
        print(f"  {t}: {n}")
