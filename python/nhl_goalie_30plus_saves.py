"""
EdgeStat -- NHL goalie 30+ saves alternate market.

Common DK alt: "Goalie to record 30+ saves yes/no". Especially popular for
high-volume save matchups vs strong offensive teams.

Typical pricing:
  - Elite goalie facing high-shot team: +120 to +180 (35-45% breakeven)
  - Average matchup: +200 to +280 (26-33%)
  - Light schedule expected: +400+ (<20%)

Method:
  Inherits expected_saves from nhl_goalie_saves_props. Normal CDF on the
  30.5 line using sigma scaled to projection.

  STRONG_YES at p_30plus in [0.35, 0.50] (vs +180 book = 35.7%)
  STRONG_NO at p_no_30plus >= 0.75 (vs -300 book = 75%)

Also exposes 35+ and 40+ alts.

Output: data/nhl_goalie_30plus_saves.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_30plus_saves.json")


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
    src = _load(os.path.join(DATA_DIR, "nhl_goalie_saves_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        x_saves = r.get("expected_saves") or r.get("xSaves") or r.get("projected_saves")
        if x_saves is None: continue
        try:
            x_saves = float(x_saves)
        except Exception:
            continue

        # Goalie save volatility: sigma ~ 15-20% of projection (rounded)
        sigma = max(4.5, 0.18 * x_saves)

        p_30 = _p_over(x_saves, sigma, 29.5)
        p_35 = _p_over(x_saves, sigma, 34.5)
        p_40 = _p_over(x_saves, sigma, 39.5)
        p_no_30 = 1 - p_30

        edge_class = "NONE"
        best_market = None
        if 0.35 <= p_30 <= 0.50:
            edge_class = "STRONG_YES_30PLUS"
            best_market = {"market": "SAVES_30PLUS_YES",
                           "p": round(p_30, 3),
                           "fair_odds": _american(p_30)}
        elif p_no_30 >= 0.75:
            edge_class = "STRONG_NO_30PLUS"
            best_market = {"market": "SAVES_30PLUS_NO",
                           "p": round(p_no_30, 3),
                           "fair_odds": _american(p_no_30)}

        out_rows.append({
            "goalie": r.get("goalie") or r.get("name"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or r.get("game") or "",
            "expected_saves": round(x_saves, 2),
            "sigma": round(sigma, 2),
            "p_30plus": round(p_30, 3),
            "p_35plus": round(p_35, 3),
            "p_40plus": round(p_40, 3),
            "fair_yes_30": _american(p_30),
            "fair_yes_35": _american(p_35) if p_35 > 0.01 else None,
            "fair_yes_40": _american(p_40) if p_40 > 0.005 else None,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_30plus"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_goalies": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 29.5/34.5/39.5 save lines from expected_saves + "
                       "sigma 18% of projection. STRONG_YES_30PLUS p in [0.35, 0.50] "
                       "vs +180 book; STRONG_NO at p_no >= 0.75.",
        "top_15_by_p_30plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-30sv] {o['n_goalies']} goalies, {o['n_strong_edges']} strong -> {OUT}")
