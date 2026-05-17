"""
EdgeStat -- golf desk pipeline.

Pulls current PGA Tour tournament state from ESPN's free API:
  - Active tournament name + dates + course + cut line
  - Full field with current position, round score, total, holes left
  - Per-player tee time / current round status

Output: data/golf_state.json
  {
    "generated_at": "...",
    "active_tournament": {name, course, dates, status},
    "n_players": 156,
    "field": [
      { name, espn_id, country, world_rank, position, total_score,
        round_score, holes_played, status (active/cut/withdrawn) }
    ],
    "current_leader": {...}
  }

Free data, no auth needed (ESPN public API).
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "golf_state.json")

# ESPN's leaderboard is exposed via the /scoreboard endpoint (the
# /leaderboard URL returns 404).
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
ESPN_LEADERBOARD = ESPN_SCOREBOARD


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _parse_competitor(c: Dict[str, Any]) -> Dict[str, Any]:
    """Each ESPN competitor entry has athlete + score + linescores per round."""
    athlete = (c.get("athlete") or {})
    score = c.get("score")   # e.g. "-6" overall
    linescores = c.get("linescores") or []
    rounds_played = len(linescores)
    last = linescores[-1] if linescores else {}
    # Per-hole linescores within the last round tell us thru
    hole_scores = (last.get("linescores") or []) if isinstance(last, dict) else []
    thru = len(hole_scores) if hole_scores else (18 if last.get("displayValue") and isinstance(last.get("value"), (int, float)) else 0)
    stats = c.get("statistics") or []
    return {
        "espn_id": c.get("id"),
        "order": c.get("order"),     # current leaderboard position
        "name": athlete.get("fullName") or athlete.get("displayName") or athlete.get("shortName"),
        "country": (athlete.get("flag") or {}).get("alt"),
        "total_to_par": score,        # like "-6" or "+2" or "E"
        "rounds_played": rounds_played,
        "last_round_score": last.get("displayValue") if isinstance(last, dict) else None,
        "thru": thru if thru and thru < 18 else None,
        "is_cut": False,              # ESPN doesn't tag this on /scoreboard; computed downstream
        "is_withdrawn": False,
    }


def run() -> Dict[str, Any]:
    lb = _http(ESPN_LEADERBOARD)
    if not lb:
        out = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "active_tournament": None,
            "error": "ESPN leaderboard unreachable",
            "field": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=2)
        return out

    events = lb.get("events") or []
    if not events:
        out = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "active_tournament": None,
            "note": "No active PGA tournament right now",
            "field": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=2)
        return out

    ev = events[0]
    name = ev.get("name") or ev.get("shortName")
    status = (ev.get("status") or {}).get("type", {})
    course = ev.get("courses") or []
    course_name = (course[0].get("name") if course else None)
    start_date = ev.get("date")
    end_date = ev.get("endDate")

    competitions = ev.get("competitions") or []
    field: List[Dict[str, Any]] = []
    leader = None
    if competitions:
        comp = competitions[0]
        for c in (comp.get("competitors") or []):
            parsed = _parse_competitor(c)
            field.append(parsed)
        # Already sorted by ESPN via the `order` field (1 = leader)
        field.sort(key=lambda p: p.get("order") or 999)
        leader = field[0] if field else None

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_tournament": {
            "name": name,
            "course": course_name,
            "start_date": start_date,
            "end_date": end_date,
            "status": status.get("description"),
            "round": (ev.get("status") or {}).get("period"),
            "is_complete": status.get("completed", False),
            "is_in_progress": status.get("state") == "in",
        },
        "n_players": len(field),
        "current_leader": leader,
        "field": field,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    t = p.get("active_tournament")
    if not t:
        print(f"  {p.get('note', p.get('error', 'No data'))}")
    else:
        print(f"  Tournament: {t['name']} @ {t['course']}")
        print(f"  Status: {t['status']} (round {t.get('round')})")
        print(f"  Field: {p['n_players']} players")
        if p.get("current_leader"):
            l = p["current_leader"]
            print(f"  Leader: {l['name']} (pos #{l.get('order')}, total {l.get('total_to_par')}, R{l.get('rounds_played')} thru {l.get('thru') or 'F'})")
