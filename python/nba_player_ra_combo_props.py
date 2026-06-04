"""
EdgeStat -- NBA player Rebounds + Assists combo prop.

Distinct from PRA. Popular DK combo for guards and forwards. Common lines:
  - Trae Young R+A: 10.5-12.5 (8 ast, 3 reb avg)
  - Haliburton R+A: 13.5
  - Jokic R+A: 22.5 (13 reb, 10 ast)

Method:
  Inherits projected_reb + projected_ast from main NBA modules. Sigma
  combined via sqrt(sig_R^2 + sig_A^2) * 1.0 (assume near-independent).

  STRONG when 10%+ edge vs -120 book.

Output: data/nba_player_ra_combo_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_ra_combo_props.json")


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
    reb_src = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    ast_src = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))

    reb_idx = {(r.get("player") or "").lower(): r
               for r in (reb_src.get("rows") or []) if isinstance(r, dict)}
    ast_idx = {(r.get("player") or "").lower(): r
               for r in (ast_src.get("rows") or []) if isinstance(r, dict)}

    common = set(reb_idx.keys()) & set(ast_idx.keys())

    out_rows: List[Dict[str, Any]] = []
    for name in common:
        rr = reb_idx[name]
        ar = ast_idx[name]
        proj_reb = _safe(rr.get("projected_reb"))
        proj_ast = _safe(ar.get("projected_ast"))
        sig_reb = _safe(rr.get("sigma"), 2.5)
        sig_ast = _safe(ar.get("sigma"), 1.8)
        if proj_reb <= 0 or proj_ast <= 0: continue

        proj_combined = proj_reb + proj_ast
        sigma_combined = math.sqrt(sig_reb**2 + sig_ast**2) * 1.0

        base_line = round(proj_combined * 2) / 2
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        for offset in (-2.0, -1.0, -0.5, 0, 0.5, 1.0, 2.0):
            line = base_line + offset
            if line < 4.5: continue
            p_over = _p_over(proj_combined, sigma_combined, line)
            p_under = 1 - p_over
            for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                if 0.62 <= p <= 0.72:
                    edge_amt = p - 0.545
                    if edge_amt > best_edge:
                        best_edge = edge_amt
                        best_market = {"market": f"RA_{direction}_{line}",
                                       "line": line, "direction": direction,
                                       "p": round(p, 3),
                                       "fair_odds": _american(p)}
                        edge_class = "STRONG"

        out_rows.append({
            "matchup": rr.get("matchup"),
            "game_date": rr.get("game_date"),
            "player": rr.get("player"),
            "team": rr.get("team"),
            "projected_reb": round(proj_reb, 2),
            "projected_ast": round(proj_ast, 2),
            "projected_ra": round(proj_combined, 2),
            "sigma_combined": round(sigma_combined, 2),
            "best_market": best_market,
            "edge_class": edge_class,
        })

    out_rows.sort(key=lambda r: -r["projected_ra"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "R+A combo = projected_reb + projected_ast (from main NBA "
                       "modules). Sigma combined = sqrt(sig_R^2 + sig_A^2). "
                       "STRONG when 10%+ edge vs -120 book.",
        "top_15_by_ra": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-ra] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
