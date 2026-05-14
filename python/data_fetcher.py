"""
EdgeStat - data fetcher.

Wraps two APIs we'll use in production:
  1. MLB Stats API (statsapi.mlb.com) - free, official, no API key
  2. The Odds API (the-odds-api.com) - paid, $30/mo for individual tier

Right now this is a thin client + sample call. Replace API key and run on a
cron once you're ready to push live data into the dashboard / Squarespace
embed.

Usage:
    pip install requests
    python data_fetcher.py
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # graceful — file remains importable in audit
    requests = None  # type: ignore


# -------------------- MLB Stats API (free) --------------------

MLB_BASE = "https://statsapi.mlb.com/api/v1"

def fetch_today_schedule(date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return today's MLB schedule. If `date` omitted, uses today (US/Pacific)."""
    if requests is None:
        raise RuntimeError("requests not installed: pip install requests")
    date = date or dt.date.today().isoformat()
    url = f"{MLB_BASE}/schedule?sportId=1&date={date}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    payload = r.json()
    games = []
    for date_block in payload.get("dates", []):
        for g in date_block.get("games", []):
            games.append({
                "gamePk": g["gamePk"],
                "time": g.get("gameDate"),
                "home": g["teams"]["home"]["team"]["abbreviation"] if "abbreviation" in g["teams"]["home"]["team"] else g["teams"]["home"]["team"]["name"],
                "away": g["teams"]["away"]["team"]["abbreviation"] if "abbreviation" in g["teams"]["away"]["team"] else g["teams"]["away"]["team"]["name"],
                "venue": g["venue"]["name"],
                "status": g["status"]["detailedState"],
            })
    return games


def fetch_probable_pitchers(game_pk: int) -> Dict[str, Any]:
    """Probable starting pitchers for a game."""
    if requests is None:
        raise RuntimeError("requests not installed: pip install requests")
    url = f"{MLB_BASE}/schedule?sportId=1&gamePk={game_pk}&hydrate=probablePitcher"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    payload = r.json()
    for d in payload.get("dates", []):
        for g in d.get("games", []):
            return {
                "home": g["teams"]["home"].get("probablePitcher", {}).get("fullName"),
                "away": g["teams"]["away"].get("probablePitcher", {}).get("fullName"),
            }
    return {}


def fetch_team_stats(team_id: int, season: int) -> Dict[str, Any]:
    """Pull season-to-date hitting + pitching for a team."""
    if requests is None:
        raise RuntimeError("requests not installed: pip install requests")
    out: Dict[str, Any] = {}
    for group in ("hitting", "pitching"):
        r = requests.get(
            f"{MLB_BASE}/teams/{team_id}/stats",
            params={"stats": "season", "group": group, "season": season},
            timeout=15,
        )
        r.raise_for_status()
        out[group] = r.json()
    return out


# -------------------- The Odds API (paid) --------------------

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4"


def fetch_mlb_odds(markets: str = "h2h,spreads,totals",
                   regions: str = "us",
                   bookmakers: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch today's MLB odds from The Odds API."""
    if requests is None:
        raise RuntimeError("requests not installed: pip install requests")
    if not ODDS_API_KEY:
        raise RuntimeError("Set ODDS_API_KEY environment variable. Get one at the-odds-api.com.")
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    r = requests.get(f"{ODDS_BASE}/sports/baseball_mlb/odds/", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_mlb_player_props(event_id: str,
                           markets: str = "batter_total_bases,batter_home_runs,batter_hits,pitcher_strikeouts") -> Dict[str, Any]:
    """Fetch MLB player prop markets for a given event."""
    if requests is None:
        raise RuntimeError("requests not installed: pip install requests")
    if not ODDS_API_KEY:
        raise RuntimeError("Set ODDS_API_KEY environment variable.")
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
    }
    r = requests.get(f"{ODDS_BASE}/sports/baseball_mlb/events/{event_id}/odds",
                     params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# -------------------- Caching / persistence --------------------

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


def cache_path(name: str, date: Optional[str] = None) -> str:
    date = date or dt.date.today().isoformat()
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{date}_{name}.json")


def save_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


# -------------------- CLI runner --------------------

def run_morning_pull() -> None:
    """Pull today's schedule + odds, save snapshots to cache/."""
    today = dt.date.today().isoformat()
    print(f"[{today}] Pulling MLB schedule…")
    sched = fetch_today_schedule()
    save_json(cache_path("schedule"), sched)
    print(f"  → {len(sched)} games")

    print(f"[{today}] Pulling MLB odds…")
    try:
        odds = fetch_mlb_odds()
        save_json(cache_path("odds"), odds)
        print(f"  → {len(odds)} events priced")
    except Exception as e:
        print(f"  ✗ Odds API skipped: {e}")


if __name__ == "__main__":
    run_morning_pull()
