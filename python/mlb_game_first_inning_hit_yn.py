"""
EdgeStat -- MLB game first-inning hit yes/no prop.

DK alt: 'Hit recorded in first inning yes/no'. Different from team-scores
in 1st (which requires the runner to reach home). This is just any hit
recorded by either team in inning 1.

Typical pricing:
  - Strong offensive matchup: -250 YES (heavy chalk)
  - Two aces facing weak lineups: +100 to +150
  - Avg matchup: -180 YES

Method:
  Combined expected hits in first inning per game:
    lam_hits_1st = 2 * 4.3 PA/half-inning * avg_AVG (~.250) * mults
                 ≈ 2 * 4.3 * 0.250 = 2.15 hits/game in 1st

  P(>=1 hit) = 1 - exp(-lam_hits_1st)

  STRONG_YES at p in [0.85, 0.93] (vs -250 book = 71.4% breakeven, +13.5%
  edge cushion since chalk markets rarely have big edges)
  STRONG_NO at p_no in [0.18, 0.32] (vs +180 NO breakeven 35.7%)

Output: data/mlb_game_first_inning_hit_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_first_inning_hit_yn.json")

LEAGUE_PA_FIRST_HALF = 4.3
LEAGUE_AVG = 0.250


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


def _lineup_score_for(matchup: str, side: str,
                      lineup_data: Dict[str, Any]) -> float:
    for g in (lineup_data.get("games") or []):
        if g.get("matchup") != matchup: continue
        return _safe((g.get(side) or {}).get("score"), 50.0)
    return 50.0


def _lineup_to_avg_mult(score: float) -> float:
    """Map lineup_quality_index score to AVG multiplier."""
    return max(0.85, min(1.20, 1.0 + (score - 50) * 0.006))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    parks = today.get("parks") or {}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue")
        park_run_factor = _safe((parks.get(park) or {}).get("run_factor"), 1.0) if isinstance(parks, dict) else 1.0

        # Sum expected hits across both half-innings
        lam_hits_total = 0.0
        side_breakdown: Dict[str, Any] = {}
        for side, sp_field in (("home", "away_pitcher"), ("away", "home_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            opp_pitcher = p_by_name.get((sp_name or "").lower(), {}) if sp_name else {}
            stats = opp_pitcher.get("stats") or {}
            opp_whip = _safe(stats.get("whip"), 1.30)
            pitcher_hit_susceptibility = opp_whip / 1.30  # 1.0 baseline

            lineup_score = _lineup_score_for(matchup, side, lineup_q)
            lineup_mult = _lineup_to_avg_mult(lineup_score)

            # Expected hits this team's first half-inning
            lam_side = (LEAGUE_PA_FIRST_HALF * LEAGUE_AVG *
                        lineup_mult * pitcher_hit_susceptibility *
                        (park_run_factor ** 0.4))
            lam_hits_total += lam_side
            side_breakdown[side] = {
                "lineup_score": round(lineup_score, 1),
                "opp_pitcher": sp_name,
                "opp_whip": round(opp_whip, 2),
                "lam_hits_side": round(lam_side, 3),
            }

        p_1plus_hit = 1 - math.exp(-lam_hits_total)
        p_no_hit = 1 - p_1plus_hit

        edge_class = "NONE"
        best_market = None
        # Tightened: require meaningful deviation. League-baseline games cluster
        # ~0.88 so STRONG_YES needs >= 0.92 (top of distribution).
        if 0.92 <= p_1plus_hit <= 0.96:
            edge_class = "STRONG_YES"
            best_market = {"market": "1ST_INN_HIT_YES",
                           "p": round(p_1plus_hit, 3),
                           "fair_odds": _american(p_1plus_hit)}
        elif 0.18 <= p_no_hit <= 0.32:
            edge_class = "STRONG_NO"
            best_market = {"market": "1ST_INN_HIT_NO",
                           "p": round(p_no_hit, 3),
                           "fair_odds": _american(p_no_hit)}

        rows.append({
            "matchup": matchup,
            "park": park,
            "park_run_factor": park_run_factor,
            "lam_hits_total_1st": round(lam_hits_total, 3),
            "p_1plus_hit": round(p_1plus_hit, 3),
            "p_no_hit": round(p_no_hit, 3),
            "fair_yes_odds": _american(p_1plus_hit),
            "fair_no_odds": _american(p_no_hit),
            "edge_class": edge_class,
            "best_market": best_market,
            "breakdown": side_breakdown,
        })

    rows.sort(key=lambda r: -r["p_1plus_hit"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(>=1 hit in 1st inning) = 1 - exp(-lam_total) where lam = "
                       "sum over both half-innings of (4.3 PA * 0.250 AVG * "
                       "lineup_mult * pitcher_WHIP_mult * park^0.4). STRONG_YES "
                       "p in [0.85, 0.93] vs -250 book; STRONG_NO p_no in [0.18, 0.32] "
                       "vs +180 NO breakeven.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-hit] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
