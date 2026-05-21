"""
EdgeStat -- MLB player to hit a home run yes/no prop.

THE most popular MLB HR prop. Common DK lines:
  - Top sluggers (Judge, Ohtani, Schwarber): +250 to +400 YES
  - Mid power: +500 to +700
  - Contact hitters: +900+ (essentially never)

Method:
  - First choice: use `adj_p_1_plus_hr` from mlb_batter_lvr_splits.json,
    which is a Bayesian-shrunk per-batter HR probability with handedness
    and opponent-pitcher adjustment already applied.
  - Fallback: estimate from blended OPS (split + season) + park HR factor.

  STRONG_YES when our P(HR) >= 14% (vs +600 book = 14.3% breakeven)
  STRONG_NO not surfaced — too thin given typical -1500+ NO juice.

Output: data/mlb_to_hit_hr_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json")

LEAGUE_HR_PER_PA = 0.030  # ~3% HR rate league avg


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


def _ops_to_hr_per_pa(ops: float) -> float:
    """Heuristic for batters not in the LvR dataset.
    OPS 0.700 -> 1.5% HR/PA, OPS 0.900 -> 4.5% HR/PA."""
    return max(0.005, min(0.080, 0.015 + (ops - 0.700) * 0.045))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))

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
        park_hr_factor = _safe((park_info or {}).get("hr_factor"), 1.0) or 1.0
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # PRIMARY: use Bayesian-shrunk adj_p_1_plus_hr if available
                lvr_p_hr = lvr_row.get("adj_p_1_plus_hr")
                if lvr_p_hr is not None:
                    p_hr = float(lvr_p_hr)
                    hr_source = "lvr_adj"
                else:
                    # FALLBACK: OPS-based estimate
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    split_ops = _safe(lvr_row.get("split_ops"), season_ops)
                    split_pa = int(_safe(lvr_row.get("split_pa"), 0))
                    blended_ops = ((split_pa * split_ops + 80 * season_ops) / (split_pa + 80)
                                   if split_pa > 0 else season_ops)
                    hr_per_pa = _ops_to_hr_per_pa(blended_ops) * park_hr_factor
                    pa = _expected_pa(order)
                    expected_hr = hr_per_pa * pa
                    p_hr = 1 - math.exp(-expected_hr)
                    hr_source = "ops_fallback"

                p_no_hr = 1 - p_hr

                edge_class = "NONE"
                best_market = None
                # STRONG_YES when P(HR) >= 14% (vs +600 book breakeven = 14.3%)
                if p_hr >= 0.14:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "TO_HIT_HR_YES", "p": round(p_hr, 3),
                                   "fair_odds": _american(p_hr)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "park": park,
                    "park_hr_factor": park_hr_factor,
                    "hr_source": hr_source,
                    "p_hr": round(p_hr, 3),
                    "p_no_hr": round(p_no_hr, 3),
                    "fair_yes_odds": _american(p_hr),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_hr"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(HR) primary from mlb_batter_lvr_splits.adj_p_1_plus_hr "
                       "(Bayesian-shrunk, opp-handedness-adjusted). Fallback: OPS-based "
                       "estimate x park_hr_factor. STRONG_YES at p>=14% (vs +600 book).",
        "top_25_by_p_hr": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-hr-yn] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
