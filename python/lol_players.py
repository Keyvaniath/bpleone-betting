"""
EdgeStat -- LoL player roster pipeline (Riot lolesports API).

Pulls full rosters for top-tier teams (LCK / LPL / LEC / LCS / regional majors).
For each player: summoner name, real name, role (top/jungle/mid/bottom/support),
team, country, image. Used to power player detail page + projections.

Output: data/lol_players.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "lol_players.json")

RIOT_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
BASE = "https://esports-api.lolesports.com/persisted/gw"

# Pull rosters only for top-tier teams to keep the file manageable
TARGET_LEAGUES = {
    "LCK", "LPL", "LEC", "LCS", "MSI", "Worlds",
    "PCS", "VCS", "CBLOL", "LLA", "LJL", "LCO",
    "First Stand", "EU Masters", "NACL",
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


def _fetch_teams() -> List[Dict[str, Any]]:
    d = _http(f"{BASE}/getTeams?hl=en-US")
    return (d.get("data") or {}).get("teams") or [] if d else []


def _team_in_league(team: Dict[str, Any], league_names: set) -> bool:
    """Heuristic: team's home league name matches one of our targets."""
    home = team.get("homeLeague") or {}
    return home.get("name", "") in league_names


def run() -> Dict[str, Any]:
    teams_raw = _fetch_teams()
    leagues = _fetch_leagues()
    target_leagues = set(TARGET_LEAGUES)

    teams_by_league: Dict[str, List[Dict[str, Any]]] = {}
    all_players: List[Dict[str, Any]] = []

    for t in teams_raw:
        home_league = (t.get("homeLeague") or {}).get("name")
        if home_league not in target_leagues:
            continue
        if t.get("status") == "disbanded":
            continue
        players = t.get("players") or []
        if not players:
            continue
        team_block = {
            "name": t.get("name"),
            "code": t.get("code"),
            "slug": t.get("slug"),
            "image": t.get("image"),
            "league": home_league,
            "n_players": len(players),
            "players": [{
                "summoner_name": p.get("summonerName"),
                "real_name": f"{p.get('firstName','') or ''} {p.get('lastName','') or ''}".strip(),
                "role": p.get("role"),
                "image": p.get("image"),
                "id": p.get("id"),
            } for p in players if p.get("role") != "none"],
        }
        teams_by_league.setdefault(home_league, []).append(team_block)
        for p in team_block["players"]:
            all_players.append({
                **p,
                "team_name": team_block["name"],
                "team_code": team_block["code"],
                "league": home_league,
            })

    # Sort by role + league strength
    role_order = {"top": 0, "jungle": 1, "mid": 2, "bottom": 3, "support": 4}
    all_players.sort(key=lambda p: (
        ["LCK","LPL","LEC","LCS"].index(p["league"]) if p["league"] in ("LCK","LPL","LEC","LCS") else 99,
        role_order.get(p.get("role"), 99),
        p.get("summoner_name", ""),
    ))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": "Riot lolesports API",
        "n_target_leagues": len(target_leagues),
        "n_teams_with_rosters": sum(len(v) for v in teams_by_league.values()),
        "n_players": len(all_players),
        "leagues": list(teams_by_league.keys()),
        "teams_by_league": teams_by_league,
        "all_players": all_players,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_teams_with_rosters']} teams, {p['n_players']} players "
          f"across {len(p['leagues'])} leagues")
    # Sample top tier
    for league in ("LCK", "LPL", "LEC", "LCS"):
        teams = p["teams_by_league"].get(league) or []
        print(f"  {league}: {len(teams)} teams")
        for t in teams[:2]:
            print(f"    {t['name']} ({t['code']}): {[pl['summoner_name'] for pl in t['players'][:5]]}")
