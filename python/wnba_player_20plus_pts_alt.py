"""
EdgeStat -- WNBA player 20+/25+ points alternate market.

Popular DK star scorer alt. Typical pricing:
  - 20+ pts: A'ja Wilson / Collier / Stewart -110 to +140 YES
  - 25+ pts: +180 to +300 for elite
  - 30+ pts: +600+ (rare)

Method:
  Inherits projected_pts + sigma from wnba_player_pts_props. Normal CDF.

  STRONG_YES_20 at p in [0.42, 0.62]
  STRONG_YES_25 at p in [0.18, 0.32]
  STRONG_YES_30 at p in [0.06, 0.15]

Output: data/wnba_player_20plus_pts_alt.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_20plus_pts_alt.json")


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


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "wnba_player_pts_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        proj = _safe(r.get("projected_pts"))
        sigma = _safe(r.get("sigma"), 4.5)
        if proj <= 0: continue

        p_20 = _p_over(proj, sigma, 19.5)
        p_25 = _p_over(proj, sigma, 24.5)
        p_30 = _p_over(proj, sigma, 29.5)

        edges: List[Dict[str, Any]] = []
        if 0.42 <= p_20 <= 0.62:
            edges.append({"market": "PTS_20PLUS_YES", "line": 19.5,
                          "p": round(p_20, 3), "fair_odds": _american(p_20)})
        if 0.18 <= p_25 <= 0.32:
            edges.append({"market": "PTS_25PLUS_YES", "line": 24.5,
                          "p": round(p_25, 3), "fair_odds": _american(p_25)})
        if 0.06 <= p_30 <= 0.15:
            edges.append({"market": "PTS_30PLUS_YES", "line": 29.5,
                          "p": round(p_30, 3), "fair_odds": _american(p_30)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "team": r.get("team"),
            "projected_pts": round(proj, 2),
            "sigma": round(sigma, 2),
            "p_20plus": round(p_20, 3),
            "p_25plus": round(p_25, 3),
            "p_30plus": round(p_30, 3),
            "fair_yes_20plus": _american(p_20),
            "fair_yes_25plus": _american(p_25),
            "fair_yes_30plus": _american(p_30) if p_30 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
        })

    out_rows.sort(key=lambda r: -r["p_20plus"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 19.5/24.5/29.5 lines from projected_pts + sigma. "
                       "STRONG_YES_20 [0.42, 0.62], _25 [0.18, 0.32], _30 [0.06, 0.15].",
        "top_15_by_p_20plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-20pts] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
