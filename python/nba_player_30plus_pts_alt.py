"""
EdgeStat -- NBA player 30+/40+ points alternate market.

Popular alt market for stars. Common DK pricing:
  - 30+ pts:
      Jokic / SGA / Luka / Giannis / Embiid: +100 to +200
      Other top scorers (Edwards, Tatum, Brown, Booker, Maxey): +200 to +400
      Mid-tier (Lillard, KD, Mitchell): +300 to +600
  - 40+ pts:
      Elite scorers in great matchups: +500 to +800
      Stars in normal games: +1000+

Method:
  Inherits projected_pts + sigma from nba_player_points_props. Normal CDF on
  29.5 / 39.5 lines.

  STRONG_YES_30 at p in [0.35, 0.55] (vs +200 book = 33.3%)
  STRONG_YES_40 at p in [0.10, 0.22] (vs +500 book = 16.7%)

Output: data/nba_player_30plus_pts_alt.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json")


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
    src = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        proj = _safe(r.get("projected_pts"))
        sigma = _safe(r.get("sigma"), 4.0)
        if proj <= 0: continue

        p_30 = _p_over(proj, sigma, 29.5)
        p_35 = _p_over(proj, sigma, 34.5)
        p_40 = _p_over(proj, sigma, 39.5)
        p_50 = _p_over(proj, sigma, 49.5)

        edges: List[Dict[str, Any]] = []
        if 0.35 <= p_30 <= 0.55:
            edges.append({"market": "PTS_30PLUS_YES",
                          "line": 29.5, "p": round(p_30, 3),
                          "fair_odds": _american(p_30)})
        if 0.10 <= p_40 <= 0.22:
            edges.append({"market": "PTS_40PLUS_YES",
                          "line": 39.5, "p": round(p_40, 3),
                          "fair_odds": _american(p_40)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "team": r.get("team"),
            "projected_pts": round(proj, 2),
            "sigma": round(sigma, 2),
            "p_30plus": round(p_30, 3),
            "p_35plus": round(p_35, 3),
            "p_40plus": round(p_40, 3),
            "p_50plus": round(p_50, 3),
            "fair_yes_30plus": _american(p_30),
            "fair_yes_40plus": _american(p_40) if p_40 > 0.005 else None,
            "alt_edges": edges,
            "edge_class": edge_class,
        })

    out_rows.sort(key=lambda r: -r["p_30plus"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 29.5/34.5/39.5/49.5 lines from projected_pts + "
                       "sigma. STRONG_YES_30 p in [0.35, 0.55] vs +200 book; "
                       "STRONG_YES_40 p in [0.10, 0.22] vs +500 book.",
        "top_15_by_p_30plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-30pts] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
