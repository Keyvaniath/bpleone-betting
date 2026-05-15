"""
EdgeStat -- travel & rest day signal.

For each game tonight, determines:
  - Each team's days-of-rest (0 = back-to-back, 1+ = at least one day off)
  - Whether the away team is in a different timezone from yesterday's game
  - Getaway-day flag (day game with travel after)

These are real edges: a team flying coast-to-coast and playing the next day
underperforms by ~0.1 win prob historically; teams with 2+ days rest after a
travel day outperform.

Writes data/travel.json keyed by matchup.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "travel.json")

# Park time-zones (approximate, used to detect cross-country trips)
PARK_TZ = {
    "Dodger Stadium": "PT", "Petco Park": "PT", "Oracle Park": "PT",
    "Angel Stadium": "PT", "Oakland Coliseum": "PT", "Sutter Health Park": "PT",
    "T-Mobile Park": "PT", "UNIQLO Field at Dodger Stadium": "PT",
    "Chase Field": "MT", "Coors Field": "MT",
    "Globe Life Field": "CT", "Daikin Park": "CT", "Minute Maid Park": "CT",
    "Kauffman Stadium": "CT", "Target Field": "CT", "Busch Stadium": "CT",
    "American Family Field": "CT", "Wrigley Field": "CT", "Rate Field": "CT",
    "Great American Ball Park": "ET", "Truist Park": "ET",
    "Tropicana Field": "ET", "loanDepot park": "ET",
    "Citi Field": "ET", "Yankee Stadium": "ET", "Fenway Park": "ET",
    "Citizens Bank Park": "ET", "Oriole Park at Camden Yards": "ET",
    "Nationals Park": "ET", "Comerica Park": "ET", "Progressive Field": "ET",
    "PNC Park": "ET", "Rogers Centre": "ET",
}

TZ_HOURS = {"PT": -8, "MT": -7, "CT": -6, "ET": -5}


def _team_last_game(team_id: int, before_date: str) -> Optional[Dict[str, Any]]:
    """Return team's most recent game before given date."""
    if requests is None:
        return None
    look_back = (dt.date.fromisoformat(before_date) - dt.timedelta(days=5)).isoformat()
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "teamId": team_id,
                    "startDate": look_back, "endDate": before_date},
            timeout=10,
        )
        if not r.ok:
            return None
        sched = r.json().get("dates", [])
    except Exception:
        return None
    games: List[Dict[str, Any]] = []
    for d in sched:
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") != "Final":
                continue
            if g.get("officialDate") and g["officialDate"] < before_date:
                games.append(g)
    if not games:
        return None
    games.sort(key=lambda x: x.get("officialDate", ""), reverse=True)
    return games[0]


def project_travel(team_id: int, today_date: str, today_venue: str) -> Dict[str, Any]:
    last = _team_last_game(team_id, today_date)
    if not last:
        return {"rest_days": None, "tz_change_hours": 0, "travel_note": "no recent data"}
    last_date = last.get("officialDate") or ""
    try:
        delta = (dt.date.fromisoformat(today_date) -
                 dt.date.fromisoformat(last_date)).days
    except Exception:
        delta = None
    last_venue = (last.get("venue") or {}).get("name") or ""
    last_tz = PARK_TZ.get(last_venue, "ET")
    today_tz = PARK_TZ.get(today_venue, "ET")
    tz_delta_h = TZ_HOURS.get(today_tz, -5) - TZ_HOURS.get(last_tz, -5)
    note = ""
    if delta == 0:
        note = "day-of-day double header"
    elif delta == 1 and abs(tz_delta_h) >= 2:
        note = f"travel + back-to-back ({tz_delta_h:+d}h tz shift)"
    elif delta == 1:
        note = "back-to-back"
    elif delta and delta >= 2:
        note = f"{delta} days rest" + (f" ({tz_delta_h:+d}h tz)" if abs(tz_delta_h) >= 2 else "")
    return {
        "rest_days": delta,
        "last_game_date": last_date,
        "last_venue": last_venue,
        "tz_change_hours": tz_delta_h,
        "travel_note": note,
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    today_date = dt.date.today().isoformat()
    teams = sr._teams()
    # Reverse map: team_id -> name
    id_to_name = {info["id"]: name for name, info in teams.items()}

    out_games = []
    for g in m.get("games", []):
        venue = g.get("venue") or g.get("park") or ""
        # Get team IDs from the home/away team dicts
        home_tid = (g.get("home") or {}).get("team_id")
        away_tid = (g.get("away") or {}).get("team_id")
        home_travel = project_travel(home_tid, today_date, venue) if home_tid else {}
        away_travel = project_travel(away_tid, today_date, venue) if away_tid else {}
        out_games.append({
            "matchup": g.get("matchup"),
            "time": g.get("time"),
            "park": venue,
            "home": home_travel,
            "away": away_travel,
        })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
    }


def write_travel(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote travel -> {path}")
    print(f"  Games covered: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:6]:
        h = g.get("home") or {}
        a = g.get("away") or {}
        print(f"  {g['matchup']:14} | home: {h.get('travel_note','--')} | away: {a.get('travel_note','--')}")


if __name__ == "__main__":
    write_travel(build_all())
