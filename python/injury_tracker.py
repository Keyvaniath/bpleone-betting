"""
EdgeStat -- daily injury tracker.

For each MLB team, pull the 40-man roster with status from MLB Stats API and
write the IL'd players to data/injuries_live.json. Filters to Injured 7-Day,
15-Day, 60-Day, and Full-Season. Surfaced on the research page.

(Distinct from python/injury.py which computes WP-impact-per-IL-event.)
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


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "injuries_live.json")

IL_STATUSES = {
    "Injured 7-Day", "Injured 10-Day", "Injured 15-Day", "Injured 60-Day",
    "Injured - Full Season",
}


def fetch_team_injuries(team_id: int) -> List[Dict[str, Any]]:
    """Return IL'd players for a team. Uses 40Man roster (active 40-man + IL)."""
    if requests is None:
        return []
    try:
        r = requests.get(
            f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster",
            params={"rosterType": "40Man"},
            timeout=10,
        )
        if not r.ok:
            return []
        roster = r.json().get("roster", []) or []
    except Exception:
        return []
    out = []
    for p in roster:
        status_desc = (p.get("status") or {}).get("description", "")
        if status_desc not in IL_STATUSES:
            continue
        person = p.get("person", {})
        out.append({
            "id": person.get("id"),
            "name": person.get("fullName"),
            "position": (p.get("position") or {}).get("abbreviation"),
            "status": status_desc,
        })
    return out


def build_injuries() -> Dict[str, Any]:
    teams = sr._teams()
    out: Dict[str, Any] = {}
    if not teams:
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "team list unavailable", "teams": {}}
    for name, info in teams.items():
        tid = info["id"]
        injuries = fetch_team_injuries(tid)
        if injuries:
            out[name] = {
                "team_id": tid,
                "abbr": info.get("abbr"),
                "il_count": len(injuries),
                "players": injuries,
            }
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "teams_with_injuries": len(out),
        "total_il_players": sum(t["il_count"] for t in out.values()),
        "teams": out,
    }


def write_injuries(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote injuries -> {path}")
    print(f"  Teams with IL players: {payload.get('teams_with_injuries', 0)}")
    print(f"  Total IL players: {payload.get('total_il_players', 0)}")


if __name__ == "__main__":
    write_injuries(build_injuries())
