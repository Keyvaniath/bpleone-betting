"""
EdgeStat -- MLB total strikeouts in game O/U prop.

DK popular alt: 'Total K in game over/under N.5' (common lines: 14.5, 15.5,
16.5). Sum of both starters' Ks + bullpen Ks across all innings.

Method:
  Combined K = sum of (expected_K_starter + bullpen_K)
  where bullpen_K = (bullpen_K9 / 9) * remaining_IP (~10.0 K9 league avg)

  STRONG-gated on deviation from league baseline ~16 Ks/game.

Output: data/mlb_total_K_game.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_total_K_game.json")

LEAGUE_K_TOTAL_GAME = 16.0
BULLPEN_K9 = 10.0


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
    k_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))

    k_idx = {(r.get("pitcher") or "").lower(): r
             for r in (k_props.get("rows") or []) if isinstance(r, dict)}
    outs_idx = {(r.get("pitcher") or "").lower(): r
                for r in (outs_props.get("rows") or []) if isinstance(r, dict)}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        total_K = 0.0
        details: Dict[str, Any] = {}
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_l = sp_name.lower()
            sp_k = _safe(k_idx.get(sp_l, {}).get("expected_k"), 5.5)
            x_outs = _safe(outs_idx.get(sp_l, {}).get("expected_outs"), 16.0)
            sp_IP = x_outs / 3.0
            bullpen_IP = max(0, 9 - sp_IP)
            bullpen_K = (BULLPEN_K9 / 9.0) * bullpen_IP
            side_K = sp_k + bullpen_K
            total_K += side_K
            details[side] = {
                "starter": sp_name,
                "sp_K": round(sp_k, 1),
                "sp_IP": round(sp_IP, 1),
                "bullpen_K": round(bullpen_K, 1),
                "side_total_K": round(side_K, 1),
            }

        sigma = max(2.5, math.sqrt(total_K))

        # Find best edge — gated on deviation
        deviates = abs(total_K - LEAGUE_K_TOTAL_GAME) >= 1.5
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        if deviates:
            base_line = round(total_K * 2) / 2
            for offset in (-0.5, 0.5):
                line = base_line + offset
                if line < 5 or line > 30: continue
                p_o = _p_over(total_K, sigma, line)
                p_u = 1 - p_o
                for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                    if 0.58 <= p <= 0.68:
                        edge_amt = p - 0.524
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {"market": f"TOTAL_K_{direction}_{line}",
                                           "line": line, "direction": direction,
                                           "p": round(p, 3),
                                           "fair_odds": _american(p)}
                            edge_class = "STRONG"

        rows.append({
            "matchup": matchup,
            "expected_K_total": round(total_K, 2),
            "sigma": round(sigma, 2),
            "deviates_from_baseline": deviates,
            "details": details,
            "best_market": best_market,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: -r["expected_K_total"])
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Total K = sum across both teams of (sp_expected_K + "
                       "bullpen_K9/9 * remaining_IP). League baseline ~16/game. "
                       "Baseline-gated STRONG when deviates >= 1.5.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[K-game] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
