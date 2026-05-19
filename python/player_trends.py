"""
EdgeStat -- player trend detector (L5 vs L20 hot/cold).

For each player with real game logs, compares last-5-game performance to
last-20-game baseline. Flags players who are:
  - HEATING UP: L5 pts/game >= 1.15x L20 baseline (15% improvement)
  - COOLING DOWN: L5 pts/game <= 0.85x L20 baseline (15% drop)
  - STABLE: in between

For each trending player, recomputes prop projections using a blended
(0.6 * L5 + 0.4 * L20) mean instead of pure L20. This produces sharper
prop edges on players whose form has shifted.

Output: data/player_trends_<sport>.json
"""
from __future__ import annotations

import os
import json
import math
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/{path}/athletes/{aid}/gamelog"

SPORTS = [
    ("nba",  "basketball/nba"),
    ("wnba", "basketball/wnba"),
    ("nhl",  "hockey/nhl"),
]

# NBA and WNBA gamelog stat-array column orders DIFFER -- see espn_player_stats.py
# for the detailed comparison. Using NBA indices on WNBA data corrupts PPG.
NBA_IDX = {"min": 0, "fg": 1, "fg_pct": 2, "3pt": 3, "3p_pct": 4,
            "ft": 5, "ft_pct": 6, "reb": 7, "ast": 8, "blk": 9,
            "stl": 10, "to": 11, "pf": 12, "pts": 13}
WNBA_IDX = {"min": 0, "pts": 1, "reb": 2, "ast": 3, "stl": 4, "blk": 5,
             "to": 6, "fg": 7, "fg_pct": 8, "3pt": 9, "3p_pct": 10,
             "ft": 11, "ft_pct": 12, "pf": 13}
BASKETBALL_IDX = NBA_IDX   # legacy default; _basketball_trend uses sport-aware idx
HOCKEY_IDX = {"goals": 0, "assists": 1, "plus_minus": 2, "shots": 3}


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


def _all_event_stats(gamelog: Dict[str, Any]) -> List[List[str]]:
    out = []
    for s in (gamelog.get("seasonTypes") or []):
        for cat in (s.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats")
                if stats and len(stats) >= 4:
                    out.append(stats)
    return out


def _basketball_trend(stats: List[List[str]], sport_key: str = "nba") -> Dict[str, Any]:
    """sport_key must be 'nba' or 'wnba' -- gamelog stat columns differ."""
    idx = WNBA_IDX if sport_key == "wnba" else NBA_IDX
    if len(stats) < 8: return {}
    l5 = stats[:5]
    l20 = stats[:20] if len(stats) >= 20 else stats[:len(stats)]
    if not l5 or not l20: return {}
    pts_l5 = sum(_to_float(s[idx["pts"]]) for s in l5) / len(l5)
    pts_l20 = sum(_to_float(s[idx["pts"]]) for s in l20) / len(l20)
    reb_l5 = sum(_to_float(s[idx["reb"]]) for s in l5) / len(l5)
    reb_l20 = sum(_to_float(s[idx["reb"]]) for s in l20) / len(l20)
    ast_l5 = sum(_to_float(s[idx["ast"]]) for s in l5) / len(l5)
    ast_l20 = sum(_to_float(s[idx["ast"]]) for s in l20) / len(l20)
    return {
        "pts_l5": round(pts_l5, 2), "pts_l20": round(pts_l20, 2),
        "reb_l5": round(reb_l5, 2), "reb_l20": round(reb_l20, 2),
        "ast_l5": round(ast_l5, 2), "ast_l20": round(ast_l20, 2),
        "pts_delta_pct": round(((pts_l5 - pts_l20) / max(0.1, pts_l20)) * 100, 1),
        "blended_pts": round(0.6 * pts_l5 + 0.4 * pts_l20, 2),
        "blended_reb": round(0.6 * reb_l5 + 0.4 * reb_l20, 2),
        "blended_ast": round(0.6 * ast_l5 + 0.4 * ast_l20, 2),
    }


def _hockey_trend(stats: List[List[str]]) -> Dict[str, Any]:
    if len(stats) < 8: return {}
    l5 = stats[:5]
    l20 = stats[:20] if len(stats) >= 20 else stats[:len(stats)]
    pts_l5 = sum((_to_float(s[0]) + _to_float(s[1])) for s in l5) / len(l5)
    pts_l20 = sum((_to_float(s[0]) + _to_float(s[1])) for s in l20) / len(l20)
    sog_l5 = sum(_to_float(s[3]) for s in l5) / len(l5)
    sog_l20 = sum(_to_float(s[3]) for s in l20) / len(l20)
    return {
        "pts_l5": round(pts_l5, 2), "pts_l20": round(pts_l20, 2),
        "sog_l5": round(sog_l5, 2), "sog_l20": round(sog_l20, 2),
        "pts_delta_pct": round(((pts_l5 - pts_l20) / max(0.05, pts_l20)) * 100, 1),
        "blended_pts": round(0.6 * pts_l5 + 0.4 * pts_l20, 2),
        "blended_sog": round(0.6 * sog_l5 + 0.4 * sog_l20, 2),
    }


def _classify(delta_pct: float) -> str:
    if delta_pct >= 15: return "HEATING_UP"
    if delta_pct <= -15: return "COOLING_DOWN"
    return "STABLE"


def fetch_sport(sport_key: str, espn_path: str) -> Dict[str, Any]:
    """Re-pull game logs for top players to compute L5 vs L20 split."""
    stats_blob = _load(os.path.join(DATA_DIR, f"player_stats_{sport_key}.json"))
    players = stats_blob.get("players") or []
    # Use the same athletes we already pulled
    is_basketball = sport_key in ("nba", "wnba")
    trends = []
    pulled = 0
    for p in players:
        aid = p.get("athlete_id")
        if not aid: continue
        gamelog = _http(GAMELOG_URL.format(path=espn_path, aid=aid))
        if not gamelog: continue
        stats = _all_event_stats(gamelog)
        if len(stats) < 8: continue
        if is_basketball:
            t = _basketball_trend(stats, sport_key)
        else:
            t = _hockey_trend(stats)
        if not t: continue
        cls = _classify(t.get("pts_delta_pct", 0))
        trends.append({
            "name": p["name"],
            "athlete_id": aid,
            "team": p.get("team"),
            "team_abbr": p.get("team_abbr"),
            "position": p.get("position"),
            "trend": cls,
            **t,
        })
        pulled += 1
        time.sleep(0.03)
    # Sort: heating up first (biggest gain), then cooling, then stable
    trends.sort(key=lambda t: -t.get("pts_delta_pct", 0))
    heating = [t for t in trends if t["trend"] == "HEATING_UP"]
    cooling = [t for t in trends if t["trend"] == "COOLING_DOWN"]
    stable = [t for t in trends if t["trend"] == "STABLE"]
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        "n_players_analyzed": len(trends),
        "n_heating_up": len(heating),
        "n_cooling_down": len(cooling),
        "n_stable": len(stable),
        "heating_up_top10": heating[:10],
        "cooling_down_top10": cooling[:10],
        "all_trends": trends,
    }
    out_path = os.path.join(DATA_DIR, f"player_trends_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, Any]:
    results = {}
    for sport_key, espn_path in SPORTS:
        try:
            p = fetch_sport(sport_key, espn_path)
            results[sport_key] = (p["n_players_analyzed"], p["n_heating_up"], p["n_cooling_down"])
        except Exception as e:
            results[sport_key] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    for sport, info in r.items():
        if isinstance(info, tuple):
            print(f"  {sport}: {info[0]} analyzed | {info[1]} heating up | {info[2]} cooling down")
        else:
            print(f"  {sport}: {info}")
