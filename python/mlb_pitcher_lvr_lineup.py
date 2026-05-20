"""
EdgeStat -- MLB pitcher LvR splits weighted by opposing lineup handedness.

matchups.json already has each starter's vsL / vsR season splits (K/9,
BAA, FIP). This module:
   1. Counts how many lefty vs righty batters in the opposing lineup
   2. Weights the pitcher's projected K/9 = (Lpct * k9_vsL) + (Rpct * k9_vsR)
   3. Compares to the pitcher's overall season K/9 to detect mismatches
      (e.g. R-heavy lineup vs a pitcher who dominates RHH)

Then re-prices k_over_X.5 lines using the lineup-adjusted K/9 projection
and surfaces the biggest divergences vs naive season K/9.

Output: data/mlb_pitcher_lvr_lineup.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_lvr_lineup.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _lineup_handedness(lineup: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Count L/R/S batters in lineup. ESPN doesn't always have bat-hand on
    the lineup entries, so we use a placeholder estimate: ~30% L, ~70% R
    for MLB (rough overall split). This is approximate -- ideally we'd
    pull each batter's batting hand from MLB Stats API."""
    n = len(lineup)
    if n == 0: return {"n_L": 0, "n_R": 0, "n_S": 0, "L_pct": 0.30, "R_pct": 0.70}
    # ESPN lineup entries have 'bat_hand' in some cases; we accept that if present
    n_L = sum(1 for b in lineup if (b.get("bat_hand") or "").upper() == "L")
    n_R = sum(1 for b in lineup if (b.get("bat_hand") or "").upper() == "R")
    n_S = sum(1 for b in lineup if (b.get("bat_hand") or "").upper() == "S")
    # If ESPN didn't give us hand data, fallback to typical 30/70 split
    if n_L + n_R + n_S == 0:
        return {"n_L": 0, "n_R": 0, "n_S": 0, "L_pct": 0.30, "R_pct": 0.70,
                "estimated": True}
    total = n_L + n_R + n_S
    # Switch-hitters bat opposite of pitcher hand -- they always "play to the lefty side"
    return {
        "n_L": n_L, "n_R": n_R, "n_S": n_S,
        "L_pct": (n_L + n_S * 0.5) / total,   # treat S as half-L for ease
        "R_pct": (n_R + n_S * 0.5) / total,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    pitchers_out: List[Dict[str, Any]] = []

    for g in (matchups.get("games") or []):
        mu = g.get("matchup")
        home_sp = g.get("home_pitcher") or {}
        away_sp = g.get("away_pitcher") or {}
        lineups = g.get("lineups") or {}
        home_lu = lineups.get("home") or []
        away_lu = lineups.get("away") or []

        for sp_raw, opp_lineup, side in (
            (home_sp, away_lu, "HOME"),
            (away_sp, home_lu, "AWAY"),
        ):
            if not isinstance(sp_raw, dict): continue
            splits = sp_raw.get("splits") or {}
            vsL = splits.get("vsL") or {}
            vsR = splits.get("vsR") or {}
            season = sp_raw.get("season") or {}

            season_k9 = season.get("k9")
            season_ip = season.get("ip") or 0
            season_starts = season.get("starts") or 1
            avg_ip_per_start = season_ip / max(1, season_starts)
            if not season_k9 or season_k9 <= 0: continue

            k9_vsL = vsL.get("k9")
            k9_vsR = vsR.get("k9")
            if k9_vsL is None or k9_vsR is None: continue

            # Lineup handedness
            handedness = _lineup_handedness(opp_lineup)
            L_pct = handedness["L_pct"]
            R_pct = handedness["R_pct"]

            # Lineup-weighted K/9 projection
            proj_k9 = L_pct * k9_vsL + R_pct * k9_vsR
            # vs season
            k9_delta = proj_k9 - season_k9
            # Expected K per start
            proj_k = proj_k9 * avg_ip_per_start / 9.0
            naive_k = season_k9 * avg_ip_per_start / 9.0

            # Re-price K props using lineup-adjusted K/9
            k_props_adjusted: Dict[str, Any] = {}
            for line in (4.5, 5.5, 6.5, 7.5, 8.5):
                p_adj = _poisson_p_over(proj_k, line)
                p_naive = _poisson_p_over(naive_k, line)
                if 0.10 < p_adj < 0.90:
                    k_props_adjusted[f"k_over_{line}"] = {
                        "line": line,
                        "p_adj": round(p_adj, 4),
                        "p_naive_season": round(p_naive, 4),
                        "p_delta_pp": round((p_adj - p_naive) * 100, 2),
                        "fair_over_adj": _american(p_adj),
                        "fair_under_adj": _american(1 - p_adj),
                    }

            pitchers_out.append({
                "matchup": mu,
                "side": side,
                "pitcher": sp_raw.get("name"),
                "hand": sp_raw.get("hand"),
                "season_k9": round(season_k9, 2),
                "vsL_k9": round(k9_vsL, 2),
                "vsR_k9": round(k9_vsR, 2),
                "lineup_L_pct": round(L_pct, 3),
                "lineup_R_pct": round(R_pct, 3),
                "lineup_handedness_known": not handedness.get("estimated", False),
                "lineup_adjusted_k9": round(proj_k9, 2),
                "k9_delta_vs_season": round(k9_delta, 2),
                "avg_ip_per_start": round(avg_ip_per_start, 2),
                "projected_k_per_start": round(proj_k, 2),
                "naive_k_per_start": round(naive_k, 2),
                "k_props_adjusted": k_props_adjusted,
            })

    # Surface biggest deltas (lineup mismatch -> reprice opportunity)
    big_boost = sorted([p for p in pitchers_out if p["k9_delta_vs_season"] > 0.5],
                        key=lambda p: -p["k9_delta_vs_season"])
    big_fade = sorted([p for p in pitchers_out if p["k9_delta_vs_season"] < -0.5],
                       key=lambda p: p["k9_delta_vs_season"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_pitchers": len(pitchers_out),
        "n_boost_pitchers": len(big_boost),
        "n_fade_pitchers": len(big_fade),
        "top_boost": big_boost[:10],
        "top_fade": big_fade[:10],
        "all_pitchers": pitchers_out,
        "note": ("Lineup-weighted K/9 projection: pitcher's vsL/vsR K/9 splits "
                  "applied to the opposing lineup's L/R composition. When the "
                  "weighted K/9 diverges materially from naive season K/9, "
                  "the K-prop line is mispriced."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB pitcher LvR x lineup: {p['n_pitchers']} starters analyzed")
    print(f"  K/9 boost vs season (R-heavy lineup vs vsR-dominant): {p['n_boost_pitchers']}")
    print(f"  K/9 fade vs season: {p['n_fade_pitchers']}")
    if p["top_boost"]:
        print(f"\n  Top 5 K/9 BOOST pitchers (lineup-adjusted K/9 > season):")
        for x in p["top_boost"][:5]:
            print(f"    {x['pitcher'][:22]:22s} season K/9 {x['season_k9']:.2f} -> lineup-adj {x['lineup_adjusted_k9']:.2f} (d {x['k9_delta_vs_season']:+.2f})")
    if p["top_fade"]:
        print(f"\n  Top 5 K/9 FADE pitchers:")
        for x in p["top_fade"][:5]:
            print(f"    {x['pitcher'][:22]:22s} season K/9 {x['season_k9']:.2f} -> lineup-adj {x['lineup_adjusted_k9']:.2f} (d {x['k9_delta_vs_season']:+.2f})")
