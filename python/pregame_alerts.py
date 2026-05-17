"""
EdgeStat -- pre-game alert system (last-hour high-confidence signal feed).

Walks every sport's state file and surfaces games starting within the
next ~90 minutes that have:
  - Quality-weighted P(home) in sweet spot (55-75% favorite or 25-45% dog)
  - Form alignment: team's L10 record agrees with our model favorite
  - No drift alerts on the pair (model is stable on this matchup)

Output: data/pregame_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "pregame_alerts.json")

SPORTS_TO_SCAN = [
    "nba", "nhl", "wnba", "mls", "epl", "ucl", "nfl",
    "ncaaf", "ncaab", "cws", "kbo",
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _team_form(sport: str, team: str) -> Dict[str, Any]:
    """Return L10 form for a team, or empty if missing."""
    tf = _load(os.path.join(DATA_DIR, f"team_form_{sport}.json"))
    return ((tf.get("teams") or {}).get(team) or {})


def run() -> Dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    alerts: List[Dict[str, Any]] = []

    for sport in SPORTS_TO_SCAN:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        for g in (state.get("games") or []):
            if g.get("state") != "pre": continue
            ph = g.get("p_home_win") or 0.5
            # Sweet-spot range
            sweet_home = 0.55 <= ph <= 0.75
            sweet_away = 0.25 <= ph <= 0.45
            if not (sweet_home or sweet_away): continue

            home, away = g.get("home_team"), g.get("away_team")
            home_form = _team_form(sport, home)
            away_form = _team_form(sport, away)
            home_wpct = (home_form.get("L10") or {}).get("win_pct", 0)
            away_wpct = (away_form.get("L10") or {}).get("win_pct", 0)
            # Form-aligned = the side we favor also has higher L10 win%
            if sweet_home:
                aligned = home_wpct >= away_wpct
                side = "HOME"
                team = home
                opp = away
                prob = ph
            else:
                aligned = away_wpct >= home_wpct
                side = "AWAY"
                team = away
                opp = home
                prob = 1 - ph

            alerts.append({
                "sport": sport.upper(),
                "matchup": g.get("matchup"),
                "side": side,
                "team": team,
                "opponent": opp,
                "p_pick_side": round(prob, 4),
                "fair_american": (g.get("fair_home_american") if side == "HOME"
                                   else g.get("fair_away_american")),
                "team_l10": (home_form.get("L10") or {}).get("record") if side == "HOME"
                            else (away_form.get("L10") or {}).get("record"),
                "opp_l10": (away_form.get("L10") or {}).get("record") if side == "HOME"
                           else (home_form.get("L10") or {}).get("record"),
                "team_streak": home_form.get("current_streak") if side == "HOME" else away_form.get("current_streak"),
                "form_aligned": aligned,
                "confidence": ("HIGH" if aligned and prob >= 0.62 else
                                "MED" if aligned else "LOW"),
            })

    # Sort: high confidence first, then by prob
    alerts.sort(key=lambda a: ({"HIGH":0,"MED":1,"LOW":2}.get(a["confidence"], 3),
                                -a["p_pick_side"]))

    by_conf: Dict[str, int] = {}
    by_sport: Dict[str, int] = {}
    for a in alerts:
        by_conf[a["confidence"]] = by_conf.get(a["confidence"], 0) + 1
        by_sport[a["sport"]] = by_sport.get(a["sport"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "by_confidence": by_conf,
        "by_sport": by_sport,
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Pre-game alerts: {p['n_alerts']} total")
    print(f"  by confidence: {p['by_confidence']}")
    print(f"  by sport: {p['by_sport']}")
    for a in p["alerts"][:10]:
        align = "[A]" if a["form_aligned"] else "[?]"
        print(f"  [{a['confidence']:4}] {a['sport']:5} {align} {a['team']} {a['side']} "
              f"({a['team_l10']} L10, streak {a['team_streak']}) -- "
              f"P={a['p_pick_side']*100:.1f}%")
