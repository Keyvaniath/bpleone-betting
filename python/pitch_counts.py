"""
EdgeStat -- pitch-count history per starter.

For each starting pitcher in today's slate, walk their last 5 starts and
compute average + max + trend in pitch count. This is a better signal than
just season-average IP for estimating today's expected IP because:

  - A starter coming off 110 pitches yesterday-or-day-before-last won't
    go deep tonight (rare with 4-5 day rest, but possible).
  - A pitcher who's been getting yanked early (avg PC 78) signals a tired
    arm or a manager pulling early -> lower expected K projection.
  - A pitcher trending UP (last 3: 90, 95, 105) is being trusted to go
    deeper -> raise expected IP / K projection.

This module exposes pitcher_pitch_history(pid) for props_pipeline to
optionally use as an IP estimator.
"""
from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional

import stats_repo as sr


CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "pitchcount")
CACHE_TTL = 6 * 3600


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def _cache_get(name: str) -> Optional[Any]:
    p = _cache_path(name)
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > CACHE_TTL:
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


def pitcher_pitch_history(pid: int, n: int = 5) -> Dict[str, Any]:
    """Return {avg_pc, max_pc, last_pc, trend, dates, n_starts}.

    Pitch count comes from pitching.numberOfPitches in the gameLog response.
    """
    if not pid:
        return {}
    cache_name = f"pc_{pid}"
    cached = _cache_get(cache_name)
    if cached is not None:
        return cached
    log = sr.pitcher_gamelog(pid)
    starts = [g for g in log if (g["stat"].get("inningsPitched") or 0) >= 3]
    sample = starts[:n]
    if not sample:
        out = {}
        _cache_put(cache_name, out)
        return out
    pcs: List[int] = []
    dates: List[str] = []
    for g in sample:
        pc = g["stat"].get("numberOfPitches")
        if pc is None:
            continue
        try:
            pcs.append(int(pc))
            dates.append(g.get("date") or "")
        except (TypeError, ValueError):
            pass
    if not pcs:
        _cache_put(cache_name, {})
        return {}
    avg = sum(pcs) / len(pcs)
    # Trend: avg of first half vs second half
    half = len(pcs) // 2
    if half:
        recent_avg = sum(pcs[:half]) / half
        older_avg = sum(pcs[half:]) / len(pcs[half:])
        trend = round(recent_avg - older_avg, 1)
    else:
        trend = 0.0
    out = {
        "n_starts": len(pcs),
        "avg_pc": round(avg, 1),
        "max_pc": max(pcs),
        "last_pc": pcs[0],
        "trend": trend,    # +ve = trending up (more pitches per start)
        "dates": dates,
        "pcs": pcs,
    }
    _cache_put(cache_name, out)
    return out


def expected_ip_from_pitch_history(pid: int, season_avg_ip: float) -> float:
    """Adjust season avg IP/start based on recent pitch count trends.

    A pitcher whose last-5 avg PC is materially lower than typical
    starter-load (~85 pitches) should project to lower expected IP today.
    """
    pc = pitcher_pitch_history(pid) or {}
    avg = pc.get("avg_pc")
    if not avg:
        return season_avg_ip
    # Each ~13 pitches = ~1 inning. Cap the adjustment.
    pc_implied_ip = avg / 15.0   # 15 pitches/inning is league avg
    blended = 0.6 * pc_implied_ip + 0.4 * season_avg_ip
    return max(3.0, min(7.5, blended))


if __name__ == "__main__":
    # Smoke: try a few well-known pitchers
    import requests
    sched = requests.get("https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=probablePitcher").json()
    pids_seen = set()
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            for side in ("home", "away"):
                pp = g["teams"][side].get("probablePitcher") or {}
                if pp.get("id") and pp.get("id") not in pids_seen:
                    pids_seen.add(pp["id"])
                    pc = pitcher_pitch_history(pp["id"])
                    if pc:
                        print(f"  {pp.get('fullName'):24} n={pc['n_starts']} avg={pc['avg_pc']} "
                              f"max={pc['max_pc']} last={pc['last_pc']} trend={pc['trend']:+.1f}")
                    if len(pids_seen) >= 6:
                        break
            if len(pids_seen) >= 6: break
        if len(pids_seen) >= 6: break
