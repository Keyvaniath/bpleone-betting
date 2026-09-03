"""
EdgeStat -- college-football results cache (the CFB rating model's raw input).

Pulls every completed FBS game for a season from ESPN's free scoreboard and
caches it. The 2025 file is a SEED (committed, ~887 games) so a fresh clone /
CI runner can fit ratings without a 15-call backfill; the current season tops
up cheaply each run.

THE groups=80 TRAP (verified 2026-09-03): ESPN's college-football scoreboard
takes a `groups` filter. In the WEEK form (?dates=YYYY&seasontype=2&week=N)
omitting it returns a curated subset -- 16 events for a week that actually had
53. `groups=80` is the FBS group id and is MANDATORY for week queries. (The
DATE form, ?dates=YYYYMMDD, returns the full slate either way -- that's why
historical_games.py is unaffected.) Always pass limit=400: CFB Saturdays run
60+ games and the default page size truncates.

Honest fetching: EdgeStat/1.0 UA + Accept header, per the repo-wide rule --
never claim to be a browser.

Output: data/cfb_results_<season>.json
  {season, generated_at, n_games, games: [{
     date, week, season_type, neutral,
     home, home_id, home_name, home_score, home_rank,
     away, away_id, away_name, away_score, away_rank, is_fbs_matchup}]}
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
FBS_GROUP = 80          # ESPN's FBS group id -- REQUIRED on week queries
PAGE_LIMIT = 400        # CFB Saturdays exceed the default page size
REG_WEEKS = 16          # regular season (seasontype=2)
POST_WEEKS = 5          # bowls + playoff (seasontype=3)

HEADERS = {
    "User-Agent": "EdgeStat/1.0",
    "Accept": "application/json, text/plain, */*",
}


def _get(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _rank(competitor: Dict[str, Any]) -> Optional[int]:
    """AP/curated rank; ESPN uses 99 for unranked."""
    cur = (competitor.get("curatedRank") or {}).get("current")
    try:
        cur = int(cur)
    except (TypeError, ValueError):
        return None
    return None if cur >= 99 else cur


def _summarize(ev: Dict[str, Any], week: int, season_type: int,
               fbs_ids: set) -> Optional[Dict[str, Any]]:
    status = (ev.get("status") or {}).get("type") or {}
    if not status.get("completed"):
        return None
    comps = ev.get("competitions") or []
    if not comps:
        return None
    c = comps[0]
    competitors = c.get("competitors") or []
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    try:
        hs, as_ = int(home.get("score")), int(away.get("score"))
    except (TypeError, ValueError):
        return None
    ht, at = home.get("team") or {}, away.get("team") or {}
    h_id, a_id = str(ht.get("id") or ""), str(at.get("id") or "")
    return {
        "id": ev.get("id"),
        "date": str(ev.get("date") or "")[:10],
        "week": week,
        "season_type": season_type,
        "neutral": bool(c.get("neutralSite")),
        "home": (ht.get("abbreviation") or "").upper(),
        "home_id": h_id,
        "home_name": ht.get("displayName"),
        "home_score": hs,
        "home_rank": _rank(home),
        "away": (at.get("abbreviation") or "").upper(),
        "away_id": a_id,
        "away_name": at.get("displayName"),
        "away_score": as_,
        "away_rank": _rank(away),
        # An FBS team playing an FCS opponent shows up in the FBS group with a
        # non-FBS team id. The rating model must treat those differently (a
        # 55-0 win over an FCS side says almost nothing), so flag it here.
        "is_fbs_matchup": (h_id in fbs_ids and a_id in fbs_ids) if fbs_ids else None,
    }


CORE_BASE = ("https://sports.core.api.espn.com/v2/sports/football/leagues/"
             "college-football/seasons")


def fbs_team_ids(season: Optional[int] = None) -> set:
    """The REAL FBS team ids (~146), so FCS opponents can be flagged.

    THE TEAMS-ENDPOINT TRAP (verified 2026-09-03): the site API's
    /teams?groups=80 SILENTLY IGNORES the groups filter and returns all 760
    teams across every division -- using it flagged all 934 of 2025's games as
    FBS-vs-FBS when ~100 were against FCS opponents. The core API's
    seasons/<yr>/types/2/groups/80/teams IS filtered (146 teams); ids are
    parsed out of the $ref urls so this stays ONE call, not 147.

    Empty set on failure -- callers must treat is_fbs_matchup=None as
    'unknown' and never as False."""
    import re
    season = season or dt.date.today().year
    out = set()
    d = _get(f"{CORE_BASE}/{season}/types/2/groups/{FBS_GROUP}/teams?limit=400")
    if not d:
        return out
    for item in (d.get("items") or []):
        ref = item.get("$ref") or ""
        m = re.search(r"/teams/(\d+)", ref)
        if m:
            out.add(m.group(1))
    return out


def fetch_season(season: int, fbs_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    """Every completed FBS game of a season, regular + postseason."""
    if fbs_ids is None:
        fbs_ids = fbs_team_ids(season)
    games: List[Dict[str, Any]] = []
    seen = set()
    for season_type, n_weeks in ((2, REG_WEEKS), (3, POST_WEEKS)):
        for wk in range(1, n_weeks + 1):
            url = (f"{BASE}/scoreboard?dates={season}&seasontype={season_type}"
                   f"&week={wk}&groups={FBS_GROUP}&limit={PAGE_LIMIT}")
            d = _get(url)
            if not d:
                continue
            for ev in (d.get("events") or []):
                row = _summarize(ev, wk, season_type, fbs_ids)
                if row and row["id"] not in seen:
                    seen.add(row["id"])
                    games.append(row)
    games.sort(key=lambda g: (g["date"], g["id"]))
    return games


def out_path(season: int) -> str:
    return os.path.join(DATA_DIR, f"cfb_results_{season}.json")


def load(season: int) -> Dict[str, Any]:
    p = out_path(season)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run(season: int, force: bool = False) -> Dict[str, Any]:
    """Fetch + cache a season. NO-CLOBBER: a fetch that comes back with fewer
    games than the cache already holds is treated as an outage, not a season
    that shrank -- the existing cache is kept (same guard philosophy as
    player_gamelogs)."""
    prev = load(season)
    prev_games = prev.get("games") or []
    if prev_games and not force:
        # A completed past season never changes; only top up the live one.
        if season < dt.date.today().year:
            return prev
    games = fetch_season(season)
    if len(games) < len(prev_games):
        print(f"  [cfb-results] fetch returned {len(games)} < cached "
              f"{len(prev_games)} -- keeping cache (treating as outage)")
        return prev
    payload = {
        "season": season,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games),
        "source": "ESPN college-football scoreboard (free, groups=80 FBS)",
        "games": games,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path(season), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    import sys
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today().year
    force = "--force" in sys.argv
    p = run(yr, force=force)
    n_fbs = sum(1 for g in p.get("games") or [] if g.get("is_fbs_matchup"))
    print(f"[cfb-results] {yr}: {p.get('n_games', 0)} completed games "
          f"({n_fbs} FBS-vs-FBS) -> {out_path(yr)}")
