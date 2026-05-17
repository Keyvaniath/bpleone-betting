"""
EdgeStat -- League of Legends esports pipeline (Riot lolesports public API).

Pulls every active league + ongoing/recent/upcoming matches from Riot's
public lolesports API. Free, no auth required (uses public web x-api-key).

Returns:
  - Active leagues (LCS, LEC, LCK, LPL, MSI, Worlds, etc.)
  - Live matches with current series score (best-of-N format)
  - Completed matches with final scores (for settlement)
  - Upcoming matches with team names

Output: data/lol_state.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "lol_state.json")

# Public Riot esports web API key (visible in lolesports.com source -- safe to use)
RIOT_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
BASE = "https://esports-api.lolesports.com/persisted/gw"

# Filter to the major leagues (otherwise we get hundreds of amateur events)
MAJOR_LEAGUES = {
    "LCS", "LEC", "LCK", "LPL", "MSI", "Worlds", "PCS", "VCS", "CBLOL",
    "LCO", "LLA", "LJL", "Liiga", "LFL", "NLC", "Ultraliga", "EU Masters",
    "Demacia Cup", "First Stand",
    # Tier 2 (academy / challenger)
    "NACL", "EMEA Masters",
}


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "EdgeStat/1.0",
            "x-api-key": RIOT_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_leagues() -> List[Dict[str, Any]]:
    d = _http(f"{BASE}/getLeagues?hl=en-US")
    return (d.get("data") or {}).get("leagues") or [] if d else []


def _fetch_schedule(league_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get current schedule across all (or specified) leagues."""
    suffix = f"&leagueId={league_id}" if league_id else ""
    d = _http(f"{BASE}/getSchedule?hl=en-US{suffix}")
    return ((d.get("data") or {}).get("schedule") or {}).get("events") or [] if d else []


def _fetch_live() -> List[Dict[str, Any]]:
    d = _http(f"{BASE}/getLive?hl=en-US")
    return ((d.get("data") or {}).get("schedule") or {}).get("events") or [] if d else []


def _parse_event(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a Riot event into a standard match record."""
    match = ev.get("match") or {}
    teams = match.get("teams") or []
    if len(teams) < 2:
        return None
    league = ev.get("league") or {}
    league_name = league.get("name", "?")

    t1 = teams[0]
    t2 = teams[1]
    s1 = (t1.get("result") or {}).get("gameWins")
    s2 = (t2.get("result") or {}).get("gameWins")

    state = ev.get("state", "?")    # "unstarted" | "inProgress" | "completed"
    strategy = match.get("strategy", {})    # {type: "bestOf", count: 3}
    bo_count = strategy.get("count", 1)

    winner = None
    if state == "completed":
        if (s1 or 0) > (s2 or 0):
            winner = t1.get("name")
        elif (s2 or 0) > (s1 or 0):
            winner = t2.get("name")

    return {
        "id": match.get("id") or ev.get("startTime"),
        "league": league_name,
        "league_slug": league.get("slug"),
        "tournament": (ev.get("tournament") or {}).get("id"),
        "start_time": ev.get("startTime"),
        "state": state,
        "best_of": bo_count,
        "team_a": t1.get("name"),
        "team_a_code": t1.get("code"),
        "team_a_record": (t1.get("record") or {}).get("wins"),
        "team_a_losses": (t1.get("record") or {}).get("losses"),
        "team_a_score": s1,
        "team_b": t2.get("name"),
        "team_b_code": t2.get("code"),
        "team_b_record": (t2.get("record") or {}).get("wins"),
        "team_b_losses": (t2.get("record") or {}).get("losses"),
        "team_b_score": s2,
        "winner": winner,
        "is_completed": state == "completed",
        "is_in_progress": state == "inProgress",
    }


def run() -> Dict[str, Any]:
    leagues_raw = _fetch_leagues()
    leagues = [{
        "id": l.get("id"),
        "name": l.get("name"),
        "slug": l.get("slug"),
        "region": (l.get("region") or "").upper(),
        "image": l.get("image"),
        "priority": l.get("priority", 99),
    } for l in leagues_raw]
    leagues.sort(key=lambda l: l["priority"])

    schedule = _fetch_schedule()
    live_evs = _fetch_live()

    # Merge live events (some may not appear in main schedule)
    seen_ids = {ev.get("startTime") for ev in schedule}
    for ev in live_evs:
        if ev.get("startTime") not in seen_ids:
            schedule.append(ev)

    matches: List[Dict[str, Any]] = []
    for ev in schedule:
        parsed = _parse_event(ev)
        if not parsed:
            continue
        # Filter to major leagues
        if parsed["league"] in MAJOR_LEAGUES or any(ml in parsed["league"] for ml in ("Worlds", "MSI", "LCS", "LEC", "LCK", "LPL")):
            matches.append(parsed)

    # Sort: live first, then upcoming by start time, then completed by start time desc
    def sort_key(m):
        if m["is_in_progress"]:
            return (0, m["start_time"])
        if not m["is_completed"]:
            return (1, m["start_time"])
        return (2, "z" + (m["start_time"] or ""))    # completed last
    matches.sort(key=sort_key)

    live_matches = [m for m in matches if m["is_in_progress"]]
    upcoming = [m for m in matches if m["state"] == "unstarted"][:30]
    recent = [m for m in matches if m["is_completed"]][:20]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": "Riot lolesports API",
        "n_leagues": len(leagues),
        "n_matches_total": len(matches),
        "n_live": len(live_matches),
        "n_upcoming": len(upcoming),
        "n_recent": len(recent),
        "leagues": leagues[:30],
        "live_matches": live_matches,
        "upcoming_matches": upcoming,
        "recent_matches": recent,
        "all_matches": matches[:80],    # cap for file size
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_matches_total']} major-league matches "
          f"({p['n_live']} live, {p['n_upcoming']} upcoming, {p['n_recent']} recent)")
    if p["live_matches"]:
        print("  Live now:")
        for m in p["live_matches"][:5]:
            print(f"    [{m['league']}] {m['team_a']} {m['team_a_score']}-{m['team_b_score']} {m['team_b']} (BO{m['best_of']})")
    if p["recent_matches"]:
        print("  Recent winners:")
        for m in p["recent_matches"][:3]:
            print(f"    [{m['league']}] {m['winner']} beat {m['team_b'] if m['winner']==m['team_a'] else m['team_a']} ({m['team_a_score']}-{m['team_b_score']})")
