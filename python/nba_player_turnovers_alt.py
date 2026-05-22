"""
EdgeStat -- NBA player turnovers ALT markets (4+, 5+).

Niche but viable DK alt for high-usage guards (Trae, Doncic, Brunson, SGA).
Typical pricing:
  - 4+ TOs: +180 to +350 for star guards on B2B nights
  - 5+ TOs: +400+ (rare; only Trae/Luka volumes)

Method:
  Inherits projected_tov + sigma from nba_player_turnovers_props. Normal CDF.

  STRONG_YES_4 at p in [0.28, 0.45]
  STRONG_YES_5 at p in [0.12, 0.25]

Output: data/nba_player_turnovers_alt.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_turnovers_alt.json")


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
    src = _load(os.path.join(DATA_DIR, "nba_player_turnovers_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        proj = _safe(r.get("projected_tov"))
        sigma = _safe(r.get("sigma"), 1.5)
        if proj <= 0: continue

        p_4 = _p_over(proj, sigma, 3.5)
        p_5 = _p_over(proj, sigma, 4.5)

        edges: List[Dict[str, Any]] = []
        if 0.28 <= p_4 <= 0.45:
            edges.append({"market": "TOV_4PLUS_YES", "line": 3.5,
                          "p": round(p_4, 3), "fair_odds": _american(p_4)})
        if 0.12 <= p_5 <= 0.25:
            edges.append({"market": "TOV_5PLUS_YES", "line": 4.5,
                          "p": round(p_5, 3), "fair_odds": _american(p_5)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "team": r.get("team"),
            "projected_tov": round(proj, 2),
            "sigma": round(sigma, 2),
            "p_4plus": round(p_4, 3),
            "p_5plus": round(p_5, 3),
            "fair_yes_4plus": _american(p_4),
            "fair_yes_5plus": _american(p_5) if p_5 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
            "tov_source": r.get("tov_source") or "fallback",
        })

    out_rows.sort(key=lambda r: -r["p_4plus"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 3.5/4.5 lines from projected_tov + sigma. "
                       "STRONG_YES_4 [0.28, 0.45], _5 [0.12, 0.25].",
        "top_15_by_p_4plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tov-alt] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
