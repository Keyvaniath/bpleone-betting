"""
EdgeStat -- MLB pitcher 6+ IP yes/no prop.

DK alt: 'Pitcher to pitch 6+ innings yes/no'. Different from outs_props which
is over/under N outs. 6+ IP correlates strongly with QS_YES but is its own
market.

Typical pricing:
  - Aces with healthy workload: -150 to -110 YES
  - Average starters: +110 to +150
  - Limited / coming off heavy load: +180 to +250

Method:
  Inherits expected_outs from mlb_pitcher_outs_props. 6+ IP = 18+ outs.
  Apply Normal approximation (Poisson with large lambda).

  STRONG_YES at p in [0.55, 0.72] (vs -130 book = 56.5% breakeven)
  STRONG_NO at p_no in [0.45, 0.60] vs +120 NO breakeven 45.5%

Output: data/mlb_pitcher_6plus_IP_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_6plus_IP_yn.json")


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


def _p_at_least(target: float, mean: float, sigma: float) -> float:
    """P(X >= target) via Normal approximation w/ continuity correction."""
    if sigma <= 0: return 1.0 if mean >= target else 0.0
    z = (target - 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))
    rows_in = src.get("rows") or src.get("starters") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        x_outs = _safe(r.get("expected_outs") or r.get("xOuts"))
        sigma_outs = _safe(r.get("sigma"), 3.5)
        if x_outs <= 0: continue

        # 18+ outs = 6+ IP
        p_18plus = _p_at_least(18, x_outs, sigma_outs)
        p_21plus = _p_at_least(21, x_outs, sigma_outs)  # 7+ IP
        p_no_18plus = 1 - p_18plus

        edge_class = "NONE"
        best_market = None
        if 0.55 <= p_18plus <= 0.72:
            edge_class = "STRONG_YES"
            best_market = {"market": "6PLUS_IP_YES",
                           "p": round(p_18plus, 3),
                           "fair_odds": _american(p_18plus)}
        elif 0.45 <= p_no_18plus <= 0.60:
            edge_class = "STRONG_NO"
            best_market = {"market": "6PLUS_IP_NO",
                           "p": round(p_no_18plus, 3),
                           "fair_odds": _american(p_no_18plus)}

        out_rows.append({
            "matchup": r.get("matchup"),
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "expected_outs": round(x_outs, 2),
            "expected_IP": round(x_outs / 3.0, 2),
            "sigma_outs": sigma_outs,
            "p_6plus_IP": round(p_18plus, 3),
            "p_7plus_IP": round(p_21plus, 3),
            "p_no_6plus": round(p_no_18plus, 3),
            "fair_yes": _american(p_18plus),
            "fair_no": _american(p_no_18plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_6plus_IP"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF at 17.5 outs (6 IP) from expected_outs + sigma. "
                       "STRONG_YES p in [0.55, 0.72] vs -130 book; STRONG_NO p_no "
                       "in [0.45, 0.60] vs +120 NO breakeven 45.5%.",
        "rows": out_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[6+IP] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
