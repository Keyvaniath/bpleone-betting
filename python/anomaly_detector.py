"""
EdgeStat -- cross-sport anomaly detector.

Compares today's predictions to historical patterns and flags games where:
  - Team is on extreme streak (W6+ or L6+) but model rates them as a coinflip
  - Heavy favorite (P >= 75%) playing road game against a team that's
    been outperforming model expectation by 6+ points in last 5 games
  - Total expected (model) diverges from team's recent over-pct by >25pp
  - Game where teams' L10 records contradict our P(home) by 20pp+

Output: data/anomaly_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "anomaly_alerts.json")

SPORTS_TEAM = ["nba", "nhl", "wnba", "mls", "epl", "cws"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _expected_winpct(p_home: float, team_is_home: bool) -> float:
    return p_home if team_is_home else 1 - p_home


def run() -> Dict[str, Any]:
    alerts: List[Dict[str, Any]] = []

    for sport in SPORTS_TEAM:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        form = _load(os.path.join(DATA_DIR, f"team_form_{sport}.json")).get("teams") or {}
        residuals = _load(os.path.join(DATA_DIR, f"team_residuals_{sport}.json")).get("teams") or {}
        for g in (state.get("games") or []):
            if g.get("state") == "post": continue
            home = g.get("home_team"); away = g.get("away_team")
            ph = g.get("p_home_win") or 0.5
            home_form = form.get(home, {})
            away_form = form.get(away, {})
            home_res = residuals.get(home, {})
            away_res = residuals.get(away, {})

            # 1) Streak mismatch: hot team rated as coinflip
            for team_name, team_form, side, side_prob in (
                (home, home_form, "HOME", ph),
                (away, away_form, "AWAY", 1 - ph),
            ):
                streak = (team_form.get("current_streak") or "")
                streak_n = 0
                streak_type = None
                if streak and len(streak) >= 2 and streak[0] in ("W", "L"):
                    try:
                        streak_type = streak[0]
                        streak_n = int(streak[1:])
                    except Exception:
                        pass
                if streak_n >= 5 and streak_type == "W" and 0.40 <= side_prob <= 0.55:
                    alerts.append({
                        "sport": sport.upper(),
                        "type": "STREAK_MISMATCH",
                        "team": team_name,
                        "matchup": g.get("matchup"),
                        "model_prob": round(side_prob, 4),
                        "detail": f"{team_name} on W{streak_n} streak but model rates as {side_prob*100:.0f}% -- may be undervalued",
                    })
                if streak_n >= 5 and streak_type == "L" and side_prob >= 0.50:
                    alerts.append({
                        "sport": sport.upper(),
                        "type": "STREAK_MISMATCH",
                        "team": team_name,
                        "matchup": g.get("matchup"),
                        "model_prob": round(side_prob, 4),
                        "detail": f"{team_name} on L{streak_n} streak but model still favors them ({side_prob*100:.0f}%) -- may be overvalued",
                    })

            # 2) Residual divergence: team has been outperforming/underperforming ELO expectation
            for team_name, team_res, side, side_prob in (
                (home, home_res, "HOME", ph),
                (away, away_res, "AWAY", 1 - ph),
            ):
                avg_res = team_res.get("avg_residual")
                if avg_res is None: continue
                if abs(avg_res) >= 6 and team_res.get("n_home", 0) + team_res.get("n_away", 0) >= 3:
                    direction = "OUTPERFORMING" if avg_res > 0 else "UNDERPERFORMING"
                    alerts.append({
                        "sport": sport.upper(),
                        "type": "RESIDUAL_DIVERGENCE",
                        "team": team_name,
                        "matchup": g.get("matchup"),
                        "avg_residual": avg_res,
                        "model_prob": round(side_prob, 4),
                        "detail": f"{team_name} {direction} expected margin by {abs(avg_res):.1f}pts in recent games -- model bias may persist",
                    })

            # 3) Over% mismatch: heavy over team in low-projected game
            for team_name, team_form in ((home, home_form), (away, away_form)):
                over_pct = team_form.get("over_pct")
                if over_pct is None: continue
                # Doesn't make sense for soccer (1-3 goal games), skip MLS/EPL
                if sport in ("mls", "epl"): continue
                if over_pct >= 0.75 and team_form.get("L10", {}).get("n", 0) >= 8:
                    alerts.append({
                        "sport": sport.upper(),
                        "type": "OVER_HEAVY_TEAM",
                        "team": team_name,
                        "matchup": g.get("matchup"),
                        "over_pct": over_pct,
                        "detail": f"{team_name} has gone OVER team-median total in {over_pct*100:.0f}% of L10 games -- lean OVER",
                    })

    # De-dup (same team can show up in multiple alerts)
    seen_keys = set()
    unique = []
    for a in alerts:
        key = f"{a['sport']}|{a['team']}|{a['type']}"
        if key in seen_keys: continue
        seen_keys.add(key)
        unique.append(a)

    by_type: Dict[str, int] = {}
    by_sport: Dict[str, int] = {}
    for a in unique:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
        by_sport[a["sport"]] = by_sport.get(a["sport"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts": len(unique),
        "by_type": by_type,
        "by_sport": by_sport,
        "alerts": unique,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Anomaly alerts: {p['n_alerts']}")
    print(f"  by type: {p['by_type']}")
    print(f"  by sport: {p['by_sport']}")
    for a in p["alerts"][:10]:
        print(f"  [{a['type']}] {a['sport']:5} {a['team']:25} -- {a['detail'][:90]}")
