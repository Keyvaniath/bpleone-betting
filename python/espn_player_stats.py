"""
EdgeStat -- per-player game logs + season stats from ESPN.

For each team's top players (first 10 on roster), pulls game log and computes
real per-game averages. These are LIVE per-game numbers, not heuristics.

Sport-specific stat columns vary; we normalize to a common shape:
  - pts (basketball/hockey goals + assists for hockey)
  - reb / ast / 3pm (basketball)
  - shots / saves (hockey)
  - games_played, total_pts

Output: data/player_stats_<sport>.json
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/{path}/athletes/{aid}/gamelog"

SPORTS = [
    ("nba",  "basketball/nba",  12),     # 12 deep per roster
    ("wnba", "basketball/wnba", 10),
    ("nhl",  "hockey/nhl",      12),
]

# NBA / WNBA stat-line indexes (column order from gamelog labels):
# MIN, FG, FG%, 3PT, 3P%, FT, FT%, REB, AST, BLK, STL, TO, PF, PTS
BASKETBALL_IDX = {"min": 0, "fg": 1, "fg_pct": 2, "3pt": 3, "3p_pct": 4,
                   "ft": 5, "ft_pct": 6, "reb": 7, "ast": 8, "blk": 9,
                   "stl": 10, "to": 11, "pf": 12, "pts": 13}

# NHL skater stats: G, A, +/-, SOG, S%, PIM, GWG, PPG, SHG, HT
HOCKEY_IDX = {"goals": 0, "assists": 1, "plus_minus": 2, "shots": 3,
              "shot_pct": 4, "pim": 5, "gwg": 6, "ppg": 7, "shg": 8, "hits": 9}


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _to_float(s):
    try: return float(s)
    except Exception: return 0.0


def _to_int(s):
    try: return int(s)
    except Exception: return 0


def _parse_made(s):
    """'8-18' -> made=8, att=18"""
    try:
        parts = str(s).split("-")
        return _to_int(parts[0]), _to_int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 0, 0


def parse_basketball_log(gamelog: Dict[str, Any], player_name: str) -> Dict[str, Any]:
    """Compute per-game averages from a basketball player's game log."""
    seasons = gamelog.get("seasonTypes") or []
    # Aggregate across regular season + postseason (most recent N games)
    all_event_stats = []
    for season in seasons:
        for cat in (season.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats")
                if stats and len(stats) >= 14:
                    all_event_stats.append(stats)
    if not all_event_stats:
        return None
    # Take last 20 games for "recent form"
    last_n = all_event_stats[:20]
    n = len(last_n)
    pts_avg = sum(_to_float(s[BASKETBALL_IDX["pts"]]) for s in last_n) / n
    reb_avg = sum(_to_float(s[BASKETBALL_IDX["reb"]]) for s in last_n) / n
    ast_avg = sum(_to_float(s[BASKETBALL_IDX["ast"]]) for s in last_n) / n
    threes_made = sum(_parse_made(s[BASKETBALL_IDX["3pt"]])[0] for s in last_n) / n
    min_avg = sum(_to_float(s[BASKETBALL_IDX["min"]]) for s in last_n) / n
    fg_pct = sum(_to_float(s[BASKETBALL_IDX["fg_pct"]]) for s in last_n) / n
    return {
        "name": player_name,
        "n_games": n,
        "min_per_game": round(min_avg, 1),
        "pts_per_game": round(pts_avg, 2),
        "reb_per_game": round(reb_avg, 2),
        "ast_per_game": round(ast_avg, 2),
        "threes_per_game": round(threes_made, 2),
        "fg_pct": round(fg_pct, 1),
    }


def parse_hockey_log(gamelog: Dict[str, Any], player_name: str) -> Dict[str, Any]:
    seasons = gamelog.get("seasonTypes") or []
    all_event_stats = []
    for season in seasons:
        for cat in (season.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats")
                if stats and len(stats) >= 4:
                    all_event_stats.append(stats)
    if not all_event_stats:
        return None
    last_n = all_event_stats[:20]
    n = len(last_n)
    goals_avg = sum(_to_float(s[HOCKEY_IDX["goals"]]) for s in last_n) / n
    assists_avg = sum(_to_float(s[HOCKEY_IDX["assists"]]) for s in last_n) / n
    shots_avg = sum(_to_float(s[HOCKEY_IDX["shots"]]) for s in last_n) / n
    return {
        "name": player_name,
        "n_games": n,
        "goals_per_game": round(goals_avg, 2),
        "assists_per_game": round(assists_avg, 2),
        "shots_per_game": round(shots_avg, 2),
        "points_per_game": round(goals_avg + assists_avg, 2),
    }


def fetch_sport(sport_key: str, espn_path: str, top_per_team: int) -> Dict[str, Any]:
    rosters = _load(os.path.join(DATA_DIR, f"rosters_{sport_key}.json"))
    teams = rosters.get("teams") or {}
    player_logs: List[Dict[str, Any]] = []
    pulled = 0
    parse_fn = parse_basketball_log if sport_key in ("nba", "wnba") else parse_hockey_log
    for team_id, tb in teams.items():
        # Take first `top_per_team` players (roster order = depth)
        for p in (tb.get("players") or [])[:top_per_team]:
            aid = p.get("id")
            if not aid: continue
            gamelog = _http(GAMELOG_URL.format(path=espn_path, aid=aid))
            if not gamelog: continue
            parsed = parse_fn(gamelog, p["name"])
            if parsed:
                parsed["athlete_id"] = aid
                parsed["team"] = tb["name"]
                parsed["team_abbr"] = tb.get("abbreviation")
                parsed["position"] = p.get("position")
                player_logs.append(parsed)
                pulled += 1
            time.sleep(0.04)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        "n_players_with_logs": len(player_logs),
        "players": player_logs,
    }
    out_path = os.path.join(DATA_DIR, f"player_stats_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, int]:
    results = {}
    for sport_key, espn_path, top_per_team in SPORTS:
        try:
            p = fetch_sport(sport_key, espn_path, top_per_team)
            results[sport_key] = p["n_players_with_logs"]
        except Exception as e:
            results[sport_key] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    for sport, n in r.items():
        print(f"  {sport}: {n} players with real per-game logs")
