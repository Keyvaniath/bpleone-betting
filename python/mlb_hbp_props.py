"""
EdgeStat -- MLB hit-by-pitch (HBP) yes/no prop.

Common DK line: "Batter to be hit by pitch yes/no" (typically +600 YES, -800 NO).
Massive longshot — league average HBP/PA ~0.012 (1.2%).

Method:
  expected_HBP = expected_PA * batter_hbp_rate * opp_pitcher_hbp_rate_mult
  batter_hbp_rate: per-batter HBP/PA from season totals (proxy via crowding-plate
                   batters: anyone hitting >5 HBP/season is in the top 20%)
  Top HBP rates (per PA, multi-year): Anthony Rizzo (3.5%), MJ Melendez (3.0%),
  Brandon Marsh (2.8%), Tyler Soderstrom (2.5%), etc.

  P(>= 1 HBP) = 1 - exp(-expected_HBP)

  STRONG_YES when our P(HBP) >= 0.04 (vs +1500 book = 6.25% breakeven for top HBP)
  Otherwise skip — most batters under 1.5% per game, not worth surfacing.

Output: data/mlb_hbp_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_hbp_props.json")

LEAGUE_HBP_PER_PA = 0.012

# 2024-25 elevated HBP rates per PA (multi-year averages)
HIGH_HBP_BATTERS = {
    "anthony rizzo":        0.035,
    "mj melendez":          0.030,
    "brandon marsh":        0.028,
    "tyler soderstrom":     0.025,
    "starling marte":       0.024,
    "yordan alvarez":       0.022,
    "ronald acuna jr":      0.021,
    "andrew benintendi":    0.020,
    "george springer":      0.020,
    "mookie betts":         0.019,
    "j.t. realmuto":        0.019,
    "ozzie albies":         0.018,
    "marcus semien":        0.018,
    "shohei ohtani":        0.017,
    "francisco lindor":     0.017,
    "matt olson":           0.017,
    "willson contreras":    0.016,
    "salvador perez":       0.015,
    "rafael devers":        0.015,
    "michael harris ii":    0.014,
}


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
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        lineups = g.get("lineups") or {}

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher_name = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")
            opp_p = p_by_name.get((opp_pitcher_name or "").lower(), {})
            # Pitcher HBP rate proxy: BB/9 * 0.10 (control issues correlate)
            opp_stats = opp_p.get("stats") or {}
            opp_bb_per_9 = _safe(opp_stats.get("bb_per_9"), 3.2)
            opp_hbp_mult = max(0.6, min(1.8, opp_bb_per_9 / 3.2))

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9

                hbp_rate = HIGH_HBP_BATTERS.get((name or "").lower(), LEAGUE_HBP_PER_PA)
                pa = _expected_pa(order)
                expected_hbp = pa * hbp_rate * opp_hbp_mult
                p_hbp = 1 - math.exp(-expected_hbp)

                edge_class = "NONE"
                best_market = None
                # STRONG_YES when p >= 9% (vs +1000 book = 9.1% breakeven, real edge required)
                # League avg P(HBP/game) ~5% so ~5% is just baseline, not real edge.
                # Only flag truly elevated HBP-prone batters facing wild pitchers.
                if p_hbp >= 0.09:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "HBP_YES", "p": round(p_hbp, 4),
                                   "fair_odds": _american(p_hbp)}

                if p_hbp < 0.015: continue   # skip super low to avoid noise

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": batter.get("team") or side.upper(),
                    "order": order,
                    "opp_pitcher": opp_pitcher_name,
                    "batter_hbp_rate": round(hbp_rate, 4),
                    "opp_bb_per_9": opp_bb_per_9,
                    "opp_hbp_mult": round(opp_hbp_mult, 3),
                    "expected_pa": pa,
                    "p_hbp": round(p_hbp, 4),
                    "fair_yes_odds": _american(p_hbp),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_hbp"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(HBP>=1) = 1 - exp(-PA * batter_hbp_rate * opp_BB/9_mult). "
                       "STRONG_YES at p>=5% (vs +1100 book ~8.3% breakeven for top "
                       "HBP-prone batters). Tracking the 20 highest career HBP rates.",
        "top_25_by_p_hbp": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hbp] {o['n_batters']} batters, {o['n_strong_edges']} strong edges -> {OUT}")
