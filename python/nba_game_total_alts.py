"""
EdgeStat -- NBA game total alternate market (over/under at various lines).

DK common alt lines: 215.5, 220.5, 225.5, 230.5.

Method:
  combined_total = home_proj + away_proj (from nba_team_total_edge).
  Sigma ~ 11 (NBA game total stddev). Normal CDF at common alt lines.

  STRONG when 6%+ edge vs -110 book.

Output: data/nba_game_total_alts.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_game_total_alts.json")


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
    tt_edge = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))
    rows_in = tt_edge.get("rows") or []

    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in rows_in:
        m = r.get("matchup")
        if not m: continue
        proj = _safe(r.get("model_proj_pts_anchored"))
        side = r.get("side")
        entry = by_matchup.setdefault(m, {"matchup": m})
        if side == "HOME":
            entry["home_proj"] = proj
            entry["home_team"] = r.get("team")
        elif side == "AWAY":
            entry["away_proj"] = proj
            entry["away_team"] = r.get("team")

    rows: List[Dict[str, Any]] = []
    for m, g in by_matchup.items():
        home_p = _safe(g.get("home_proj"))
        away_p = _safe(g.get("away_proj"))
        if home_p <= 0 or away_p <= 0: continue
        total = home_p + away_p
        sigma = 11.0

        edges: List[Dict[str, Any]] = []
        for line in (215.5, 220.5, 225.5, 230.5):
            p_o = _p_over(total, sigma, line)
            p_u = 1 - p_o
            for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                if 0.56 <= p <= 0.66:
                    edges.append({"market": f"GAME_TOTAL_{direction}_{line}",
                                   "line": line, "direction": direction,
                                   "p": round(p, 3),
                                   "fair_odds": _american(p)})

        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG_TOTAL" if best_edge else "NONE"

        rows.append({
            "matchup": m,
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_proj": round(home_p, 1),
            "away_proj": round(away_p, 1),
            "model_game_total": round(total, 1),
            "sigma": sigma,
            "best_market": best_edge,
            "edge_class": edge_class,
            "edges_found": edges,
        })

    rows.sort(key=lambda r: -r["model_game_total"])
    strong = [r for r in rows if r["edge_class"] == "STRONG_TOTAL"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "NBA game total = home_proj + away_proj from nba_team_total_edge. "
                       "Tests 215.5/220.5/225.5/230.5 alt lines with sigma 11. "
                       "STRONG when 6%+ edge vs -110 book (p in [0.56, 0.66]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-total] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
