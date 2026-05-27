"""
EdgeStat -- NBA 50-point watchlist.

Surfaces players with elite scoring potential to drop 50+ points in a
single game (rare ~10x per season). Requirements:
  - Player confluence_score >= 9
  - p_30plus_pts >= 0.50
  - Projected minutes >= 36
  - Projected pts >= 32
  - Hot form

Output: data/nba_50_burger_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_50_burger_watchlist.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    confluence = _load(os.path.join(DATA_DIR, "nba_player_confluence_score.json"))
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))
    heat = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))

    pts_idx = {_norm(r.get("player")): r
               for r in (pts.get("rows") or []) if isinstance(r, dict)}
    min_idx = {_norm(r.get("player")): _safe(
                   r.get("projected_minutes") or r.get("expected_minutes"))
               for r in (minutes.get("rows") or []) if isinstance(r, dict)}

    pts30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts30_idx:
                    pts30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "heating_up", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    watchlist: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 9: continue

        name = _norm(r.get("player") or "")
        p_30 = pts30_idx.get(name, 0)
        if p_30 < 0.50: continue

        proj_min = min_idx.get(name, 0)
        if proj_min < 36: continue

        pts_data = pts_idx.get(name, {})
        proj_pts = _safe(pts_data.get("projected_pts") or pts_data.get("expected_pts"))
        if proj_pts < 32: continue

        h_trend = heat_idx.get(name, "")
        is_hot = "HOT" in h_trend or "HEATING" in h_trend

        # Estimate 50+ probability (very rough)
        # baseline ~ 0.5% per game for elite scorers
        p_50_est = 0.005 * (score / 9.0) * (p_30 / 0.50) * (proj_pts / 32.0)
        if is_hot: p_50_est *= 1.5
        p_50_est = min(p_50_est, 0.04)

        if p_50_est < 0.005: continue  # baseline filter

        watchlist.append({
            "player": r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "composite_score": round(score, 2),
            "projected_pts": round(proj_pts, 1),
            "projected_minutes": round(proj_min, 1),
            "p_30plus_pts": round(p_30, 3),
            "form": h_trend or None,
            "est_p_50plus_pts": round(p_50_est, 4),
            "advisory": "Long-shot 50-burger candidate. Recommended bets: "
                        "40+ PTS YES (3-1 to 8-1), 35+ PTS YES (better "
                        "value), PTS OVER + 30+ PTS YES + PRA OVER "
                        "(correlated parlay).",
            "recommended_markets": [
                "40+ PTS YES",
                "35+ PTS YES",
                "PTS OVER 30.5 + 30+ PTS YES + PRA OVER (parlay)",
                "50+ PTS YES (long shot)",
            ],
        })

    watchlist.sort(key=lambda w: -w["est_p_50plus_pts"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "NBA 50-burger watchlist. Confluence >= 9 + p_30plus_pts "
                       ">= 50% + minutes >= 36 + proj_pts >= 32. 50+ point "
                       "games ~0.5% historical for top scorers.",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-50] {o['n_watchlist']} on watchlist -> {OUT}")
