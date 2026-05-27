"""
EdgeStat -- NBA garbage time fade alerts.

When a game projects as a blowout, star players on the favored side
typically sit late = early bench risk = PTS/PRA UNDER value:
  - Spread >= 8 OR double_digit_lead_forecast tier LIKELY
  - Star player projected 32+ minutes (he won't get all of them)
  - Projected pts >= 22

Recommends fading their alt total UNDER (lower line = safer cover).

Output: data/nba_garbage_time_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_garbage_time_alerts.json")


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
    dd_lead = _load(os.path.join(DATA_DIR, "nba_double_digit_lead_forecast.json"))
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))

    # Likely blowout matchups + sides
    blowout_sides: Dict[str, str] = {}
    for f in (dd_lead.get("likely_picks") or dd_lead.get("forecasts") or []):
        if isinstance(f, dict) and f.get("tier") in ("DOUBLE_DIGIT_LIKELY", "DOUBLE_DIGIT_LEAN"):
            blowout_sides[f.get("matchup", "")] = (f.get("team") or "").upper()

    min_idx = {_norm(r.get("player")): _safe(
                   r.get("projected_minutes") or r.get("expected_minutes"))
               for r in (minutes.get("rows") or []) if isinstance(r, dict)}

    fades: List[Dict[str, Any]] = []
    for r in (pts.get("rows") or []):
        if not isinstance(r, dict): continue
        matchup = r.get("matchup", "")
        team = (r.get("team") or "").upper()

        # Only star players on favored (blowout) side
        if blowout_sides.get(matchup) != team: continue

        proj_pts = _safe(r.get("projected_pts") or r.get("expected_pts"))
        if proj_pts < 22: continue

        name = _norm(r.get("player") or "")
        proj_min = min_idx.get(name, 0)
        if proj_min < 32: continue  # only stars

        # Estimate garbage time risk: at 8+ spread, top scorers play ~4-6 min less
        # so projected pts likely under by ~3-5 points
        risk_adjusted_pts = max(proj_pts - 5, proj_pts * 0.78)

        fades.append({
            "player": r.get("player"),
            "team": team,
            "matchup": matchup,
            "projected_pts": round(proj_pts, 1),
            "projected_minutes": round(proj_min, 1),
            "risk_adjusted_pts": round(risk_adjusted_pts, 1),
            "advisory": "Star player on likely blowout side -- garbage time bench "
                        "risk. Consider PTS UNDER alt + PRA UNDER alt at lower "
                        "lines.",
            "recommended_markets": [
                f"{r.get('player')} PTS UNDER (alt)",
                f"{r.get('player')} PRA UNDER (alt)",
                f"FADE {r.get('player')} 30+ PTS YES",
            ],
        })

    fades.sort(key=lambda f: -(f.get("projected_pts") or 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fades": len(fades),
        "method_note": "NBA garbage time fade alerts. Stars (proj_min >= 32, "
                       "proj_pts >= 22) on likely-blowout sides (from "
                       "double_digit_lead_forecast). 8+ spread games often "
                       "remove starters in Q4 -> UNDER value.",
        "fades": fades,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-garbage] {o['n_fades']} garbage time fades -> {OUT}")
