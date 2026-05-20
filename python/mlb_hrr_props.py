"""
EdgeStat -- MLB HRR (Hits + Runs + RBI) combo prop projections.

HRR is one of DraftKings' most-bet player props. Common lines:
  - HRR 1.5 over/under
  - HRR 2.5 over/under
  - HRR 3.5 over/under (for elite hitters)

Approach:
  Per-batter expected per-PA contribution:
    - E[hits/PA]  = AVG * (AB/PA ratio)
    - E[runs/PA]  = (R / PA) season rate (~ 0.13 league avg)
    - E[RBI/PA]   = (RBI / PA) season rate (~ 0.13 league avg)
    - E[HRR/PA]   = sum above (HRs count once for hit AND a run AND an RBI = 3)
  Then E[HRR per game] = E[HRR/PA] * expected_PA (4.4 for top of order)
  Poisson approximation for P(HRR >= 2), P(HRR >= 3), P(HRR >= 4)

Edge tagging vs typical DK lines (Over -150 to +130):
  - STRONG_2_PLUS: P(HRR >= 2) >= 0.70 (-233 fair)
  - STRONG_3_PLUS: P(HRR >= 3) >= 0.45 (+122 fair)
  - STANDARD_2_PLUS / 3_PLUS for moderate edges

Inputs:
  - data/matchups.json (lineups + pitchers)
  - data/mlb_batter_lvr_splits.json (batter season + matchup splits)
  - data/today.json (park factors)

Output: data/mlb_hrr_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_hrr_props.json")

# League averages (per PA)
LEAGUE_HITS_PER_PA = 0.227  # ~AVG * 0.92 (PA → AB)
LEAGUE_RUNS_PER_PA = 0.128  # 4.5 R/g / 35 PA per team
LEAGUE_RBI_PER_PA = 0.128
LEAGUE_HRR_PER_PA = LEAGUE_HITS_PER_PA + LEAGUE_RUNS_PER_PA + LEAGUE_RBI_PER_PA  # ~0.48


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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    p_less = sum(_poisson_pmf(i, lam) for i in range(k))
    return max(0.0, min(1.0, 1.0 - p_less))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _expected_pa(order: int) -> float:
    if order <= 3: return 4.4
    if order <= 6: return 4.1
    return 3.7


def _hrr_per_pa(blended_ops: float, batter_position_index: int, park_run_factor: float,
                lineup_runs_per_game: float) -> Dict[str, float]:
    """Estimate HRR rate per PA for this batter in this matchup."""
    # Higher OPS = more hits AND more runs AND more RBI (correlated)
    # Calibrate: league avg OPS ~ 0.726 -> HRR/PA = 0.48
    # Each 0.100 OPS bump -> +0.10 HRR/PA roughly
    ops_factor = max(0.5, min(1.7, blended_ops / 0.726))
    base_hrr = LEAGUE_HRR_PER_PA * ops_factor
    # Lineup position affects R/RBI mix:
    #   top of order (1-3) -> more R, fewer RBI
    #   middle (3-5)        -> more RBI
    #   bottom (7-9)        -> less of both
    if batter_position_index <= 3:
        hits_share = 0.40; runs_share = 0.40; rbi_share = 0.20
    elif batter_position_index <= 6:
        hits_share = 0.35; runs_share = 0.30; rbi_share = 0.35
    else:
        hits_share = 0.40; runs_share = 0.25; rbi_share = 0.35
    # Park: hitter parks boost runs/RBI more than hits
    park_mult = 1.0 + (park_run_factor - 1.0) * 0.7
    park_mult = max(0.85, min(1.20, park_mult))
    base_hrr *= park_mult
    return {
        "hrr_per_pa": base_hrr,
        "expected_hits_per_pa": base_hrr * hits_share,
        "expected_runs_per_pa": base_hrr * runs_share,
        "expected_rbi_per_pa": base_hrr * rbi_share,
        "ops_factor": ops_factor,
        "park_mult": park_mult,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    parks = today.get("parks") or {}
    lvr_idx = {}
    for row in (lvr.get("all_batters") or []):
        nm = (row.get("batter") or "").lower()
        if nm: lvr_idx[nm] = row

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        lineup_runs = _safe((g.get("home") or {}).get("runs"), 4.5)

        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # Blend split-OPS with season OPS (Bayesian, prior 80 PA)
                season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                split_ops = _safe(lvr_row.get("split_ops"), season_ops)
                split_pa = int(_safe(lvr_row.get("split_pa"), 0))
                blended_ops = ((split_pa * split_ops + 80 * season_ops) / (split_pa + 80)
                               if split_pa > 0 else season_ops)
                # Clamp to realistic range
                blended_ops = max(0.55, min(1.10, blended_ops))

                rates = _hrr_per_pa(blended_ops, order, park_run_factor, lineup_runs)
                pa = _expected_pa(order)
                expected_hrr = rates["hrr_per_pa"] * pa

                p_2_plus = _poisson_at_least(2, expected_hrr)
                p_3_plus = _poisson_at_least(3, expected_hrr)
                p_4_plus = _poisson_at_least(4, expected_hrr)
                p_1_plus = _poisson_at_least(1, expected_hrr)

                edge_class = "NONE"
                if p_3_plus >= 0.50:
                    edge_class = "STRONG_3_PLUS"
                elif p_2_plus >= 0.72:
                    edge_class = "STRONG_2_PLUS"
                elif p_3_plus >= 0.40:
                    edge_class = "STANDARD_3_PLUS"
                elif p_2_plus >= 0.62:
                    edge_class = "STANDARD_2_PLUS"

                if expected_hrr < 0.8: continue

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "opp_pitcher": opp_pitcher,
                    "park": park,
                    "park_run_factor": park_run_factor,
                    "blended_ops": round(blended_ops, 3),
                    "hrr_per_pa": round(rates["hrr_per_pa"], 3),
                    "expected_pa": pa,
                    "expected_hrr": round(expected_hrr, 2),
                    "p_1_plus": round(p_1_plus, 3),
                    "p_2_plus": round(p_2_plus, 3),
                    "p_3_plus": round(p_3_plus, 3),
                    "p_4_plus": round(p_4_plus, 3),
                    "fair_odds_2_plus": _american(p_2_plus),
                    "fair_odds_3_plus": _american(p_3_plus),
                    "edge_class": edge_class,
                })

    rows.sort(key=lambda r: -r["expected_hrr"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "league_hrr_per_pa": LEAGUE_HRR_PER_PA,
        "method_note": "HRR = Hits + Runs + RBI per batter. Poisson on per-PA rate × E[PA].",
        "top_25_by_xHRR": rows[:25],
        "strong_edges": strong[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hrr-props] {o['n_batters']} batters, {o['n_strong_edges']} strong edges -> {OUT}")
