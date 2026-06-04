"""
EdgeStat -- NBA player Points + Assists combo prop.

Distinct from PRA (P+R+A) and PR (P+R) — this is the popular P+A combo for
playmakers and guards. Common DK lines:
  - Trae Young: 30.5-34.5
  - Haliburton: 25.5-29.5
  - Brunson: 30.5-34.5
  - LeBron: 30.5+

Method:
  Inherits projected_pts (PPG model) + projected_ast (assists model).
  Sigma combined = sqrt(sigma_pts^2 + sigma_ast^2) * 1.05 for small positive
  PTS/AST correlation (high-usage games elevate both).

  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_player_pa_combo_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_pa_combo_props.json")


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
    pts_src = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    ast_src = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))

    pts_idx = {(r.get("player") or "").lower(): r
               for r in (pts_src.get("rows") or []) if isinstance(r, dict)}
    ast_idx = {(r.get("player") or "").lower(): r
               for r in (ast_src.get("rows") or []) if isinstance(r, dict)}

    common = set(pts_idx.keys()) & set(ast_idx.keys())

    out_rows: List[Dict[str, Any]] = []
    for name in common:
        pts_r = pts_idx[name]
        ast_r = ast_idx[name]
        proj_pts = _safe(pts_r.get("projected_pts"))
        proj_ast = _safe(ast_r.get("projected_ast"))
        sig_pts = _safe(pts_r.get("sigma"), 4.0)
        sig_ast = _safe(ast_r.get("sigma"), 1.8)
        if proj_pts <= 0 or proj_ast <= 0: continue

        proj_combined = proj_pts + proj_ast
        sigma_combined = math.sqrt(sig_pts**2 + sig_ast**2) * 1.05

        base_line = round(proj_combined * 2) / 2
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        for offset in (-2.0, -1.0, 0, 1.0, 2.0):
            line = base_line + offset
            if line < 5.5: continue
            p_over = _p_over(proj_combined, sigma_combined, line)
            p_under = 1 - p_over
            for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                if 0.62 <= p <= 0.72:
                    edge_amt = p - 0.545
                    if edge_amt > best_edge:
                        best_edge = edge_amt
                        best_market = {"market": f"PA_{direction}_{line}",
                                       "line": line, "direction": direction,
                                       "p": round(p, 3),
                                       "fair_odds": _american(p)}
                        edge_class = "STRONG"

        out_rows.append({
            "matchup": pts_r.get("matchup"),
            "game_date": pts_r.get("game_date"),
            "player": pts_r.get("player"),
            "team": pts_r.get("team"),
            "projected_pts": round(proj_pts, 2),
            "projected_ast": round(proj_ast, 2),
            "projected_pa": round(proj_combined, 2),
            "sigma_combined": round(sigma_combined, 2),
            "best_market": best_market,
            "edge_class": edge_class,
        })

    out_rows.sort(key=lambda r: -r["projected_pa"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "P+A combo = projected_pts + projected_ast (from main NBA modules). "
                       "Sigma combined = sqrt(sig_p^2 + sig_a^2) * 1.05. "
                       "STRONG when p in [0.62, 0.72] vs -120 book.",
        "top_15_by_pa": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pa] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
