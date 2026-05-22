"""
EdgeStat -- MLB Perfect Storm alerts.

Finds the day's most-leveraged batter situations: when MULTIPLE positive
factors converge on a single batter (sweet spot of the slate).

A "perfect storm" requires 3+ of the following:
  - HOMER_FRIENDLY park (HR-environment 110+)
  - Opp starter BAD_SPOT (pitcher edge composite SOFT/BAD_SPOT)
  - Batter is HOT (in hot_streaks.hot_batters)
  - Batter has STRONG_PLATOON_ADV vs opp starter's hand
  - Batter is in top-3 of lineup (high PA leverage)
  - Bullpen GASSED (extends to late-inning leverage)
  - Lineup_quality ELITE (entire lineup elevated)

Output: top-10 perfect-storm candidates with their convergent factors.

Output: data/mlb_perfect_storm_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_perfect_storm_alerts.json")


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
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    bp_fatigue = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    hot_streaks = _load(os.path.join(DATA_DIR, "hot_streaks.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    # Index helpers
    park_idx = {g.get("matchup"): g for g in (park_hr.get("games") or [])}
    pe_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher_edge.get("rows") or []):
        k = f"{r.get('matchup','')}|{r.get('side','')}"
        pe_idx[k] = r
    bp_idx = {g.get("matchup"): g for g in (bp_fatigue.get("games") or [])}
    hot_set = {(b.get("name") or "").lower() for b in (hot_streaks.get("hot_batters") or [])}

    candidates: List[Dict[str, Any]] = []

    for g in (lineup_q.get("games") or []):
        matchup = g.get("matchup") or ""
        park_info = park_idx.get(matchup, {})
        park_tier = park_info.get("tier") or ""
        bp_info = bp_idx.get(matchup, {})

        for side, opp_side in (("home", "AWAY"), ("away", "HOME")):
            lineup_info = g.get(side) or {}
            lineup_tier = lineup_info.get("tier") or ""
            opp_pitcher_row = pe_idx.get(f"{matchup}|{opp_side}", {})
            opp_tier = opp_pitcher_row.get("tier") or ""
            opp_pen_key = f"{opp_side.lower()}_pen"
            opp_pen_info = bp_info.get(opp_pen_key, {})

            top3 = lineup_info.get("top_3_batters") or []
            for i, batter in enumerate(top3):
                name = batter.get("name") or ""
                name_l = name.lower()
                factors: List[str] = []
                score = 0

                # Park factor
                if park_tier == "HOMER_FRIENDLY":
                    factors.append("HOMER_FRIENDLY_PARK")
                    score += 1
                elif park_tier == "HITTER_FRIENDLY":
                    factors.append("HITTER_FRIENDLY_PARK")
                    score += 0.5

                # Opp pitcher BAD_SPOT
                if opp_tier in ("BAD_SPOT", "SOFT"):
                    factors.append(f"OPP_PITCHER_{opp_tier}")
                    score += 1.5

                # Batter HOT
                if name_l in hot_set:
                    factors.append("BATTER_HOT_STREAK")
                    score += 1

                # Top of order
                if i < 3:
                    factors.append(f"BATTING_{i+1}ST")
                    score += 0.5

                # Lineup ELITE
                if lineup_tier == "elite":
                    factors.append("LINEUP_ELITE")
                    score += 1

                # Opp bullpen GASSED
                if opp_pen_info.get("tier") in ("GASSED", "TIRED"):
                    factors.append(f"OPP_BULLPEN_{opp_pen_info.get('tier')}")
                    score += 0.5

                # Power bonus
                if batter.get("score", 50) >= 70:
                    factors.append("ELITE_BATTER_QUALITY")
                    score += 0.5

                if len(factors) >= 3:
                    candidates.append({
                        "matchup": matchup,
                        "batter": name,
                        "team": lineup_info.get("team"),
                        "batting_position": i + 1,
                        "n_factors": len(factors),
                        "convergence_score": round(score, 1),
                        "factors": factors,
                        "opp_pitcher": opp_pitcher_row.get("pitcher"),
                        "opp_pitcher_tier": opp_tier,
                        "park": park_info.get("park"),
                        "park_tier": park_tier,
                        "lineup_tier": lineup_tier,
                    })

    candidates.sort(key=lambda r: -r["convergence_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_perfect_storms": len(candidates),
        "method_note": "Surfaces batters with 3+ convergent positive factors: "
                       "HOMER_FRIENDLY park, opp pitcher BAD_SPOT, HOT streak, "
                       "top-of-order PA leverage, ELITE lineup, GASSED bullpen, "
                       "ELITE batter quality. Higher convergence_score = more leveraged.",
        "top_10_perfect_storms": candidates[:10],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[storm] {o['n_perfect_storms']} perfect-storm batters -> {OUT}")
