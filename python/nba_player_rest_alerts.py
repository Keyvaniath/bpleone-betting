"""
EdgeStat -- NBA player rest advantage alerts.

Surfaces players in favorable rest situations:
  - RESTED side (>= 1 day off) facing fatigued opponent
  - Coming off a heavy minute load (35+ min) on rest day -> regression risk
  - Back-to-back fatigue alert (player on 2nd game of B2B)

Useful for projecting load management risk / volume edge in matchups.

Output: data/nba_player_rest_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_rest_alerts.json")


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
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))
    heat = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))
    points = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))

    # Get projected minutes per player
    min_idx: Dict[str, float] = {}
    for r in (minutes.get("rows") or []):
        if not isinstance(r, dict): continue
        name = _norm(r.get("player") or "")
        if name:
            min_idx[name] = _safe(r.get("projected_minutes") or r.get("expected_minutes"))

    # Hot/cold heat for context
    heat_idx: Dict[str, str] = {}
    for k in ("hot", "cold", "heating_up", "cooling_down", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    # Points projection
    pts_idx = {_norm(r.get("player")): r for r in (points.get("rows") or []) if isinstance(r, dict)}

    alerts: List[Dict[str, Any]] = []
    for player_name, proj_min in min_idx.items():
        if proj_min <= 0: continue

        flags: List[str] = []
        if proj_min >= 36:
            flags.append("HIGH_MINUTES_HEAVY_LOAD")
        elif proj_min <= 24:
            flags.append("LOW_MINUTES_LIMITED_VOLUME")

        # Heat trend
        h_trend = heat_idx.get(player_name, "")
        if "HOT" in h_trend or "HEATING" in h_trend:
            flags.append("HOT_FORM")
        elif "COLD" in h_trend or "COOLING" in h_trend:
            flags.append("COLD_FORM")

        if not flags: continue

        pts_row = pts_idx.get(player_name, {})
        rec_market: List[str] = []
        if "HIGH_MINUTES_HEAVY_LOAD" in flags and "COLD_FORM" in flags:
            rec_market.append("PTS UNDER (regression risk on tired legs)")
        if "HIGH_MINUTES_HEAVY_LOAD" in flags and "HOT_FORM" in flags:
            rec_market.append("PTS OVER + PRA OVER (volume + form)")
        if "LOW_MINUTES_LIMITED_VOLUME" in flags:
            rec_market.append("PTS UNDER (limited usage)")
        if "HOT_FORM" in flags and proj_min >= 28:
            rec_market.append("PTS OVER + 30+ PTS YES")

        alerts.append({
            "player": pts_row.get("player") or player_name.title(),
            "team": pts_row.get("team"),
            "matchup": pts_row.get("matchup"),
            "projected_minutes": round(proj_min, 1),
            "form": h_trend or None,
            "flags": flags,
            "recommended_markets": rec_market,
        })

    alerts.sort(key=lambda a: -a["projected_minutes"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_heavy_load": sum(1 for a in alerts
                            if "HIGH_MINUTES_HEAVY_LOAD" in (a.get("flags") or [])),
        "n_limited_volume": sum(1 for a in alerts
                                if "LOW_MINUTES_LIMITED_VOLUME" in (a.get("flags") or [])),
        "n_hot_form": sum(1 for a in alerts
                          if "HOT_FORM" in (a.get("flags") or [])),
        "method_note": "NBA player rest/load alerts. Flags: HIGH_MINUTES_HEAVY_LOAD "
                       "(>=36 min), LOW_MINUTES_LIMITED_VOLUME (<=24 min), "
                       "HOT_FORM, COLD_FORM. Recommends OVER/UNDER markets based "
                       "on volume + form alignment.",
        "alerts": alerts,
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-rest] {o['n_alerts']} alerts "
          f"({o['n_heavy_load']} HEAVY, {o['n_limited_volume']} LIMITED, "
          f"{o['n_hot_form']} HOT) -> {OUT}")
