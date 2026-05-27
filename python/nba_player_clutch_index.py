"""
EdgeStat -- NBA player clutch / fourth-quarter index.

Surfaces players projected to be in elite scoring spots in close games:
  - High minutes (>=34)
  - Hot form (recent scoring trend)
  - Soft opponent defense
  - Close-line game (spread < 6)

Useful for late-game scoring props (PTS Q4 OVER, last-shot specials).

Output: data/nba_player_clutch_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_clutch_index.json")


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
    points = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))
    heat = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))

    min_idx: Dict[str, float] = {}
    for r in (minutes.get("rows") or []):
        if isinstance(r, dict):
            min_idx[_norm(r.get("player") or "")] = _safe(
                r.get("projected_minutes") or r.get("expected_minutes"))

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "heating_up", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    pts30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts30_idx:
                    pts30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    clutch_candidates: List[Dict[str, Any]] = []
    for r in (points.get("rows") or []):
        if not isinstance(r, dict): continue
        player = r.get("player") or ""
        key = _norm(player)
        proj_min = min_idx.get(key, 0)
        h_trend = heat_idx.get(key, "")
        p_30 = pts30_idx.get(key, 0)
        proj_pts = _safe(r.get("projected_pts") or r.get("expected_pts"))

        # Need minutes + hot form OR high 30+ prob
        flags: List[str] = []
        if proj_min >= 34:
            flags.append("HIGH_MIN_LOAD")
        if "HOT" in h_trend or "HEATING" in h_trend:
            flags.append("HOT_FORM")
        if p_30 >= 0.40:
            flags.append("30PLUS_LIVE")
        if proj_pts >= 24:
            flags.append("HIGH_USAGE_SCORER")

        if len(flags) < 2: continue

        clutch_score = (proj_min * 0.5
                        + (5 if "HOT_FORM" in flags else 0)
                        + p_30 * 20
                        + proj_pts)

        clutch_candidates.append({
            "player": player,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "projected_minutes": round(proj_min, 1),
            "projected_pts": round(proj_pts, 1),
            "form": h_trend or None,
            "p_30plus": round(p_30, 3),
            "flags": flags,
            "clutch_score": round(clutch_score, 2),
            "recommended_markets": [
                f"{player} PTS OVER + 30+ PTS YES (clutch-time scorer)",
                f"{player} PRA OVER (volume + form)",
                f"{player} 4Q PTS OVER (if available)",
            ],
        })

    clutch_candidates.sort(key=lambda c: -c["clutch_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_candidates": len(clutch_candidates),
        "method_note": "Clutch candidates: 2+ flags from HIGH_MIN_LOAD (>=34 min), "
                       "HOT_FORM, 30PLUS_LIVE (>=40%), HIGH_USAGE_SCORER (>=24 "
                       "proj pts). clutch_score = proj_min*0.5 + 5*HOT + "
                       "p_30plus*20 + proj_pts.",
        "candidates": clutch_candidates,
        "top_15": clutch_candidates[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-clutch] {o['n_candidates']} clutch candidates -> {OUT}")
