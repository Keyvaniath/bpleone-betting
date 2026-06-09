"""
EdgeStat -- FREE book odds feed from ESPN.

The paid The Odds API key (ODDS_API_KEY) is lapsed, which froze the book-vs-model
edges / line movement / CLV on stale lines. ESPN's public scoreboard API carries
live sportsbook odds (DraftKings) -- moneyline, total, and spread -- for free, no
key required. The site already uses ESPN's free endpoints for results
(espn_event_results, espn_box_logs), so this just adds the odds they also expose.

This removes the hard dependency on a paid key: fresh, comprehensive game odds for
every game on the slate, every pipeline run.

Output: data/espn_odds.json  -- matchup-keyed ("AWAY @ HOME" abbreviations) so it
joins straight onto matchups.json / today.json, consumed by book_vs_model_team.py.

Usage: python espn_odds.py [sport ...]   (default: mlb)
"""
from __future__ import annotations

import os
import sys
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "espn_odds.json")

# ESPN scoreboard path per sport (free, no key). Extensible -- add a row to cover
# another league's odds.
SPORT_PATHS = {
    "mlb": "baseball/mlb",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "nhl": "hockey/nhl",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "ncaab": "basketball/mens-college-basketball",
}

# ESPN uses a few different team abbreviations than this codebase's model side
# (today.json / matchups.json / prop files). Normalize ESPN -> model so the
# "AWAY @ HOME" matchup key joins straight onto the model. Confirmed from the
# model's own vocabulary across data/.
ESPN_TO_MODEL = {
    "mlb": {"TB": "TBR", "KC": "KCR", "SD": "SDP", "WSH": "WSN", "SF": "SFG",
            "ATH": "OAK", "AZ": "ARI"},
}


def _norm(sport: str, abbr: Optional[str]) -> Optional[str]:
    if not abbr:
        return abbr
    return ESPN_TO_MODEL.get(sport, {}).get(abbr.upper(), abbr.upper())


def _get(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EdgeStat)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _am(v) -> Optional[int]:
    """ESPN odds come as strings like '+103' / '-124' / 'EVEN'."""
    if v is None:
        return None
    s = str(v).strip().upper().replace("EVEN", "+100")
    try:
        return int(s.replace("+", ""))
    except ValueError:
        return None


def _deep(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def fetch_sport(sport: str) -> List[Dict[str, Any]]:
    path = SPORT_PATHS.get(sport)
    if not path:
        return []
    try:
        data = _get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard")
    except Exception as e:
        print(f"[espn-odds] {sport} fetch failed: {e!r}")
        return []
    out: List[Dict[str, Any]] = []
    for e in (data.get("events") or []):
        comp = (e.get("competitions") or [{}])[0]
        teams = {t.get("homeAway"): t for t in (comp.get("competitors") or [])}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        home_ab = _norm(sport, _deep(home, "team", "abbreviation"))
        away_ab = _norm(sport, _deep(away, "team", "abbreviation"))
        if not home_ab or not away_ab:
            continue
        odds_list = comp.get("odds") or []
        o = odds_list[0] if odds_list else {}
        ml = o.get("moneyline") or {}
        tot = o.get("total") or {}
        ml_home = _am(_deep(ml, "home", "close", "odds") or _deep(ml, "home", "open", "odds"))
        ml_away = _am(_deep(ml, "away", "close", "odds") or _deep(ml, "away", "open", "odds"))
        over_px = _am(_deep(tot, "over", "close", "odds") or _deep(tot, "over", "open", "odds"))
        under_px = _am(_deep(tot, "under", "close", "odds") or _deep(tot, "under", "open", "odds"))
        status = _deep(comp, "status", "type", "state")  # pre / in / post
        out.append({
            "sport": sport.upper(),
            "matchup": f"{away_ab} @ {home_ab}",
            "away": away_ab,
            "home": home_ab,
            "commence_time": e.get("date"),
            "status": status,
            "provider": _deep(o, "provider", "name"),
            "market": {
                "ml_home": ml_home,
                "ml_away": ml_away,
                "total": o.get("overUnder"),
                "over_price": over_px,
                "under_price": under_px,
                "spread": o.get("spread"),
                "book": (_deep(o, "provider", "name") or "espn").lower().replace(" ", ""),
            },
        })
    return out


def run(sports: Optional[List[str]] = None) -> Dict[str, Any]:
    sports = sports or ["mlb"]
    games: List[Dict[str, Any]] = []
    for s in sports:
        games.extend(fetch_sport(s))
    priced = [g for g in games if g["market"]["ml_home"] is not None and g["market"]["ml_away"] is not None]
    by_matchup = {g["matchup"]: g["market"] for g in priced}
    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "source": "espn-scoreboard (free, no key)",
        "sports": [s.upper() for s in sports],
        "n_games": len(games),
        "n_priced": len(priced),
        "by_matchup": by_matchup,
        "games": games,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]] or ["mlb"]
    o = run(args)
    print(f"[espn-odds] {o['n_priced']}/{o['n_games']} games priced "
          f"({', '.join(o['sports'])}) -> {OUT}")
    for g in o["games"][:8]:
        m = g["market"]
        if m["ml_home"] is not None:
            print(f"    {g['matchup']:12s} {g['sport']:4s} away {m['ml_away']:+d} / home {m['ml_home']:+d} "
                  f"| O/U {m['total']} ({m['over_price']:+d}/{m['under_price']:+d}) [{m['book']}]")
