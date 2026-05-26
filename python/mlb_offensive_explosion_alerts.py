"""
EdgeStat -- MLB offensive explosion alerts.

Companion to dominant_outing_alerts but on the OFFENSE side. Surfaces teams
projecting elite offensive performance (5+ runs likely, lineup_quality
elite, opp_pitcher BAD_SPOT, HOMER_FRIENDLY park).

Aligned positive signals:
  - Lineup elite (score >= 70)
  - Opp pitcher BAD_SPOT or SOFT tier
  - Park HOMER_FRIENDLY or HITTER_FRIENDLY
  - Team total STRONG_OVER lean
  - 5+ runs probability >= 30%
  - Weather HOT_BOOST or WIND_BOOST_HR

A team with 4+ positive signals = stack candidate / team total OVER lean.

Output: data/mlb_offensive_explosion_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json")


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


def run() -> Dict[str, Any]:
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    five_plus = _load(os.path.join(DATA_DIR, "mlb_team_5plus_runs.json"))
    weather = _load(os.path.join(DATA_DIR, "mlb_weather_advisory.json"))

    # Index by matchup
    lq_idx = {g.get("matchup"): g for g in (lineup_q.get("games") or [])}
    park_idx = {g.get("matchup"): g for g in (park_hr.get("games") or [])}
    weather_idx = {g.get("matchup"): g for g in (weather.get("games") or [])}

    pe_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher_edge.get("rows") or []):
        pe_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r

    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        tt_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r

    fp_idx: Dict[str, Dict[str, Any]] = {}
    for r in (five_plus.get("rows") or []):
        fp_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r

    alerts: List[Dict[str, Any]] = []

    for g in (lineup_q.get("games") or []):
        matchup = g.get("matchup") or ""
        park_game = park_idx.get(matchup, {})
        weather_game = weather_idx.get(matchup, {})

        for side in ("home", "away"):
            side_data = g.get(side) or {}
            signals: Dict[str, int] = {}

            # 1) Lineup quality
            tier = side_data.get("tier")
            signals["LINEUP_ELITE"] = 1 if tier in ("elite", "above_avg") else 0

            # 2) Opp pitcher tier (opposing side)
            opp_side = "AWAY" if side == "home" else "HOME"
            opp_pitch = pe_idx.get(f"{matchup}|{opp_side}", {})
            opp_tier = opp_pitch.get("tier")
            signals["OPP_PITCHER_BAD_SPOT"] = 1 if opp_tier in ("BAD_SPOT", "SOFT") else 0

            # 3) Park environment
            park_tier = park_game.get("tier")
            signals["PARK_FRIENDLY"] = 1 if park_tier in ("HOMER_FRIENDLY", "HITTER_FRIENDLY") else 0

            # 4) Team total direction
            tt_row = tt_idx.get(f"{matchup}|{side.upper()}", {})
            tt_dir = tt_row.get("direction") or ""
            signals["TT_OVER"] = 1 if tt_dir in ("STRONG_OVER", "LEAN_OVER") else 0

            # 5) 5+ runs probability
            fp_row = fp_idx.get(f"{matchup}|{side.upper()}", {})
            p_5plus = _safe(fp_row.get("p_5plus"))
            signals["5PLUS_RUNS_HIGH"] = 1 if p_5plus >= 0.40 else 0

            # 6) Weather boost (game-level)
            w_leans = weather_game.get("directional_leans") or []
            has_weather_boost = any("OVER" in l or "BOOST" in l for l in w_leans)
            signals["WEATHER_BOOST"] = 1 if has_weather_boost else 0

            positive_count = sum(1 for v in signals.values() if v == 1)
            if positive_count < 3: continue

            tier_label = "ELITE_EXPLOSION" if positive_count >= 5 else "STRONG_OFFENSE"

            alerts.append({
                "matchup": matchup,
                "team": side_data.get("team"),
                "side": side.upper(),
                "lineup_tier": tier,
                "lineup_score": side_data.get("score"),
                "opp_pitcher_tier": opp_tier,
                "park_tier": park_tier,
                "tt_direction": tt_dir,
                "p_5plus_runs": round(p_5plus, 3),
                "n_positive_signals": positive_count,
                "signals": signals,
                "tier": tier_label,
            })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "ELITE_EXPLOSION"),
        "method_note": "Offensive explosion alert: team with 3+ positive signals "
                       "across LINEUP_ELITE, OPP_PITCHER_BAD_SPOT, PARK_FRIENDLY, "
                       "TT_OVER, 5PLUS_RUNS_HIGH, WEATHER_BOOST. ELITE_EXPLOSION = "
                       "5+ signals.",
        "alerts": alerts,
        "elite_explosions": [a for a in alerts if a["tier"] == "ELITE_EXPLOSION"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[off-explosion] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
