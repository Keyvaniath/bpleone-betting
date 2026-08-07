"""
EdgeStat -- ESPN team rosters for NBA, NFL, WNBA, NHL.

For each league, pulls all teams + each team's full roster (player name, position,
ESPN athlete id). Used to populate real player projections downstream.

Output: data/rosters_<sport>.json
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE = "https://site.api.espn.com/apis/site/v2/sports"

SPORTS = [
    ("nba",  "basketball/nba"),
    ("wnba", "basketball/wnba"),
    ("nhl",  "hockey/nhl"),
    ("nfl",  "football/nfl"),
]


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _list_teams(espn_path: str) -> List[Dict[str, Any]]:
    d = _http(f"{BASE}/{espn_path}/teams")
    if not d: return []
    leagues = (d.get("sports") or [{}])[0].get("leagues") or [{}]
    return leagues[0].get("teams") or []


def _get_roster(espn_path: str, team_id: str) -> List[Dict[str, Any]]:
    d = _http(f"{BASE}/{espn_path}/teams/{team_id}/roster")
    if not d: return []
    out = []
    # NBA returns athletes flat; NFL returns nested by position group
    athletes = d.get("athletes", [])
    if athletes and isinstance(athletes[0], dict) and "items" in athletes[0]:
        # NFL-style: list of position groups, each with items[]
        for group in athletes:
            for a in (group.get("items") or []):
                out.append({
                    "id": a.get("id"),
                    "name": a.get("fullName") or a.get("displayName"),
                    "first_name": a.get("firstName"),
                    "last_name": a.get("lastName"),
                    "position": (a.get("position") or {}).get("abbreviation") or group.get("position"),
                    "jersey": a.get("jersey"),
                    "age": a.get("age"),
                    "height": a.get("displayHeight"),
                    "weight": a.get("weight"),
                    "experience": (a.get("experience") or {}).get("years"),
                    "headshot": (a.get("headshot") or {}).get("href"),
                })
    else:
        # NBA/WNBA-style: flat list
        for a in athletes:
            out.append({
                "id": a.get("id"),
                "name": a.get("fullName") or a.get("displayName"),
                "first_name": a.get("firstName"),
                "last_name": a.get("lastName"),
                "position": (a.get("position") or {}).get("abbreviation"),
                "jersey": a.get("jersey"),
                "age": a.get("age"),
                "height": a.get("displayHeight"),
                "weight": a.get("weight"),
                "experience": (a.get("experience") or {}).get("years"),
                "headshot": (a.get("headshot") or {}).get("href"),
            })
    return out


def fetch_sport(sport_key: str, espn_path: str) -> Dict[str, Any]:
    teams_raw = _list_teams(espn_path)
    teams_out: Dict[str, Any] = {}
    all_players: List[Dict[str, Any]] = []
    for t_wrapper in teams_raw:
        t = t_wrapper.get("team") or t_wrapper
        tid = t.get("id")
        if not tid: continue
        roster = _get_roster(espn_path, tid)
        team_block = {
            "id": tid,
            "name": t.get("displayName"),
            "abbreviation": t.get("abbreviation"),
            "location": t.get("location"),
            "n_players": len(roster),
            "players": roster,
        }
        teams_out[tid] = team_block
        for p in roster:
            all_players.append({**p, "team_id": tid, "team_name": t.get("displayName"), "team_abbr": t.get("abbreviation")})
        time.sleep(0.05)    # polite

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        "n_teams": len(teams_out),
        "n_players": len(all_players),
        "teams": teams_out,
        "all_players": all_players,
    }
    out_path = os.path.join(DATA_DIR, f"rosters_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, Any]:
    results = {}
    for sport_key, espn_path in SPORTS:
        try:
            p = fetch_sport(sport_key, espn_path)
            results[sport_key] = (p["n_teams"], p["n_players"])
        except Exception as e:
            results[sport_key] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    for sport, info in r.items():
        if isinstance(info, tuple):
            print(f"  {sport}: {info[0]} teams, {info[1]} players")
        else:
            print(f"  {sport}: {info}")
