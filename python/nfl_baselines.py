"""
EdgeStat -- shared NFL player-baseline machinery.

One place for the name-normalization, roster/ESPN-id resolution, cached 2025
season baselines, and info-dict construction used by BOTH the props desk
(nfl_player_props) and the DFS desk (nfl_dfs). Extracted 2026-08-13 so the two
can't drift apart (nfl_dfs imports nfl_player_props for the simulator, so this
lives in its own module to avoid a circular import).

Baseline priority everywhere: curated NFL_PLAYER_DB priors > 2025 season
per-game rates (ESPN athlete statistics, cached once per player in
data/nfl_2025_baselines.json -- do not delete) > current-season gamelogs
(>= MIN_GP_CUR games; the rookie path, live once the season starts).
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE_CACHE = os.path.join(DATA_DIR, "nfl_2025_baselines.json")

MIN_GP_2025 = 6         # min 2025 games for a usable season baseline
MIN_GP_CUR = 3          # min current-season games for a gamelog-only baseline
FETCH_CAP = int(os.environ.get("NFL_DFS_FETCH_CAP", "120"))  # new fetches per run

H = {"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"}

_SKILL_POS = {"QB", "RB", "WR", "TE"}
_SUFFIXES = (" jr", " sr", " ii", " iii", " iv", " v")


def _get(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(p: str, obj: Any) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def norm_name(s: Any) -> str:
    n = re.sub(r"[^a-z ]", "", str(s or "").lower()).strip()
    for suf in _SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)].strip()
    return re.sub(r"\s+", " ", n)


def roster_index() -> Dict[str, List[Dict[str, Any]]]:
    """norm_name -> [{id, pos, team, name}] from rosters_nfl.json (collisions kept)."""
    idx: Dict[str, List[Dict[str, Any]]] = {}
    rost = _load(os.path.join(DATA_DIR, "rosters_nfl.json"))
    teams = rost.get("teams")
    teams_iter = teams.values() if isinstance(teams, dict) else (teams or [])
    for t in teams_iter:
        ab = (t.get("abbreviation") or "").upper()
        for pl in t.get("players") or []:
            idx.setdefault(norm_name(pl.get("name")), []).append(
                {"id": str(pl.get("id")), "pos": (pl.get("position") or "").upper(),
                 "team": ab, "name": pl.get("name")})
    return idx


def skill_players_by_team() -> Dict[str, List[Dict[str, Any]]]:
    """team abbrev -> [{id, pos, name, norm}] for QB/RB/WR/TE only."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    rost = _load(os.path.join(DATA_DIR, "rosters_nfl.json"))
    teams = rost.get("teams")
    teams_iter = teams.values() if isinstance(teams, dict) else (teams or [])
    for t in teams_iter:
        ab = (t.get("abbreviation") or "").upper()
        for pl in t.get("players") or []:
            pos = (pl.get("position") or "").upper()
            if pos in _SKILL_POS:
                out.setdefault(ab, []).append(
                    {"id": str(pl.get("id")), "pos": pos, "name": pl.get("name"),
                     "norm": norm_name(pl.get("name"))})
    return out


_STAT_KEEP = {
    "general": ("gamesPlayed", "fumblesLost"),
    "passing": ("passingYards", "passingTouchdowns", "interceptions",
                 "completions", "passingAttempts"),
    "rushing": ("rushingAttempts", "rushingYards", "rushingTouchdowns"),
    "receiving": ("receptions", "receivingTargets", "receivingYards",
                   "receivingTouchdowns"),
}


def _fetch_baseline(espn_id: str) -> Dict[str, Any]:
    url = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
           f"seasons/2025/types/2/athletes/{espn_id}/statistics")
    try:
        s = _get(url)
    except Exception:
        return {"no_data": True}
    out: Dict[str, Any] = {}
    for c in ((s.get("splits") or {}).get("categories")) or []:
        keep = _STAT_KEEP.get(c.get("name"))
        if not keep:
            continue
        for x in c.get("stats") or []:
            if x.get("name") in keep:
                out[x["name"]] = x.get("value")
    if not out.get("gamesPlayed"):
        return {"no_data": True}
    return out


def ensure_baselines(needed: List[Tuple[str, str]]) -> Dict[str, Any]:
    """needed = [(espn_id, display_name)]. Fetch at most FETCH_CAP new ids per
    run; cache everything (incl. no_data markers so rookies aren't re-fetched)."""
    cache = _load(BASE_CACHE)
    entries = cache.get("by_id") or {}
    fetched = 0
    for espn_id, name in needed:
        if espn_id in entries:
            continue
        if fetched >= FETCH_CAP:
            break
        bl = _fetch_baseline(espn_id)
        bl["name"] = name
        entries[espn_id] = bl
        fetched += 1
    if fetched:
        _write(BASE_CACHE, {"season": 2025,
                            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                            "n_players": len(entries), "by_id": entries})
        print(f"[nfl-baselines] fetched {fetched} new 2025 baselines (cache: {len(entries)})")
    return entries


def info_from_2025(bl: Dict[str, Any], pos: str) -> Optional[Dict[str, Any]]:
    gp = bl.get("gamesPlayed") or 0
    if gp < MIN_GP_2025:
        return None
    info: Dict[str, Any] = {"pos": pos}
    pass_y = (bl.get("passingYards") or 0) / gp
    rush_y = (bl.get("rushingYards") or 0) / gp
    rec_y = (bl.get("receivingYards") or 0) / gp
    rec = (bl.get("receptions") or 0) / gp
    if pos == "QB" and pass_y >= 60:
        info["pass_yds"] = round(pass_y, 1)
        info["pass_td"] = round((bl.get("passingTouchdowns") or 0) / gp, 2)
    if rush_y >= 8:
        info["rush_yds"] = round(rush_y, 1)
    if rec >= 1.2 and rec_y >= 8:
        info["rec"] = round(rec, 2)
        info["rec_yds"] = round(rec_y, 1)
    tds = ((bl.get("rushingTouchdowns") or 0) + (bl.get("receivingTouchdowns") or 0)) / gp
    if "rush_yds" in info or "rec_yds" in info:
        info["td_rate"] = round(tds, 2)
    return info if any(k in info for k in ("pass_yds", "rush_yds", "rec_yds")) else None


def info_from_gamelogs(gl_rows: List[Dict[str, Any]], pos: str) -> Optional[Dict[str, Any]]:
    """Current-season fallback baseline (covers rookies once they have games)."""
    if len(gl_rows) < MIN_GP_CUR:
        return None
    n = len(gl_rows)
    avg = lambda k: sum(float(g.get(k) or 0) for g in gl_rows) / n
    info: Dict[str, Any] = {"pos": pos}
    if pos == "QB" and avg("pass_yds") >= 60:
        info["pass_yds"] = round(avg("pass_yds"), 1)
        info["pass_td"] = round(avg("pass_td"), 2)
    if avg("rush_yds") >= 8:
        info["rush_yds"] = round(avg("rush_yds"), 1)
    if avg("rec") >= 1.2:
        info["rec"] = round(avg("rec"), 2)
        info["rec_yds"] = round(avg("rec_yds"), 1)
    if "rush_yds" in info or "rec_yds" in info:
        info["td_rate"] = round(avg("rush_td") + avg("rec_td"), 2)
    return info if any(k in info for k in ("pass_yds", "rush_yds", "rec_yds")) else None


def resolve_info(norm: str, pos: str, espn_id: Optional[str],
                 baselines: Dict[str, Any], gl_all: Dict[str, Any],
                 curated_db: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """The one shared resolution ladder -> (info, source) or (None, None)."""
    info: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    bl = baselines.get(espn_id) if espn_id else None
    if bl and not bl.get("no_data"):
        info = info_from_2025(bl, pos)
        source = "season2025" if info else None
    db_info = curated_db.get(norm)
    if db_info:
        info = dict(info or {})
        info.update(db_info)          # curated priors win on conflicts
        source = "curated+2025" if source else "curated"
    if info is None:
        gl_rows = gl_all.get(norm)
        gl_rows = gl_rows if isinstance(gl_rows, list) else ((gl_rows or {}).get("games") or [])
        info = info_from_gamelogs(gl_rows, pos)
        source = "gamelogs" if info else None
    return info, source
