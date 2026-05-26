"""
EdgeStat -- MLB total HRs in game O/U prop.

DK alt: 'Total HRs in game over/under N.5' (common lines 1.5, 2.5, 3.5).

Method:
  Combined expected HRs across both teams:
    lam_HRs = sum over both lineups of:
      n_PA * AVG_HR_per_PA * lineup_quality_mult * park_HR_factor

  League AVG_HR_per_PA ~ 0.030. Top lineups ~0.040. Bottom ~0.020.

  P(>=N HRs) = 1 - poisson_cdf(N-1, lam_HRs)

  STRONG_OVER when 5%+ edge; gated by lineup_quality deviation from baseline.

Output: data/mlb_total_HRs_game.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_total_HRs_game.json")

LEAGUE_HR_PER_PA = 0.030
LEAGUE_PA_PER_TEAM = 38  # 9 innings * ~4.2 PA


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def _lineup_quality_for(matchup: str, side: str,
                        lineup_data: Dict[str, Any]) -> float:
    for g in (lineup_data.get("games") or []):
        if g.get("matchup") != matchup: continue
        return _safe((g.get(side) or {}).get("score"), 50.0)
    return 50.0


def _lineup_to_hr_mult(score: float) -> float:
    """Higher-quality lineups produce ~33% more HRs at score 70 vs baseline 50."""
    return max(0.70, min(1.45, 1.0 + (score - 50) * 0.012))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    parks = today.get("parks") or {}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue")
        park_hr_factor = _safe((parks.get(park) or {}).get("hr_factor"), 1.0) if isinstance(parks, dict) else 1.0

        lam_total_hrs = 0.0
        side_details: Dict[str, Any] = {}
        for side in ("home", "away"):
            lineup_score = _lineup_quality_for(matchup, side, lineup_q)
            lineup_mult = _lineup_to_hr_mult(lineup_score)
            lam_side = LEAGUE_PA_PER_TEAM * LEAGUE_HR_PER_PA * lineup_mult * park_hr_factor
            lam_total_hrs += lam_side
            side_details[side] = {
                "lineup_score": round(lineup_score, 1),
                "lineup_mult": round(lineup_mult, 3),
                "lam_side": round(lam_side, 3),
            }

        p_1plus = _poisson_at_least(1, lam_total_hrs)
        p_2plus = _poisson_at_least(2, lam_total_hrs)
        p_3plus = _poisson_at_least(3, lam_total_hrs)
        p_4plus = _poisson_at_least(4, lam_total_hrs)

        # Find best edge across alt lines — require deviation from baseline
        # (~2.28 HRs avg game). Otherwise Normal/Poisson at center always shows
        # ~60% on offset lines (spurious).
        league_baseline = 2.28
        deviates = abs(lam_total_hrs - league_baseline) >= 0.5
        edges: List[Dict[str, Any]] = []
        if deviates:
            for line, p in [(0.5, p_1plus), (1.5, p_2plus), (2.5, p_3plus), (3.5, p_4plus)]:
                for direction, prob in (("OVER", p), ("UNDER", 1 - p)):
                    if 0.60 <= prob <= 0.70:
                        edges.append({
                            "market": f"TOTAL_HRS_{direction}_{line}",
                            "line": line, "direction": direction,
                            "p": round(prob, 3),
                            "fair_odds": _american(prob),
                        })

        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG_ALT" if best_edge else "NONE"

        rows.append({
            "matchup": matchup,
            "park": park,
            "park_hr_factor": park_hr_factor,
            "lam_total_HRs": round(lam_total_hrs, 3),
            "p_1plus_HR": round(p_1plus, 3),
            "p_2plus_HR": round(p_2plus, 3),
            "p_3plus_HR": round(p_3plus, 3),
            "p_4plus_HR": round(p_4plus, 3),
            "side_details": side_details,
            "best_market": best_edge,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: -r["lam_total_HRs"])
    strong = [r for r in rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Total HRs in game = sum across both lineups of "
                       "PA * HR/PA * lineup_quality_mult * park_HR_factor. Poisson(>=N) "
                       "at 0.5/1.5/2.5/3.5 lines. STRONG when p in [0.58, 0.68].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hrs-game] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
