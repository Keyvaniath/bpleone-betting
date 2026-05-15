"""
EdgeStat -- batter recent form (last 14 days).

For each batter in tonight's confirmed lineups, pull their last 14 days
of hitting from MLB Stats API gameLog. Useful for:
  - Hot/cold flag (last 14d OPS vs season OPS delta)
  - Props that depend on recent form rather than season aggregate
  - Surfaces on research page

Run only at the 6 AM ET cron since lineups aren't always posted earlier.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "batter_form.json")


def batter_recent_form(pid: int, days: int = 14) -> Dict[str, Any]:
    """Aggregate last N days of hitting stats from gameLog."""
    if not pid or requests is None:
        return {}
    cache_name = f"bform_{pid}_{days}"
    cached = sr._cache_get(cache_name)
    if cached is not None:
        return cached
    season = dt.date.today().year
    try:
        r = requests.get(
            f"{sr.MLB_BASE}/people/{pid}/stats",
            params={"stats": "gameLog", "group": "hitting", "season": season},
            timeout=10,
        )
        if not r.ok:
            sr._cache_put(cache_name, {})
            return {}
        payload = r.json()
    except Exception:
        return {}
    splits = (payload.get("stats") or [{}])[0].get("splits") or []
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    recent = [g for g in splits if (g.get("date") or "") >= cutoff]
    if not recent:
        sr._cache_put(cache_name, {})
        return {}
    pa = sum(int(g["stat"].get("plateAppearances", 0) or 0) for g in recent)
    ab = sum(int(g["stat"].get("atBats", 0) or 0) for g in recent)
    hits = sum(int(g["stat"].get("hits", 0) or 0) for g in recent)
    hr = sum(int(g["stat"].get("homeRuns", 0) or 0) for g in recent)
    bb = sum(int(g["stat"].get("baseOnBalls", 0) or 0) for g in recent)
    k = sum(int(g["stat"].get("strikeOuts", 0) or 0) for g in recent)
    runs = sum(int(g["stat"].get("runs", 0) or 0) for g in recent)
    rbi = sum(int(g["stat"].get("rbi", 0) or 0) for g in recent)
    doubles = sum(int(g["stat"].get("doubles", 0) or 0) for g in recent)
    triples = sum(int(g["stat"].get("triples", 0) or 0) for g in recent)
    if not ab:
        out = {"games": len(recent), "pa": pa, "ab": 0, "low_sample": True}
        sr._cache_put(cache_name, out)
        return out
    singles = hits - doubles - triples - hr
    tb = singles + 2 * doubles + 3 * triples + 4 * hr
    avg = round(hits / ab, 3)
    obp = round((hits + bb) / pa, 3) if pa else None
    slg = round(tb / ab, 3)
    ops = round((obp or 0) + slg, 3)
    out = {
        "games": len(recent),
        "pa": pa, "ab": ab, "hits": hits, "hr": hr, "bb": bb, "k": k,
        "runs": runs, "rbi": rbi,
        "avg": avg, "obp": obp, "slg": slg, "ops": ops,
        "low_sample": pa < 30,
    }
    sr._cache_put(cache_name, out)
    return out


def hot_cold_label(recent_ops: float, season_ops: float) -> str:
    if recent_ops is None or season_ops is None or season_ops == 0:
        return "neutral"
    delta = recent_ops - season_ops
    if delta >= 0.150:
        return "blistering"
    if delta >= 0.075:
        return "hot"
    if delta <= -0.150:
        return "freezing"
    if delta <= -0.075:
        return "cold"
    return "neutral"


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(os.path.dirname(__file__), "..", "data", "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    out_games = []
    for g in m.get("games", []):
        L = g.get("lineups") or {}
        for side in ("home", "away"):
            for b in (L.get(side) or [])[:9]:
                pid = b.get("id")
                if not pid:
                    continue
                form = batter_recent_form(pid)
                if not form or form.get("low_sample"):
                    continue
                out_games.append({
                    "matchup": g.get("matchup"),
                    "side": side,
                    "order": b.get("order"),
                    "name": b.get("name"),
                    "player_id": pid,
                    **form,
                })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "lookback_days": 14,
        "batters_covered": len(out_games),
        "batters": out_games,
    }


def write_form(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote batter_form -> {path}")
    print(f"  Batters covered: {payload.get('batters_covered', 0)}")
    # Show top 3 hottest
    sorted_by_ops = sorted(payload.get("batters", []),
                           key=lambda b: -(b.get("ops") or 0))[:3]
    for b in sorted_by_ops:
        print(f"  {b['name']:25} ({b['games']} g, {b['pa']} PA) "
              f"AVG {b['avg']} OPS {b['ops']} ({b['hr']} HR, {b['rbi']} RBI)")


if __name__ == "__main__":
    write_form(build_all())
