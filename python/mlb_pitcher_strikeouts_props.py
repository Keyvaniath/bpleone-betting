"""
EdgeStat -- MLB pitcher strikeouts (K) prop projections.

THE most popular MLB pitcher prop. Common DK lines: 4.5, 5.5, 6.5, 7.5, 8.5 K's.

Method:
  expected_K = pitcher_avg_K * lineup_K_rate_mult * park_mult
  Then Poisson at nearest 0.5 line within 1.0 of expected.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

The mlb_pitcher_logs.json already has pre-computed k_over_X.5 props per pitcher.
This module consumes those, applies opponent + park adjustments, and surfaces
STRONG edges with proper line-distance filtering.

Output: data/mlb_pitcher_strikeouts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

import mlb_weather_factor as _WX   # live weather -> run-environment multiplier


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json")

LEAGUE_K_RATE = 0.225  # league avg K% per PA


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
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _lineup_k_rate(lineup: List[Dict[str, Any]], lvr_idx: Dict[str, Dict[str, Any]]) -> float:
    """Estimate opposing lineup K-rate from per-batter splits."""
    if not lineup: return LEAGUE_K_RATE
    total_k_rate = 0.0
    count = 0
    for b in lineup:
        if not isinstance(b, dict): continue
        name = (b.get("name") or b.get("fullName") or "").lower()
        lvr_row = lvr_idx.get(name, {})
        # Estimate: derived from season_ops; lower OPS = higher K rate
        ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
        # Inverse relationship: K rate ~ 0.30 - 0.10 * (ops - 0.7)
        k_rate = max(0.15, min(0.35, 0.30 - 0.12 * (ops - 0.7)))
        total_k_rate += k_rate
        count += 1
    return total_k_rate / count if count else LEAGUE_K_RATE


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))

    parks = today.get("parks") or {}
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
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        # K-friendly park factor: higher elevation/colder air -> more K's
        park_k_factor = _safe((park_info or {}).get("k_factor"), 1.0) or 1.0
        # Live weather: good carry favors hitters -> slightly fewer K (k_mult<1);
        # cold wind-in nudges K up. Neutral 1.0 indoors / when weather is missing.
        wx = _WX.pitcher_weather_factors(g.get("weather"))
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            starter_info = (g.get(side) or {}).get("starter") or g.get(f"{side}_pitcher")
            if isinstance(starter_info, str):
                starter_name = starter_info
            elif isinstance(starter_info, dict):
                starter_name = starter_info.get("name") or starter_info.get("fullName")
            else:
                starter_name = None
            if not starter_name: continue

            pitcher_row = pitcher_idx.get(starter_name.lower())
            if not pitcher_row: continue

            opp_side = "away" if side == "home" else "home"
            opp_lineup = lineups.get(opp_side) or []
            opp_k_rate = _lineup_k_rate(opp_lineup, lvr_idx)
            opp_k_mult = opp_k_rate / LEAGUE_K_RATE

            stats = pitcher_row.get("stats") or {}
            avg_k = _safe(stats.get("avg_k"), 5.5)
            expected_k = avg_k * opp_k_mult * park_k_factor * wx["k_mult"]

            # Only evaluate nearest 0.5 line within 1.0 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(expected_k * 2) / 2
            # Lines exist at .5 increments (4.5, 5.5, 6.5, etc.)
            candidate_lines = [base_line - 0.5, base_line, base_line + 0.5]
            for line in candidate_lines:
                if line < 2.5 or line > 12.5: continue
                if abs(expected_k - line) > 1.0: continue
                # Adjust line down to nearest .5 boundary if it's .0
                if line == int(line): line = line - 0.5  # convert 6.0 -> 5.5
                p_over = _poisson_at_least(int(line) + 1, expected_k)
                p_under = 1 - p_over
                # STRONG: 10%+ edge vs -120 book (54.5% breakeven), capped at 72%
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"K_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"K_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": matchup_str,
                "pitcher": starter_name,
                "team": pitcher_row.get("team_abbr"),
                "side": side,
                "season_avg_k": avg_k,
                "k_per_9": stats.get("k_per_9"),
                "opp_k_rate": round(opp_k_rate, 3),
                "opp_k_mult": round(opp_k_mult, 3),
                "park_k_factor": park_k_factor,
                "weather_k_mult": wx["k_mult"],
                "weather": {"carry": wx["carry"], "temp_f": wx["temp_f"], "indoor": wx["is_indoor"]},
                "expected_k": round(expected_k, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["expected_k"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "expected_K = avg_K x opp_lineup_K_mult x park_K_factor x weather_K_mult "
                       "(carry/temp; neutral indoors). Poisson at nearest 0.5 line within 1.0 of "
                       "projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-K] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong edges -> {OUT}")
