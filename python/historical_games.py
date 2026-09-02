"""
EdgeStat -- historical games fetcher.

Pulls last N days of completed games per ESPN sport. Powers:
  - Team form (L5/L10 records)
  - Head-to-head history
  - Backtest-driven self-training
  - ATS / O-U records

Output: data/historical_<sport>.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sports + ESPN paths + how many days of history to pull
SPORTS = [
    ("nba",   "basketball/nba",                  14),
    ("nhl",   "hockey/nhl",                       14),
    ("wnba",  "basketball/wnba",                  14),
    ("mls",   "soccer/usa.1",                     21),  # fewer matches per day
    ("epl",   "soccer/eng.1",                     21),
    ("nfl",   "football/nfl",                      7),  # off-season; less needed
    ("ncaaf", "football/college-football",         3),  # 99/day = too many
    ("cws",   "baseball/college-baseball",         7),
    ("mlb",   "baseball/mlb",                     14),
]


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _summarize(ev: Dict[str, Any], board_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pull the bits we need from an ESPN event.

    board_date (2026-09-02): the calendar day the scoreboard was QUERIED for.
    ev['date'] is a UTC timestamp, so a west-coast night game (10pm ET = 02:00
    UTC next day) got stamped one day late -- e.g. the real 8/27 ARI @ SF final
    sat in this file dated 8/28, where no pick could ever match it. Every
    consumer (settlement, alpha grading) keys picks by the ET schedule day, so
    the file must stamp the day ESPN's own schedule calls the game."""
    status = (ev.get("status") or {}).get("type", {})
    if not status.get("completed"):
        return None
    comps = ev.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"),
                 competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"),
                 competitors[1] if len(competitors) > 1 else {})
    try:
        h_score = int(home.get("score") or 0)
        a_score = int(away.get("score") or 0)
    except Exception:
        return None
    return {
        "id": ev.get("id"),
        "date": board_date or (ev.get("date") or "")[:10],
        "home_team": (home.get("team") or {}).get("displayName"),
        "away_team": (away.get("team") or {}).get("displayName"),
        "home_abbrev": (home.get("team") or {}).get("abbreviation"),
        "away_abbrev": (away.get("team") or {}).get("abbreviation"),
        "home_score": h_score,
        "away_score": a_score,
        "winner": (home.get("team") or {}).get("displayName") if h_score > a_score
                  else (away.get("team") or {}).get("displayName") if a_score > h_score
                  else None,
        "total": h_score + a_score,
        "margin": h_score - a_score,
    }


def fetch_sport_history(sport_key: str, espn_path: str, days: int) -> Dict[str, Any]:
    """Pull last `days` days of completed games."""
    out: List[Dict[str, Any]] = []
    today = dt.date.today()
    for d in range(days):
        date = today - dt.timedelta(days=d + 1)    # skip today; today still in progress
        date_str = date.strftime("%Y%m%d")
        url = f"{BASE}/{espn_path}/scoreboard?dates={date_str}"
        sb = _http(url)
        if not sb:
            continue
        for ev in (sb.get("events") or []):
            summary = _summarize(ev, board_date=date.isoformat())
            if summary:
                out.append(summary)
    return {
        "sport": sport_key,
        "n_days_back": days,
        "n_games": len(out),
        "games": out,
    }


def run() -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for sport_key, espn_path, days in SPORTS:
        try:
            data = fetch_sport_history(sport_key, espn_path, days)
            out_path = os.path.join(DATA_DIR, f"historical_{sport_key}.json")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump({
                    "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    **data,
                }, f, indent=2)
            results[sport_key] = data["n_games"]
        except Exception as e:
            results[sport_key] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    print("Historical games pulled:")
    for sport, n in r.items():
        print(f"  {sport:8}: {n}")
