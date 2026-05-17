"""
EdgeStat -- multi-sport team form tracker (LIVE from historical_*.json).

For every sport with historical data, computes per-team:
  - L5 / L10 form (record, avg PF/PA, last 5 results with scores)
  - Home vs away splits
  - Over% (pct of games over team's median total)

Output: data/team_form_<sport>.json (one per sport)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "cws"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _last_n_form(games_for_team: List[Dict[str, Any]], n: int) -> Dict[str, Any]:
    recent = games_for_team[:n]
    if not recent:
        return {"n": 0, "record": "0-0", "win_pct": 0,
                 "avg_pf": 0, "avg_pa": 0, "diff": 0, "last_results": []}
    wins = sum(1 for g in recent if g.get("won"))
    losses = len(recent) - wins
    pf = sum(g.get("team_score", 0) for g in recent) / len(recent)
    pa = sum(g.get("opp_score", 0) for g in recent) / len(recent)
    return {
        "n": len(recent),
        "record": f"{wins}-{losses}",
        "wins": wins, "losses": losses,
        "avg_pf": round(pf, 1),
        "avg_pa": round(pa, 1),
        "diff": round(pf - pa, 1),
        "win_pct": round(wins / len(recent), 3),
        "last_results": [{
            "date": g["date"], "vs": g.get("opp"),
            "score": f"{g['team_score']}-{g['opp_score']}",
            "result": "W" if g.get("won") else "L",
            "home": g.get("is_home"),
        } for g in recent[:5]],
    }


def compute_team_form(sport: str) -> Dict[str, Any]:
    h = _load(os.path.join(DATA_DIR, f"historical_{sport}.json"))
    games = h.get("games") or []
    if not games:
        return {"sport": sport, "n_teams": 0, "teams": {}}

    by_team: Dict[str, List[Dict[str, Any]]] = {}
    for g in games:
        if not (g.get("home_team") and g.get("away_team")): continue
        by_team.setdefault(g["home_team"], []).append({
            "date": g["date"], "opp": g["away_team"],
            "team_score": g["home_score"], "opp_score": g["away_score"],
            "won": g["home_score"] > g["away_score"],
            "is_home": True, "total": g["total"], "margin": g["margin"],
        })
        by_team.setdefault(g["away_team"], []).append({
            "date": g["date"], "opp": g["home_team"],
            "team_score": g["away_score"], "opp_score": g["home_score"],
            "won": g["away_score"] > g["home_score"],
            "is_home": False, "total": g["total"], "margin": -g["margin"],
        })

    for team, gs in by_team.items():
        gs.sort(key=lambda g: g["date"], reverse=True)

    teams: Dict[str, Any] = {}
    for team, gs in by_team.items():
        home_games = [g for g in gs if g["is_home"]]
        away_games = [g for g in gs if not g["is_home"]]
        home_wins = sum(1 for g in home_games if g["won"])
        away_wins = sum(1 for g in away_games if g["won"])
        if gs:
            totals = sorted(g["total"] for g in gs)
            median_total = totals[len(totals) // 2]
            over_pct = sum(1 for g in gs if g["total"] > median_total) / len(gs)
        else:
            median_total = 0; over_pct = 0
        # Current win/loss streak
        streak = 0
        streak_type = None
        for g in gs:
            r = "W" if g["won"] else "L"
            if streak_type is None: streak_type = r; streak = 1
            elif streak_type == r: streak += 1
            else: break
        teams[team] = {
            "name": team,
            "total_games": len(gs),
            "L5": _last_n_form(gs, 5),
            "L10": _last_n_form(gs, 10),
            "home_record": f"{home_wins}-{len(home_games) - home_wins}",
            "away_record": f"{away_wins}-{len(away_games) - away_wins}",
            "home_win_pct": round(home_wins / max(1, len(home_games)), 3),
            "away_win_pct": round(away_wins / max(1, len(away_games)), 3),
            "median_total": median_total,
            "over_pct": round(over_pct, 3),
            "current_streak": f"{streak_type}{streak}" if streak_type else "—",
        }

    out_path = os.path.join(DATA_DIR, f"team_form_{sport}.json")
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport,
        "n_teams": len(teams),
        "n_historical_games": len(games),
        "teams": teams,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, int]:
    results = {}
    for sport in SPORTS:
        try:
            p = compute_team_form(sport)
            results[sport] = p["n_teams"]
        except Exception as e:
            results[sport] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    print("Multi-sport team form:")
    for sport, n in r.items():
        print(f"  {sport:6}: {n} teams")
