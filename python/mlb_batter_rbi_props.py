"""
EdgeStat -- MLB batter RBI yes/no prop.

Common DK line: "Batter to record 1+ RBI yes/no"
Typical book: YES -160 to +130 (depends on batting position/order). Cleanup
hitters and 4/5-spot bats are typically -130 to -180 favorites.

Method:
  Primary: pull pre-computed 1_plus_rbi probability from mlb_batter_logs.props
           (real recent-form data, last-14 games sample).
  Fallback: estimate from OPS proxy + batting order RBI-share weighting:
    expected_RBI_per_PA varies by order:
      4: 0.135 (cleanup) — most RBI opportunities
      5: 0.130
      3: 0.115
      6: 0.105
      2: 0.090
      1: 0.075 (leadoff — fewer RBI chances)
      7-9: 0.065
    expected_RBI = expected_RBI_per_PA * PA * team_run_mult * park_mult
    P(>=1 RBI) = 1 - exp(-expected_RBI)

STRONG_YES at p >= 0.70 (vs -180 book = 64% breakeven), capped at 0.85
STRONG_NO  at p_no >= 0.65 (vs -150 book on NO = 60% breakeven)

Output: data/mlb_batter_rbi_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_rbi_props.json")


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


def _rbi_per_pa_by_order(order: int) -> float:
    return {1: 0.075, 2: 0.090, 3: 0.115, 4: 0.135, 5: 0.130,
            6: 0.105, 7: 0.075, 8: 0.065, 9: 0.060}.get(order, 0.080)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))

    parks = today.get("parks") or {}
    lvr_idx = {(r.get("batter") or "").lower(): r for r in (lvr.get("all_batters") or []) if r.get("batter")}
    blog_idx = {(b.get("name") or "").lower(): b for b in (batter_logs.get("batters") or []) if b.get("name")}

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            team_runs = _safe((g.get(side) or {}).get("runs"), 4.5)
            team_run_mult = max(0.80, min(1.20, team_runs / 4.5))

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # PRIMARY: use real 1_plus_rbi probability from batter logs
                rbi_source = "ops_proxy"
                blog = blog_idx.get((name or "").lower())
                if blog:
                    props = blog.get("props") or {}
                    real_p_rbi = (props.get("1_plus_rbi") or {}).get("p")
                    n_games = blog.get("n_games_logged") or 0
                    if real_p_rbi is not None and n_games >= 8:
                        p_rbi = float(real_p_rbi) * (park_run_factor ** 0.30)
                        p_rbi = max(0.05, min(0.95, p_rbi))
                        rbi_source = "real_last_14"
                        expected_rbi = -math.log(max(1 - p_rbi, 1e-6))

                if rbi_source == "ops_proxy":
                    # FALLBACK: OPS-based estimate
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    ops_mult = max(0.70, min(1.30, season_ops / 0.72))
                    rbi_per_pa = _rbi_per_pa_by_order(order) * ops_mult * team_run_mult * (park_run_factor ** 0.5)
                    pa = _expected_pa(order)
                    expected_rbi = rbi_per_pa * pa
                    p_rbi = 1 - math.exp(-expected_rbi)

                p_no_rbi = 1 - p_rbi

                edge_class = "NONE"
                best_market = None
                # Tighter thresholds since middle-order hitters routinely 60-70% RBI
                if 0.78 <= p_rbi <= 0.88:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "RBI_1PLUS_YES", "p": round(p_rbi, 3),
                                   "fair_odds": _american(p_rbi)}
                elif p_no_rbi >= 0.75 and p_no_rbi <= 0.85:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "RBI_1PLUS_NO", "p": round(p_no_rbi, 3),
                                   "fair_odds": _american(p_no_rbi)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "rbi_source": rbi_source,
                    "expected_rbi": round(expected_rbi, 3),
                    "p_rbi": round(p_rbi, 3),
                    "p_no_rbi": round(p_no_rbi, 3),
                    "fair_yes_odds": _american(p_rbi),
                    "fair_no_odds": _american(p_no_rbi),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_rbi"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Primary: real 1_plus_rbi from batter_logs (last 14 games). "
                       "Fallback: order-weighted RBI/PA * OPS * team_runs * park. "
                       "STRONG_YES p in [0.70, 0.85] (vs -180 book); "
                       "STRONG_NO p_no >= 70% (vs -150 NO).",
        "top_25_by_p_rbi": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[batter-rbi] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
