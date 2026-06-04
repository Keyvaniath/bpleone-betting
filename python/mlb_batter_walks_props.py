"""
EdgeStat -- MLB batter walks (BB) prop projections.

Common DK lines: 0.5 walks O/U (-120 / +100) per batter.
"Batter to walk 1+" is a yes/no prop tied to plate-discipline talent.

Method:
  expected_walks = expected_PA * season_BB_rate * opp_pitcher_BB_rate_mult
  P(walks >= 1) = 1 - exp(-expected_walks)  [Poisson]
  STRONG_YES when P(walk) >= 0.42 (vs typical book +130 ~ 43.5% breakeven)
  STRONG_NO when P(walk) <= 0.20 (vs book -150 = 60% breakeven on NO)

Output: data/mlb_batter_walks_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

import mlb_batter_splits as _SPL   # real per-batter (venue) BB% split


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_walks_props.json")

LEAGUE_BB_RATE = 0.085  # ~8.5% BB rate league avg


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
    spl = _SPL.load(DATA_DIR)   # real per-batter venue BB% (neutral fallback if absent)

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
            opp_bb_per_9 = _safe(opp_stats.get("k_per_9"), 3.2)  # using as proxy when bb_per_9 missing
            opp_bb_per_9_inv = _safe(opp_stats.get("bb_per_9"), 3.2)
            # If we have actual bb_per_9, use that. Otherwise default.
            if opp_bb_per_9_inv > 0 and opp_bb_per_9_inv < 8:
                opp_bb_factor = opp_bb_per_9_inv / 3.2
            else:
                opp_bb_factor = 1.0

            lineup = lineups.get(side) or []
            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # Prefer the batter's REAL measured BB% (venue, PA-regularized);
                # fall back to the OPS proxy only when the batter has no split.
                real_bb = spl.bb_rate(name, side == "home")
                if real_bb is not None:
                    bb_rate = max(0.02, min(0.22, real_bb))
                    bb_source = "real_split"
                else:
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    # Higher OPS roughly correlates with higher BB rate (selective hitters)
                    bb_rate = max(0.04, min(0.18, 0.075 + (season_ops - 0.72) * 0.15))
                    bb_source = "ops_proxy"

                pa = _expected_pa(order)
                expected_walks = pa * bb_rate * opp_bb_factor
                p_walks = 1 - math.exp(-expected_walks)
                p_no_walk = 1 - p_walks

                edge_class = "NONE"
                best_market = None
                # STRONG_YES when P(walk) >= 42% (5%+ edge vs +130 book = 43.5%)
                if p_walks >= 0.42:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "WALK_1PLUS_YES", "p": round(p_walks, 3),
                                   "fair_odds": _american(p_walks)}
                # STRONG_NO when P(walk) <= 0.20 (5%+ edge vs -120 book on NO)
                elif p_walks <= 0.20:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "WALK_1PLUS_NO", "p": round(p_no_walk, 3),
                                   "fair_odds": _american(p_no_walk)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "bb_rate": round(bb_rate, 3),
                    "bb_source": bb_source,
                    "opp_pitcher": opp_starter_name,
                    "opp_bb_factor": round(opp_bb_factor, 3),
                    "expected_pa": pa,
                    "expected_walks": round(expected_walks, 3),
                    "p_walks": round(p_walks, 3),
                    "p_no_walk": round(p_no_walk, 3),
                    "fair_yes": _american(p_walks),
                    "fair_no": _american(p_no_walk),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_walks"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(walks>=1) = 1-exp(-PA*BB_rate*opp_pitcher_BB_factor). "
                       "BB_rate derived from OPS proxy. STRONG_YES p>=42% (vs +130 book), "
                       "STRONG_NO p<=20% (vs -120 on NO).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[batter-bb] {o['n_batters']} batters, {o['n_strong_edges']} strong edges -> {OUT}")
