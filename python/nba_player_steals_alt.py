"""
EdgeStat -- NBA player steals alt market (2+, 3+, 4+).

DK alt for thieves (Caruso, OG Anunoby, Smart, Holiday).
Companion to blocks_alt.

Method:
  Inherits projected_spg + sigma from nba_player_blocks_steals_props.
  Normal CDF at 1.5/2.5/3.5.

  STRONG_YES_2 at p in [0.35, 0.55]
  STRONG_YES_3 at p in [0.15, 0.28]

Output: data/nba_player_steals_alt.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_steals_alt.json")


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
    src = _load(os.path.join(DATA_DIR, "nba_player_blocks_steals_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        proj_spg = _safe(r.get("projected_steals") or r.get("projected_spg"))
        sigma = _safe(r.get("steals_sigma") or r.get("sigma"), 0.85)
        if proj_spg <= 0: continue

        p_2 = _p_over(proj_spg, sigma, 1.5)
        p_3 = _p_over(proj_spg, sigma, 2.5)
        p_4 = _p_over(proj_spg, sigma, 3.5)

        edges: List[Dict[str, Any]] = []
        if 0.35 <= p_2 <= 0.55:
            edges.append({"market": "STEALS_2PLUS_YES", "line": 1.5,
                          "p": round(p_2, 3), "fair_odds": _american(p_2)})
        if 0.15 <= p_3 <= 0.28:
            edges.append({"market": "STEALS_3PLUS_YES", "line": 2.5,
                          "p": round(p_3, 3), "fair_odds": _american(p_3)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "team": r.get("team"),
            "projected_spg": round(proj_spg, 2),
            "p_2plus_steals": round(p_2, 3),
            "p_3plus_steals": round(p_3, 3),
            "p_4plus_steals": round(p_4, 3),
            "fair_yes_2plus": _american(p_2),
            "fair_yes_3plus": _american(p_3),
            "fair_yes_4plus": _american(p_4) if p_4 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
        })

    out_rows.sort(key=lambda r: -r["p_2plus_steals"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 1.5/2.5/3.5 lines from projected_spg + sigma. "
                       "STRONG_YES_2 [0.35, 0.55], _3 [0.15, 0.28].",
        "top_15_by_p_2plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[steals-alt] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
