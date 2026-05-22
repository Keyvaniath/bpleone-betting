"""
EdgeStat -- NBA player assists ALT markets (10+, 12+, 15+).

Common DK alts beyond the standard 0.5-step assists line:
  - 10+ assists: -110 for Haliburton/Trae, +130 for SGA, +300+ for others
  - 12+ assists: +200 for Trae, +500 for most playmakers
  - 15+ assists: +800+ (very rare; Doncic / Haliburton ceiling)

Method:
  Inherits projected_ast + sigma from nba_player_assists_props. Normal CDF
  for each threshold.

  STRONG_YES_10 at p in [0.55, 0.72]
  STRONG_YES_12 at p in [0.28, 0.45]
  STRONG_YES_15 at p in [0.08, 0.20]

Output: data/nba_player_assists_alt_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_assists_alt_props.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


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
    src = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        proj = r.get("projected_ast")
        sigma = r.get("sigma") or 2.0
        if proj is None: continue
        try:
            proj = float(proj); sigma = float(sigma)
        except Exception:
            continue

        p_10 = _p_over(proj, sigma, 9.5)
        p_12 = _p_over(proj, sigma, 11.5)
        p_15 = _p_over(proj, sigma, 14.5)

        edges: List[Dict[str, Any]] = []
        if 0.55 <= p_10 <= 0.72:
            edges.append({"market": "AST_10PLUS_YES", "line": 9.5,
                          "p": round(p_10, 3), "fair_odds": _american(p_10)})
        if 0.28 <= p_12 <= 0.45:
            edges.append({"market": "AST_12PLUS_YES", "line": 11.5,
                          "p": round(p_12, 3), "fair_odds": _american(p_12)})
        if 0.08 <= p_15 <= 0.20:
            edges.append({"market": "AST_15PLUS_YES", "line": 14.5,
                          "p": round(p_15, 3), "fair_odds": _american(p_15)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "team": r.get("team"),
            "projected_ast": round(proj, 2),
            "sigma": round(sigma, 2),
            "p_10plus": round(p_10, 3),
            "p_12plus": round(p_12, 3),
            "p_15plus": round(p_15, 3),
            "fair_yes_10": _american(p_10),
            "fair_yes_12": _american(p_12),
            "fair_yes_15": _american(p_15) if p_15 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
            "apg_source": r.get("apg_source") or "fallback",
        })

    out_rows.sort(key=lambda r: -r["p_10plus"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 9.5/11.5/14.5 lines from projected_ast + sigma. "
                       "STRONG_YES_10 [0.55, 0.72], _12 [0.28, 0.45], _15 [0.08, 0.20].",
        "top_15_by_p_10plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ast-alt] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
