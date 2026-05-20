"""
EdgeStat -- MLB Pitcher Walks (BB) prop projections.

Walks-allowed is one of the more reliable pitcher props because BB% is one
of the stickiest pitcher stats year-over-year (correlation ~0.65). Common lines:
  - Walks 1.5 over/under
  - Walks 2.5 over/under
  - Walks 3.5 over/under (for control issues / wild starters)

Approach:
  - Per-PA BB rate from pitcher logs (BB / TBF)
  - Adjusted by opposing lineup OBP (high-OBP teams draw more walks)
  - Adjusted by umpire's strike zone (wide zones reduce walks)
  - E[BB per start] = BB_per_PA × expected_TBF
  - Poisson P(BB >= 1), P(BB >= 2), P(BB >= 3), P(BB >= 4)

Edge tagging:
  - STRONG_OVER_2_5: P(BB >= 3) >= 0.55 (-122 fair vs typical -120 line)
  - STRONG_UNDER_2_5: P(BB <= 2) >= 0.65
  - STRONG_UNDER_1_5: P(BB <= 1) >= 0.45

Source data:
  - data/matchups.json
  - data/mlb_pitcher_logs.json
  - data/umpires.json (if available)

Output: data/mlb_pitcher_walks_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_walks_props.json")

LEAGUE_BB_PCT = 0.083  # 8.3% of PA result in walks (league avg 2024)
LEAGUE_OBP = 0.317


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


def _poisson_at_most(k: int, lam: float) -> float:
    return 1.0 - _poisson_at_least(k + 1, lam)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    umpires = _load(os.path.join(DATA_DIR, "umpires.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    ump_by_game = {}  # gamePk -> umpire info
    for u in (umpires.get("umpires") or umpires.get("rows") or []):
        gpk = u.get("gamePk")
        if gpk: ump_by_game[gpk] = u

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]
        # Opposing lineup OBP
        home_obp = _safe((g.get("home") or {}).get("obp"), LEAGUE_OBP)
        away_obp = _safe((g.get("away") or {}).get("obp"), LEAGUE_OBP)

        # Umpire strike-zone size: bigger zone = fewer walks
        ump_zone_mult = 1.0
        ump = ump_by_game.get(g.get("gamePk"))
        if ump:
            bb_factor = _safe(ump.get("bb_factor"), 1.0) or 1.0
            ump_zone_mult = bb_factor

        for side in ("home", "away"):
            opp_obp = away_obp if side == "home" else home_obp
            p_raw = g.get(f"{side}_pitcher")
            name = p_raw if isinstance(p_raw, str) else (p_raw or {}).get("name")
            pitcher = p_by_name.get((name or "").lower())
            if not pitcher and isinstance(p_raw, dict): pitcher = p_raw
            if not pitcher: continue

            # Pitcher BB rate per PA
            season_bb = _safe(pitcher.get("walks") or pitcher.get("bb"), 0)
            season_tbf = _safe(pitcher.get("batters_faced") or pitcher.get("tbf"), 0)
            if season_tbf > 0:
                bb_per_pa = season_bb / season_tbf
            else:
                # Fallback: BB/9 -> BB per PA (assume ~4.1 PA per inning)
                bb_per_9 = _safe(pitcher.get("bb_per_9") or pitcher.get("season", {}).get("bb_per_9"), 3.0)
                bb_per_pa = bb_per_9 / 9 / 4.1
            # Clamp
            bb_per_pa = max(0.03, min(0.18, bb_per_pa))

            # Opposing-lineup OBP adjustment (linear)
            obp_mult = max(0.80, min(1.25, opp_obp / LEAGUE_OBP))
            # Umpire strike-zone adjustment
            bb_per_pa_adj = bb_per_pa * obp_mult * ump_zone_mult

            # Expected TBF in the start (~21-24 for a 5-6 IP start)
            avg_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.5)
            expected_tbf = avg_ip * 4.2  # ~4.2 PA per inning faced

            expected_bb = bb_per_pa_adj * expected_tbf
            p_over_1_5 = _poisson_at_least(2, expected_bb)
            p_over_2_5 = _poisson_at_least(3, expected_bb)
            p_over_3_5 = _poisson_at_least(4, expected_bb)
            p_under_1_5 = _poisson_at_most(1, expected_bb)
            p_under_2_5 = _poisson_at_most(2, expected_bb)

            # Book lines for BB props are heavily juiced. Only call STRONG when model
            # significantly beats typical book pricing:
            #  BB OVER 2.5 book ~ +110 (47.6% breakeven); STRONG if p >= 55%
            #  BB UNDER 2.5 book ~ -200 (66.7% breakeven); STRONG if p >= 78%
            #  BB OVER 1.5 book ~ -180 (64.3% breakeven); STRONG if p >= 75%
            edge_class = "NONE"
            best_market = None
            if p_over_2_5 >= 0.55:
                edge_class = "STRONG_OVER_2_5"
                best_market = {"market": "BB_OVER_2_5", "p": p_over_2_5, "fair_odds": _american(p_over_2_5)}
            elif p_under_2_5 >= 0.78:
                edge_class = "STRONG_UNDER_2_5"
                best_market = {"market": "BB_UNDER_2_5", "p": p_under_2_5, "fair_odds": _american(p_under_2_5)}
            elif p_over_1_5 >= 0.75:
                edge_class = "STRONG_OVER_1_5"
                best_market = {"market": "BB_OVER_1_5", "p": p_over_1_5, "fair_odds": _american(p_over_1_5)}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "opp_team": away if side == "home" else home,
                "opp_obp": opp_obp,
                "bb_per_pa": round(bb_per_pa, 4),
                "bb_per_pa_adjusted": round(bb_per_pa_adj, 4),
                "expected_tbf": round(expected_tbf, 1),
                "expected_bb": round(expected_bb, 2),
                "p_over_1_5": round(p_over_1_5, 3),
                "p_over_2_5": round(p_over_2_5, 3),
                "p_over_3_5": round(p_over_3_5, 3),
                "p_under_1_5": round(p_under_1_5, 3),
                "p_under_2_5": round(p_under_2_5, 3),
                "umpire_bb_factor": round(ump_zone_mult, 3),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else r["expected_bb"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "league_bb_pct": LEAGUE_BB_PCT,
        "method_note": "Per-pitcher BB/PA × opp OBP × umpire zone × expected_TBF. "
                       "Poisson for over/under probabilities.",
        "starters": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[walks-props] {o['n_starters']} starters, {o['n_strong_edges']} strong edges -> {OUT}")
