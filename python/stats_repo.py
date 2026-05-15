"""
EdgeStat — stats repository.

Thin, file-cached client around the MLB Stats API (free, no key). Gives us:
  - Team season-to-date hitting + pitching
  - Pitcher season, career, and vs L/R splits
  - Pitcher game log (used to derive pitcher-vs-team history this season)

All responses are cached under data/cache/stats/ with a 6-hour TTL so the daily
workflow runs in <30s without hammering MLB's servers.

Designed to fall back gracefully: if a call fails or returns no data, the
caller gets None or league-average defaults rather than an exception.
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


MLB_BASE = "https://statsapi.mlb.com/api/v1"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "stats")
CACHE_TTL_SEC = 6 * 3600   # 6 hours

# League baselines (approximate — used as fallback and to compute z-scores).
LEAGUE = {
    "ops": 0.720, "k9": 8.6, "bb9": 3.1, "era": 4.10, "whip": 1.30,
    "wrc_plus": 100, "babip": 0.295,
}


# -------------------- Cache layer --------------------

def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def _cache_get(name: str) -> Optional[Any]:
    p = _cache_path(name)
    if not os.path.exists(p):
        return None
    if time.time() - os.path.getmtime(p) > CACHE_TTL_SEC:
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _cache_put(name: str, data: Any) -> None:
    try:
        with open(_cache_path(name), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _get(url: str, cache_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    if cache_name:
        c = _cache_get(cache_name)
        if c is not None:
            return c
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if cache_name:
        _cache_put(cache_name, data)
    return data


# -------------------- Team lookup --------------------

_TEAMS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

def _teams() -> Dict[str, Dict[str, Any]]:
    """Map full team name -> {id, abbreviation, code}."""
    global _TEAMS_CACHE
    if _TEAMS_CACHE is not None:
        return _TEAMS_CACHE
    season = dt.date.today().year
    payload = _get(f"{MLB_BASE}/teams?sportId=1&season={season}", f"teams_{season}")
    out: Dict[str, Dict[str, Any]] = {}
    if payload:
        for t in payload.get("teams", []):
            out[t["name"]] = {"id": t["id"], "abbr": t.get("abbreviation", "")}
    _TEAMS_CACHE = out
    return out


def team_id(name: str) -> Optional[int]:
    return _teams().get(name, {}).get("id")


# -------------------- Team season stats --------------------

def team_season_stats(team_id_: int, season: Optional[int] = None) -> Dict[str, float]:
    """Return team's season hitting + pitching key rates. {} on failure."""
    season = season or dt.date.today().year
    out: Dict[str, float] = {}
    for group in ("hitting", "pitching"):
        payload = _get(
            f"{MLB_BASE}/teams/{team_id_}/stats?stats=season&group={group}&season={season}",
            f"team_{team_id_}_{group}_{season}",
        )
        if not payload or not payload.get("stats"):
            continue
        splits = payload["stats"][0].get("splits", [])
        if not splits:
            continue
        s = splits[0]["stat"]
        for k in ("ops", "obp", "slg", "avg", "runs",
                  "era", "whip", "strikeoutsPer9Inn", "walksPer9Inn",
                  "homeRunsPer9", "babip"):
            v = s.get(k)
            if v is None:
                continue
            try:
                out[f"{group[0]}_{k}"] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def team_offensive_index(team_id_: int) -> int:
    """Proxy for wRC+ from team OPS. League avg ~0.720 -> 100."""
    s = team_season_stats(team_id_)
    ops = s.get("h_ops")
    if ops is None:
        return LEAGUE["wrc_plus"]
    return int(round(100 + (ops - LEAGUE["ops"]) * 500))


def team_bullpen_delta(team_id_: int) -> float:
    """ERA - FIP-ish proxy for bullpen quality. Negative = good. Uses team pitching era vs league."""
    s = team_season_stats(team_id_)
    era = s.get("p_era")
    if era is None:
        return 0.0
    return round(era - LEAGUE["era"], 2)


# -------------------- Pitcher stats --------------------

def pitcher_id_by_name(name: str) -> Optional[int]:
    if not name:
        return None
    payload = _get(f"{MLB_BASE}/people/search?names={requests.utils.quote(name) if requests else name}", f"pid_{name}")
    if not payload:
        # Fallback: people search via different endpoint
        payload = _get(f"{MLB_BASE}/sports/1/players?names={name}", f"pid2_{name}")
    if not payload:
        return None
    for p in payload.get("people", []) or payload.get("players", []):
        return p.get("id")
    return None


def pitcher_season(pid: int, season: Optional[int] = None) -> Dict[str, Any]:
    season = season or dt.date.today().year
    payload = _get(
        f"{MLB_BASE}/people/{pid}/stats?stats=season&group=pitching&season={season}",
        f"psn_{pid}_{season}",
    )
    if not payload or not payload.get("stats"):
        return {}
    splits = payload["stats"][0].get("splits", [])
    if not splits:
        return {}
    return _coerce_stat(splits[0]["stat"])


def pitcher_career(pid: int) -> Dict[str, Any]:
    payload = _get(f"{MLB_BASE}/people/{pid}/stats?stats=career&group=pitching", f"pcar_{pid}")
    if not payload or not payload.get("stats"):
        return {}
    splits = payload["stats"][0].get("splits", [])
    if not splits:
        return {}
    return _coerce_stat(splits[0]["stat"])


def pitcher_splits(pid: int, season: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    """Return {'vsL': {...}, 'vsR': {...}} this season."""
    season = season or dt.date.today().year
    payload = _get(
        f"{MLB_BASE}/people/{pid}/stats?stats=statSplits&group=pitching&sitCodes=vl,vr&season={season}",
        f"psplit_{pid}_{season}",
    )
    out: Dict[str, Dict[str, Any]] = {}
    if not payload or not payload.get("stats"):
        return out
    for sp in payload["stats"][0].get("splits", []):
        code = sp.get("split", {}).get("code", "")
        if code == "vl":
            out["vsL"] = _coerce_stat(sp["stat"])
        elif code == "vr":
            out["vsR"] = _coerce_stat(sp["stat"])
    return out


def pitcher_gamelog(pid: int, season: Optional[int] = None) -> List[Dict[str, Any]]:
    season = season or dt.date.today().year
    payload = _get(
        f"{MLB_BASE}/people/{pid}/stats?stats=gameLog&group=pitching&season={season}",
        f"pgl_{pid}_{season}",
    )
    if not payload or not payload.get("stats"):
        return []
    out = []
    for g in payload["stats"][0].get("splits", []):
        out.append({
            "date": g.get("date"),
            "opponent_id": (g.get("opponent") or {}).get("id"),
            "opponent": (g.get("opponent") or {}).get("name"),
            "is_home": g.get("isHome", False),
            "stat": _coerce_stat(g["stat"]),
        })
    # Sort newest first
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    return out


def pitcher_vs_team(pid: int, opp_team_id: int) -> Dict[str, Any]:
    """Aggregate this season's starts against a specific opponent."""
    log = pitcher_gamelog(pid)
    rel = [g for g in log if g["opponent_id"] == opp_team_id]
    if not rel:
        return {"starts": 0}
    agg = {
        "starts": len(rel),
        "ip": round(sum(g["stat"].get("inningsPitched", 0) or 0 for g in rel), 1),
        "er": sum(int(g["stat"].get("earnedRuns", 0) or 0) for g in rel),
        "k": sum(int(g["stat"].get("strikeOuts", 0) or 0) for g in rel),
        "bb": sum(int(g["stat"].get("baseOnBalls", 0) or 0) for g in rel),
        "h": sum(int(g["stat"].get("hits", 0) or 0) for g in rel),
        "wins": sum(1 for g in rel if g.get("stat", {}).get("wins", 0)),
        "last_outing": rel[0].get("date"),
    }
    if agg["ip"] > 0:
        agg["era"] = round(agg["er"] * 9 / agg["ip"], 2)
        agg["k9"] = round(agg["k"] * 9 / agg["ip"], 2)
        agg["bb9"] = round(agg["bb"] * 9 / agg["ip"], 2)
        agg["whip"] = round((agg["h"] + agg["bb"]) / agg["ip"], 2)
    return agg


def pitcher_recent_form(pid: int, n: int = 3) -> Dict[str, Any]:
    """Roll-up of last N starts."""
    log = pitcher_gamelog(pid)
    # Filter to starts (IP >= 3) to exclude relief outings.
    starts = [g for g in log if (g["stat"].get("inningsPitched") or 0) >= 3]
    rel = starts[:n] if starts else log[:n]
    if not rel:
        return {}
    ip = sum(g["stat"].get("inningsPitched", 0) or 0 for g in rel)
    er = sum(int(g["stat"].get("earnedRuns", 0) or 0) for g in rel)
    k = sum(int(g["stat"].get("strikeOuts", 0) or 0) for g in rel)
    bb = sum(int(g["stat"].get("baseOnBalls", 0) or 0) for g in rel)
    out = {
        "starts": len(rel),
        "ip": round(ip, 1), "er": er, "k": k, "bb": bb,
        "era": round(er * 9 / ip, 2) if ip else None,
        "k9": round(k * 9 / ip, 2) if ip else None,
        "bb9": round(bb * 9 / ip, 2) if ip else None,
        "dates": [g["date"] for g in rel],
    }
    return out


def pitcher_vs_batter(pid: int, bid: int) -> Dict[str, Any]:
    """Career H2H stats: this pitcher vs this specific batter. Cached 7 days."""
    if not pid or not bid:
        return {}
    cache_name = f"pvb_{pid}_{bid}"
    cached = _cache_get(cache_name)
    if cached is not None:
        return cached
    payload = _get(
        f"{MLB_BASE}/people/{bid}/stats?stats=vsPlayer&opposingPlayerId={pid}&group=hitting",
        None,   # already managing cache here with longer TTL via custom key
    )
    out: Dict[str, Any] = {}
    if payload and payload.get("stats"):
        splits = payload["stats"][0].get("splits", [])
        if splits:
            s = _coerce_stat(splits[0]["stat"])
            ab = s.get("atBats")
            if ab and ab > 0:
                out = {
                    "ab": int(ab),
                    "hits": int(s.get("hits", 0) or 0),
                    "hr": int(s.get("homeRuns", 0) or 0),
                    "bb": int(s.get("baseOnBalls", 0) or 0),
                    "so": int(s.get("strikeOuts", 0) or 0),
                    "avg": s.get("avg"),
                    "obp": s.get("obp"),
                    "slg": s.get("slg"),
                    "ops": s.get("ops"),
                }
    _cache_put(cache_name, out)
    return out


def pitcher_hand(pid: int) -> str:
    """L or R from /people/{id}."""
    payload = _get(f"{MLB_BASE}/people/{pid}", f"phand_{pid}")
    if not payload or not payload.get("people"):
        return "R"
    return (payload["people"][0].get("pitchHand", {}) or {}).get("code", "R")


# -------------------- Probable pitcher resolution --------------------

def game_lineups(game_pk: int) -> Dict[str, Any]:
    """Return {'home': {batter_id: {name, order, pos}, ...}, 'away': {...}}.
    Empty until teams post lineups (~1-2 hours pre-game).
    Cached short (15 min) since lineups can update late.
    """
    # Short TTL so we pick up late lineup changes; use a non-stats cache slot.
    cache_name = f"lineup_{game_pk}"
    cache_path = _cache_path(cache_name)
    fresh = False
    if os.path.exists(cache_path):
        if time.time() - os.path.getmtime(cache_path) < 900:  # 15 min
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except Exception:
                pass
    payload = None
    if requests is not None:
        try:
            r = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", timeout=10)
            if r.ok:
                payload = r.json()
        except Exception:
            pass
    out: Dict[str, Any] = {"home": {}, "away": {}}
    if payload:
        for side in ("home", "away"):
            team = payload.get("teams", {}).get(side, {})
            order = team.get("battingOrder", []) or []
            for i, pid in enumerate(order):
                p = team.get("players", {}).get(f"ID{pid}", {})
                out[side][int(pid)] = {
                    "name": p.get("person", {}).get("fullName"),
                    "order": i + 1,
                    "pos": (p.get("position", {}) or {}).get("abbreviation"),
                }
    _cache_put(cache_name, out)
    return out


def player_is_in_lineup(pid: int, game_pk: int, home_team_id: Optional[int],
                       away_team_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Returns {side, order, pos} if confirmed in lineup, None if not, {} if no lineup posted yet."""
    lineups = game_lineups(game_pk)
    if not (lineups["home"] or lineups["away"]):
        return {}  # not posted yet -- caller should use heuristic
    for side in ("home", "away"):
        if pid in lineups[side]:
            entry = dict(lineups[side][pid])
            entry["side"] = side
            return entry
    return None  # lineup posted but player not in it (bench)


def probable_pitchers_for_game(game_pk: int) -> Dict[str, Dict[str, Any]]:
    """Return {'home': {id, name}, 'away': {id, name}} for a game."""
    payload = _get(
        f"{MLB_BASE}/schedule?sportId=1&gamePk={game_pk}&hydrate=probablePitcher",
        f"pp_{game_pk}",
    )
    out = {"home": {}, "away": {}}
    if not payload:
        return out
    for d in payload.get("dates", []):
        for g in d.get("games", []):
            for side in ("home", "away"):
                pp = (g["teams"][side] or {}).get("probablePitcher") or {}
                if pp:
                    out[side] = {"id": pp.get("id"), "name": pp.get("fullName")}
    return out


# -------------------- Helpers --------------------

def _coerce_stat(s: Dict[str, Any]) -> Dict[str, Any]:
    """Convert numeric-looking strings to floats. Leave non-numerics."""
    out: Dict[str, Any] = {}
    for k, v in s.items():
        if isinstance(v, (int, float)):
            out[k] = v
        elif isinstance(v, str):
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
        else:
            out[k] = v
    return out


if __name__ == "__main__":
    print("Smoke test stats_repo:")
    print("  teams:", len(_teams()))
    nyy = team_id("New York Yankees")
    print(f"  NYY id={nyy}")
    if nyy:
        s = team_season_stats(nyy)
        print(f"  NYY season stats keys: {sorted(s.keys())[:8]}")
        print(f"  NYY off index: {team_offensive_index(nyy)}")
