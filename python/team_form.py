"""
EdgeStat -- team form tracker.

Pulls each MLB team's last 10 games from the schedule endpoint and computes:
  - W-L record (last 10)
  - Run differential
  - Current win/loss streak
  - Runs per game / Runs allowed per game

These metrics are a useful research overlay -- "this team is 8-2 in their
last 10 with a +24 run diff" is signal that the model's season stats may
be lagging actual recent performance.

Writes data/team_form.json keyed by team name.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "team_form.json")


def fetch_last_10(team_id: int) -> Dict[str, Any]:
    """Return {wins, losses, run_diff, streak, runs_pg, runs_allowed_pg} for last 10 games."""
    if requests is None:
        return {}
    # Pull last 20 days of schedule to ensure we get ~10 played games
    today = dt.date.today()
    start = (today - dt.timedelta(days=20)).isoformat()
    end = today.isoformat()
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "teamId": team_id,
                    "startDate": start, "endDate": end},
            timeout=10,
        )
        if not r.ok:
            return {}
        sched = r.json().get("dates", [])
    except Exception:
        return {}
    games: List[Dict[str, Any]] = []
    for d in sched:
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") != "Final":
                continue
            home_id = g["teams"]["home"]["team"]["id"]
            away_id = g["teams"]["away"]["team"]["id"]
            home_r = g["teams"]["home"].get("score")
            away_r = g["teams"]["away"].get("score")
            if home_r is None or away_r is None:
                continue
            is_home = home_id == team_id
            team_runs = home_r if is_home else away_r
            opp_runs = away_r if is_home else home_r
            games.append({
                "date": g.get("officialDate"),
                "won": team_runs > opp_runs,
                "team_runs": team_runs,
                "opp_runs": opp_runs,
            })
    games.sort(key=lambda x: x["date"] or "", reverse=True)
    last10 = games[:10]
    if not last10:
        return {}
    wins = sum(1 for g in last10 if g["won"])
    losses = len(last10) - wins
    run_diff = sum(g["team_runs"] - g["opp_runs"] for g in last10)
    runs_pg = round(sum(g["team_runs"] for g in last10) / len(last10), 2)
    runs_allowed_pg = round(sum(g["opp_runs"] for g in last10) / len(last10), 2)
    # Current streak (most recent game forward)
    streak_count = 1
    if len(last10) >= 2:
        latest_won = last10[0]["won"]
        for g in last10[1:]:
            if g["won"] == latest_won:
                streak_count += 1
            else:
                break
        streak_str = ("W" if latest_won else "L") + str(streak_count)
    else:
        streak_str = "W1" if last10[0]["won"] else "L1"
    return {
        "wins": wins,
        "losses": losses,
        "run_diff": run_diff,
        "runs_pg": runs_pg,
        "runs_allowed_pg": runs_allowed_pg,
        "streak": streak_str,
        "games_in_sample": len(last10),
    }


def build_all() -> Dict[str, Any]:
    teams = sr._teams()
    out: Dict[str, Any] = {}
    if not teams:
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "team list unavailable", "teams": {}}
    for name, info in teams.items():
        form = fetch_last_10(info["id"])
        if form:
            out[name] = {"team_id": info["id"], "abbr": info.get("abbr"), **form}
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "teams": out,
    }


def write_team_form(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote team_form -> {path}")
    print(f"  Teams covered: {len(payload.get('teams', {}))}")
    # Show 3 hottest and 3 coldest teams
    teams = payload.get("teams") or {}
    sorted_by_diff = sorted(teams.items(), key=lambda kv: -kv[1].get("run_diff", 0))
    print("  Hottest 3 (last 10 run diff):")
    for name, t in sorted_by_diff[:3]:
        print(f"    {name:25} {t.get('wins')}-{t.get('losses')} ({t.get('streak')}), "
              f"run diff {t.get('run_diff'):>+3}, {t.get('runs_pg')} R/G, {t.get('runs_allowed_pg')} RA/G")
    print("  Coldest 3:")
    for name, t in sorted_by_diff[-3:]:
        print(f"    {name:25} {t.get('wins')}-{t.get('losses')} ({t.get('streak')}), "
              f"run diff {t.get('run_diff'):>+3}, {t.get('runs_pg')} R/G, {t.get('runs_allowed_pg')} RA/G")


if __name__ == "__main__":
    write_team_form(build_all())
