"""
EdgeStat -- MLB total walks in game O/U prop (150th module milestone).

DK alt: 'Total walks in game over/under N.5' (common lines: 5.5, 6.5, 7.5).

Method:
  Combined expected walks across both starters + bullpen:
    expected_walks_total = (sp_home_bb9/9 * sp_home_IP) +
                           (sp_away_bb9/9 * sp_away_IP) +
                           (bullpen_bb_rate * remaining_innings)

  Use Normal CDF on typical 0.5-step lines.
  STRONG when 8%+ edge vs -110 book.

Output: data/mlb_total_walks_game.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_total_walks_game.json")

LEAGUE_BB9 = 3.10
BULLPEN_BB9 = 3.40  # bullpen slightly higher walk rate than starters


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


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    outs_idx = {(r.get("pitcher") or "").lower(): r
                for r in (outs_props.get("rows") or []) if isinstance(r, dict)}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        total_bb = 0.0
        details: Dict[str, Any] = {}
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue

            sp_row = p_by_name.get(sp_name.lower(), {})
            stats = sp_row.get("stats") or {}
            sp_bb9 = _safe(stats.get("bb_per_9"), LEAGUE_BB9)

            outs_row = outs_idx.get(sp_name.lower(), {})
            x_outs = _safe(outs_row.get("expected_outs") or outs_row.get("xOuts"), 16.0)
            sp_IP = x_outs / 3.0

            sp_walks = (sp_bb9 / 9.0) * sp_IP
            bullpen_IP = max(0, 9 - sp_IP)
            bullpen_walks = (BULLPEN_BB9 / 9.0) * bullpen_IP
            side_walks = sp_walks + bullpen_walks
            total_bb += side_walks
            details[side] = {
                "starter": sp_name, "sp_bb9": round(sp_bb9, 2),
                "sp_IP": round(sp_IP, 1), "sp_walks": round(sp_walks, 2),
                "bullpen_walks": round(bullpen_walks, 2),
                "side_total_walks": round(side_walks, 2),
            }

        sigma = max(1.5, math.sqrt(total_bb))  # Poisson sigma approximation

        # Find best edge across typical lines. Only emit STRONG when the
        # projection meaningfully deviates from league mean (combined BB9 != 3.10).
        # Otherwise the Normal CDF will always show ~60% at offset lines and
        # produce false positives.
        league_baseline = 6.20  # league-avg total walks per game
        deviates_from_baseline = abs(total_bb - league_baseline) >= 0.6
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        if deviates_from_baseline:
            base_line = round(total_bb * 2) / 2
            # Test at projection +/- 0.5 only (immediate neighbors of model)
            for offset in (-0.5, 0.5):
                line = base_line + offset
                if line < 2.5 or line > 12.5: continue
                p_o = _p_over(total_bb, sigma, line)
                p_u = 1 - p_o
                for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                    if 0.58 <= p <= 0.68:
                        edge_amt = p - 0.524  # -110 breakeven
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {"market": f"WALKS_TOTAL_{direction}_{line}",
                                           "line": line, "direction": direction,
                                           "p": round(p, 3),
                                           "fair_odds": _american(p)}
                            edge_class = "STRONG"

        rows.append({
            "matchup": matchup,
            "expected_walks_total": round(total_bb, 2),
            "sigma": round(sigma, 2),
            "details": details,
            "best_market": best_market,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: -r["expected_walks_total"])
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Total walks = sum across both teams of "
                       "(sp_BB9/9 * sp_IP) + (bullpen_BB9/9 * remaining_IP). "
                       "Normal CDF, sigma sqrt(lambda). STRONG when 8%+ edge vs -110 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bb-game] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
