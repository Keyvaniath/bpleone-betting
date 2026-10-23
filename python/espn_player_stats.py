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

# NBA / WNBA gamelog stats use DIFFERENT column orders -- this caused
# player_stats_wnba.json to silently corrupt PPG (read PF as PTS).
# Verified via live ESPN call 2026-05-19: WNBA labels =
#   MIN(0) PTS(1) REB(2) AST(3) STL(4) BLK(5) TO(6) FG(7) FG%(8) 3PT(9) 3P%(10) FT(11) FT%(12) PF(13)
# NBA labels =
#   MIN(0) FG(1) FG%(2) 3PT(3) 3P%(4) FT(5) FT%(6) REB(7) AST(8) BLK(9) STL(10) TO(11) PF(12) PTS(13)
NBA_IDX = {"min": 0, "fg": 1, "fg_pct": 2, "3pt": 3, "3p_pct": 4,
            "ft": 5, "ft_pct": 6, "reb": 7, "ast": 8, "blk": 9,
            "stl": 10, "to": 11, "pf": 12, "pts": 13}
WNBA_IDX = {"min": 0, "pts": 1, "reb": 2, "ast": 3, "stl": 4, "blk": 5,
             "to": 6, "fg": 7, "fg_pct": 8, "3pt": 9, "3p_pct": 10,
             "ft": 11, "ft_pct": 12, "pf": 13}
BASKETBALL_IDX = NBA_IDX   # legacy default; parse_basketball_log uses sport-aware

# NHL skater gamelog labels (verified live 2026-05-20):
#   G A PTS +/- PIM S SPCT PPG PPA SHG SHA GWG TOI/G PROD
#    0 1  2   3   4 5  6    7   8   9  10  11   12   13
# Previous code had shots=3 which is actually +/-, causing shots/game
# to read +/- and goals/game to be reasonable. Critical bug for any
# downstream that used SOG (real_player_props_nhl etc).
HOCKEY_IDX = {"goals": 0, "assists": 1, "points": 2, "plus_minus": 3,
              "pim": 4, "shots": 5, "shot_pct": 6, "ppg": 7,
              "ppa": 8, "shg": 9, "sha": 10, "gwg": 11}


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
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


def parse_basketball_log(gamelog: Dict[str, Any], player_name: str,
                          sport_key: str = "nba") -> Dict[str, Any]:
    """Compute per-game averages from a basketball player's game log.

    sport_key MUST be 'nba' or 'wnba' -- the gamelog stat-array column order
    differs between the two leagues (see NBA_IDX/WNBA_IDX above). Calling
    this with the wrong sport_key silently corrupts PPG.
    """
    idx = WNBA_IDX if sport_key == "wnba" else NBA_IDX
    seasons = _no_preseason(gamelog.get("seasonTypes") or [])
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
    pts_avg = sum(_to_float(s[idx["pts"]]) for s in last_n) / n
    reb_avg = sum(_to_float(s[idx["reb"]]) for s in last_n) / n
    ast_avg = sum(_to_float(s[idx["ast"]]) for s in last_n) / n
    threes_made = sum(_parse_made(s[idx["3pt"]])[0] for s in last_n) / n
    min_avg = sum(_to_float(s[idx["min"]]) for s in last_n) / n
    fg_pct = sum(_to_float(s[idx["fg_pct"]]) for s in last_n) / n
    # 2026-05-21: extended for data-accuracy push — these unlock the
    # hardcoded turnover / FTA / blocks / steals prop modules.
    tov_avg = sum(_to_float(s[idx["to"]]) for s in last_n) / n
    blk_avg = sum(_to_float(s[idx["blk"]]) for s in last_n) / n
    stl_avg = sum(_to_float(s[idx["stl"]]) for s in last_n) / n
    # FT column is "made-attempted" string like "8-10"
    ft_made_avg = sum(_parse_made(s[idx["ft"]])[0] for s in last_n) / n
    fta_avg = sum(_parse_made(s[idx["ft"]])[1] for s in last_n) / n
    return {
        "name": player_name,
        "n_games": n,
        "min_per_game": round(min_avg, 1),
        "pts_per_game": round(pts_avg, 2),
        "reb_per_game": round(reb_avg, 2),
        "ast_per_game": round(ast_avg, 2),
        "threes_per_game": round(threes_made, 2),
        "fg_pct": round(fg_pct, 1),
        # Extended stats (new 2026-05-21)
        "tov_per_game": round(tov_avg, 2),
        "blk_per_game": round(blk_avg, 2),
        "stl_per_game": round(stl_avg, 2),
        "ft_made_per_game": round(ft_made_avg, 2),
        "fta_per_game": round(fta_avg, 2),
    }


def parse_hockey_log(gamelog: Dict[str, Any], player_name: str) -> Dict[str, Any]:
    seasons = _no_preseason(gamelog.get("seasonTypes") or [])
    all_event_stats = []
    for season in seasons:
        for cat in (season.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats")
                # NHL gamelog rows have ~14 stat columns
                if stats and len(stats) >= 12:
                    all_event_stats.append(stats)
    if not all_event_stats:
        return None
    last_n = all_event_stats[:20]
    n = len(last_n)
    goals_avg = sum(_to_float(s[HOCKEY_IDX["goals"]]) for s in last_n) / n
    assists_avg = sum(_to_float(s[HOCKEY_IDX["assists"]]) for s in last_n) / n
    points_avg = sum(_to_float(s[HOCKEY_IDX["points"]]) for s in last_n) / n
    shots_avg = sum(_to_float(s[HOCKEY_IDX["shots"]]) for s in last_n) / n
    plus_minus_avg = sum(_to_float(s[HOCKEY_IDX["plus_minus"]]) for s in last_n) / n
    return {
        "name": player_name,
        "n_games": n,
        "goals_per_game": round(goals_avg, 2),
        "assists_per_game": round(assists_avg, 2),
        "points_per_game": round(points_avg, 2),
        "shots_per_game": round(shots_avg, 2),
        "plus_minus_per_game": round(plus_minus_avg, 2),
    }


# ---------------------------------------------------------------------------
# PRIOR-SEASON BLEND (2026-10-23)
# ---------------------------------------------------------------------------
# The athlete gamelog returns the CURRENT season only, preseason included. Two
# days into the 2026-27 NBA season every average was built from 1-2
# regular-season games plus preseason minutes (Luka: 1 + 3), and anyone under
# the generators' 5-game floor fell back to hard-coded 2024-25 tables. Now:
# preseason is dropped, last season's full regular-season averages are the
# prior (one bulk call per league), and this season blends in by games
# played, w = n/(n+K). K was MEASURED on 2025-26 (prior = 2024-25, predict the
# next 10 games from the first n): NBA K=5 best or near-best for pts/reb/ast
# at n=1..20 (after 1 game: current-only RMSE 6.45 pts vs 3.57 blended); NHL
# skaters want far more prior, K~20-40 (goals even favour the prior alone),
# so 30. WNBA uses the basketball K.
BLEND_K = {"nba": 5.0, "wnba": 5.0, "nhl": 30.0}
BULK_URL = ("https://site.web.api.espn.com/apis/common/v3/sports/{path}/statistics/byathlete"
            "?region=us&lang=en&contentorigin=espn&isqualified=false&limit=50&page={page}"
            "&seasontype=2{season_q}")
# ESPN abbreviations -> the generators' vocabulary (PLAYER_DB team keys).
MODEL_TEAM = {
    "nba": {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"},
    "nhl": {"LA": "LAK", "NJ": "NJD", "SJ": "SJS", "TB": "TBL", "UTAH": "UTA"},
    "wnba": {},
}
# bulk field -> our per-game key (basketball fields are already averages;
# hockey fields are season totals, divided by games below)
_BB_PRIOR = {"avgPoints": "pts_per_game", "avgRebounds": "reb_per_game",
             "avgAssists": "ast_per_game", "avgThreePointFieldGoalsMade": "threes_per_game",
             "avgMinutes": "min_per_game", "avgTurnovers": "tov_per_game",
             "avgBlocks": "blk_per_game", "avgSteals": "stl_per_game",
             "avgFreeThrowsMade": "ft_made_per_game", "avgFreeThrowsAttempted": "fta_per_game",
             "fieldGoalPct": "fg_pct"}
_HK_PRIOR = {"goals": "goals_per_game", "assists": "assists_per_game",
             "points": "points_per_game", "shotsTotal": "shots_per_game",
             "plusMinus": "plus_minus_per_game"}


def _no_preseason(season_types: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in season_types if "preseason" not in str(t.get("displayName") or "").lower()]


def _current_season(espn_path: str) -> Optional[int]:
    d = _http(BULK_URL.format(path=espn_path, page=1, season_q="")) or {}
    try:
        return int((d.get("currentSeason") or d.get("requestedSeason") or {}).get("year"))
    except Exception:
        return None


def fetch_prior(sport_key: str, espn_path: str, season: int) -> Dict[str, Dict[str, float]]:
    """{athlete_id: {gp, <per-game keys>}} for a completed regular season."""
    out: Dict[str, Dict[str, float]] = {}
    hockey = sport_key == "nhl"
    for page in range(1, 40):
        d = _http(BULK_URL.format(path=espn_path, page=page, season_q=f"&season={season}")) or {}
        names = {c.get("name"): c.get("names") or [] for c in (d.get("categories") or [])}
        for a in d.get("athletes") or []:
            vals: Dict[str, float] = {}
            for c in a.get("categories") or []:
                for k, v in zip(names.get(c.get("name"), []), c.get("totals") or []):
                    f = _to_float(v)
                    if f is not None:
                        vals[k] = f
            gp = vals.get("games" if hockey else "gamesPlayed") or 0
            if not gp:
                continue
            rec: Dict[str, float] = {"gp": gp}
            for src, dst in (_HK_PRIOR if hockey else _BB_PRIOR).items():
                if src in vals:
                    rec[dst] = round(vals[src] / gp, 3) if hockey else vals[src]
            out[str((a.get("athlete") or {}).get("id"))] = rec
        if page >= int((d.get("pagination") or {}).get("pages") or 0):
            break
        time.sleep(0.05)
    return out


def blend_record(cur: Optional[Dict[str, Any]], prior: Optional[Dict[str, float]],
                 k: float) -> Optional[Dict[str, Any]]:
    """Season-to-date averages shrunk toward last season by games played."""
    if not cur and not prior:
        return None
    n = int((cur or {}).get("n_games") or 0)
    w = n / (n + k) if n else 0.0
    out = dict(cur or {})
    out["n_games"] = n
    if prior:
        keys = {k_ for k_ in prior if k_ != "gp"}
        out["current"] = {k_: (cur or {}).get(k_) for k_ in keys if (cur or {}).get(k_) is not None}
        for k_ in keys:
            c_, p_ = (cur or {}).get(k_), prior.get(k_)
            if p_ is None:
                continue
            out[k_] = round(p_ if (c_ is None or not n) else w * c_ + (1 - w) * p_, 3)
        out["prior_gp"] = int(prior.get("gp") or 0)
        out["blend_w_current"] = round(w, 3)
        out["blend_k"] = k
        out["blended"] = True
    return out


def fetch_sport(sport_key: str, espn_path: str, top_per_team: int) -> Dict[str, Any]:
    """Per-game averages for EVERY rostered player: this season's regular-season
    numbers shrunk toward last season's (blend_record).

    BULK, NOT PER-PLAYER (2026-10-23): this used to pull one gamelog per player
    for the first `top_per_team` names on each roster -- but roster order is not
    depth, so stars were simply missing (Cale Makar, Sabonis, De'Aaron Fox) and
    fell back to hard-coded 2024-25 tables, while the gamelog mixed preseason
    into the averages. ESPN's statistics/byathlete endpoint returns every
    player's regular-season averages for a season in ~10-20 paged calls, so the
    current season and the prior come from the same source. `top_per_team` is
    kept for the signature only."""
    rosters = _load(os.path.join(DATA_DIR, f"rosters_{sport_key}.json"))
    teams = rosters.get("teams") or {}
    season = _current_season(espn_path)
    current = fetch_prior(sport_key, espn_path, season) if season else {}
    prior = fetch_prior(sport_key, espn_path, season - 1) if season else {}
    k = BLEND_K.get(sport_key, 5.0)
    tmap = MODEL_TEAM.get(sport_key) or {}
    player_logs: List[Dict[str, Any]] = []
    for team_id, tb in teams.items():
        ab = str(tb.get("abbreviation") or "").upper()
        for p in (tb.get("players") or []):
            aid = str(p.get("id") or "")
            if not aid:
                continue
            cur = current.get(aid)
            cur_rec = None
            if cur:
                cur_rec = {kk: vv for kk, vv in cur.items() if kk != "gp"}
                cur_rec["n_games"] = int(cur.get("gp") or 0)
            rec = blend_record(cur_rec, prior.get(aid), k)
            if not rec:
                continue                      # rookie with no games yet: nothing to say
            rec.update({"name": p.get("name"), "athlete_id": aid, "team": tb.get("name"),
                        "team_abbr": tb.get("abbreviation"), "team_model": tmap.get(ab, ab),
                        "position": p.get("position")})
            player_logs.append(rec)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        "n_players_with_logs": len(player_logs),
        "season": season,
        "prior_season": (season - 1) if season else None,
        "n_current_players": len(current),
        "n_prior_players": len(prior),
        "blend": {"k": k, "formula": "w = n/(n+k); value = w*current + (1-w)*prior; regular season only"},
        "players": player_logs,
    }
    out_path = os.path.join(DATA_DIR, f"player_stats_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    # Never clobber a useful file with an empty fetch (ESPN hiccup).
    if not player_logs and os.path.exists(out_path):
        return dict(payload, n_players_with_logs=0, note="empty fetch -- kept previous file")
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
