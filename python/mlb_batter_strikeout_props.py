"""
EdgeStat -- MLB batter strikeout (1+ K yes/no) prop projections.

Common DK lines: "Batter to strike out 1+" -- typical -150 (60% breakeven).
"Batter to strike out 2+" -- typical +200 (33%).

Method:
  expected_K = PA * batter_K_rate * opp_pitcher_K_rate_factor
  P(K >= 1) = 1 - exp(-expected_K)  [Poisson]
  P(K >= 2) = 1 - exp(-expected_K) - expected_K * exp(-expected_K)

  STRONG_YES (1+) when P(K) >= 0.65 (5%+ edge vs -150 book)
  STRONG_NO (1+) when P(K) <= 0.32 (5%+ edge vs +200 on NO)
  STRONG_YES (2+) when P(K2) >= 0.38 (5%+ edge vs +200 book)

Output: data/mlb_batter_strikeout_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_strikeout_props.json")

LEAGUE_K_RATE = 0.225  # ~22.5% K rate league avg


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


def _expected_pa(order: int) -> float:
    if order <= 3: return 4.4
    if order <= 6: return 4.1
    return 3.7


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    lvr_idx = {}
    for row in (lvr.get("all_batters") or []):
        nm = (row.get("batter") or "").lower()
        if nm: lvr_idx[nm] = row

    pitcher_idx = {}
    for p in (pitcher_logs.get("pitchers") or []):
        nm = (p.get("name") or "").lower()
        if nm: pitcher_idx[nm] = p

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            opp_side = "away" if side == "home" else "home"
            opp_starter_info = (g.get(opp_side) or {}).get("starter") or g.get(f"{opp_side}_pitcher")
            opp_starter_name = (
                opp_starter_info if isinstance(opp_starter_info, str)
                else (opp_starter_info or {}).get("name") if isinstance(opp_starter_info, dict)
                else None
            )
            opp_pitcher_row = pitcher_idx.get((opp_starter_name or "").lower(), {})
            opp_stats = opp_pitcher_row.get("stats") or {}
            opp_k_per_9 = _safe(opp_stats.get("k_per_9"), 8.5)
            opp_k_factor = max(0.65, min(1.50, opp_k_per_9 / 8.5))

            lineup = lineups.get(side) or []
            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # Estimate batter K rate from OPS proxy (lower OPS -> higher K)
                season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                k_rate = max(0.15, min(0.38, 0.27 - 0.10 * (season_ops - 0.72)))

                pa = _expected_pa(order)
                expected_k = pa * k_rate * opp_k_factor

                # Poisson probabilities
                exp_neg = math.exp(-expected_k)
                p_0 = exp_neg
                p_1 = expected_k * exp_neg
                p_at_least_1 = 1 - p_0
                p_at_least_2 = 1 - p_0 - p_1

                edge_class = "NONE"
                best_market = None
                # STRONG_YES (1+) when p(K>=1) >= 0.65 (vs -150 book = 60%)
                if p_at_least_1 >= 0.65:
                    edge_class = "STRONG_YES_1PLUS"
                    best_market = {"market": "K_1PLUS_YES", "p": round(p_at_least_1, 3),
                                   "fair_odds": _american(p_at_least_1)}
                # STRONG_NO (1+) when p(K>=1) <= 0.32 (low K hitters, vs +200 NO)
                elif p_at_least_1 <= 0.32:
                    edge_class = "STRONG_NO_1PLUS"
                    best_market = {"market": "K_1PLUS_NO", "p": round(1 - p_at_least_1, 3),
                                   "fair_odds": _american(1 - p_at_least_1)}
                # STRONG_YES (2+) when p(K>=2) >= 0.38 (vs +200 book = 33%)
                elif p_at_least_2 >= 0.38:
                    edge_class = "STRONG_YES_2PLUS"
                    best_market = {"market": "K_2PLUS_YES", "p": round(p_at_least_2, 3),
                                   "fair_odds": _american(p_at_least_2)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "batter_k_rate": round(k_rate, 3),
                    "opp_pitcher": opp_starter_name,
                    "opp_k_per_9": opp_k_per_9,
                    "opp_k_factor": round(opp_k_factor, 3),
                    "expected_pa": pa,
                    "expected_k": round(expected_k, 3),
                    "p_at_least_1": round(p_at_least_1, 3),
                    "p_at_least_2": round(p_at_least_2, 3),
                    "fair_1plus_yes": _american(p_at_least_1),
                    "fair_2plus_yes": _american(p_at_least_2),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_at_least_1"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(K>=N) = Poisson with lambda = PA*batter_K_rate*opp_K_factor. "
                       "STRONG_YES 1+ p>=65% (vs -150), STRONG_NO 1+ p<=32% (vs +200 NO), "
                       "STRONG_YES 2+ p>=38% (vs +200).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[batter-k] {o['n_batters']} batters, {o['n_strong_edges']} strong edges -> {OUT}")
