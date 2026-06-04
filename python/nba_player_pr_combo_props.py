"""
EdgeStat -- NBA player Points + Rebounds combo prop.

Different from PRA (P+R+A): this is the P+R only combo, common on DK at lines
typically 28.5 - 45.5 for stars (e.g. Jokic 45.5, Wembanyama 38.5).

Method:
  Inherits projected_pts from nba_player_points_props + projected_reb from
  nba_player_rebounds_props. Combined projection = pts + reb. Sigma combined
  via independent-variance assumption: sqrt(sigma_pts^2 + sigma_reb^2) but
  with a small positive correlation adjustment (high-usage games boost both).

  Effective sigma_combined = sqrt(sigma_pts^2 + sigma_reb^2) * 1.05
  Normal CDF on typical 0.5-step lines around projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_player_pr_combo_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_pr_combo_props.json")


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
    reb_src = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))

    pts_idx = {(r.get("player") or "").lower(): r
               for r in (pts_src.get("rows") or []) if isinstance(r, dict)}
    reb_idx = {(r.get("player") or "").lower(): r
               for r in (reb_src.get("rows") or []) if isinstance(r, dict)}

    # Players appearing in both projections
    common_players = set(pts_idx.keys()) & set(reb_idx.keys())

    out_rows: List[Dict[str, Any]] = []
    for name in common_players:
        pts_r = pts_idx[name]
        reb_r = reb_idx[name]
        proj_pts = _safe(pts_r.get("projected_pts"))
        proj_reb = _safe(reb_r.get("projected_reb"))
        sig_pts = _safe(pts_r.get("sigma"), 4.0)
        sig_reb = _safe(reb_r.get("sigma"), 2.5)
        if proj_pts <= 0 or proj_reb <= 0: continue

        proj_combined = proj_pts + proj_reb
        # Small positive correlation between PTS and REB (~0.20)
        sigma_combined = math.sqrt(sig_pts**2 + sig_reb**2) * 1.05

        # Find typical book lines around projection (0.5-step)
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
                        best_market = {"market": f"PR_{direction}_{line}",
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
            "projected_reb": round(proj_reb, 2),
            "projected_pr": round(proj_combined, 2),
            "sigma_combined": round(sigma_combined, 2),
            "best_market": best_market,
            "edge_class": edge_class,
        })

    out_rows.sort(key=lambda r: -r["projected_pr"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "P+R combo = projected_pts + projected_reb (from main props "
                       "modules). Sigma combined = sqrt(sig_p^2 + sig_r^2) * 1.05 "
                       "(small positive PTS/REB correlation). STRONG when 10%+ edge "
                       "vs -120 book (p in [0.62, 0.72]).",
        "top_15_by_pr": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pr] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
