"""
EdgeStat -- MLB pitcher to pitch INTO 6th inning yes/no prop.

Different from '6+ IP yes/no'. 'Pitches INTO 6th' = records at least 1 out
in the 6th inning, i.e., expected_outs >= 16 (vs 18 for 6+ IP).

Less strict threshold means slightly different breakeven; common book:
  - Aces: -180 YES
  - Avg starters: +130 YES
  - Limited / RED workload: +220+

Method:
  P(expected_outs >= 16) via Normal CDF on outs distribution.

  STRONG_YES at p in [0.60, 0.75]
  STRONG_NO at p_no in [0.45, 0.60]

Output: data/mlb_pitcher_pitches_into_6th.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_pitches_into_6th.json")


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

        # 16+ outs = pitches into 6th
        p_16plus = _p_at_least(16, x_outs, sigma_outs)
        p_no = 1 - p_16plus

        edge_class = "NONE"
        best_market = None
        if 0.60 <= p_16plus <= 0.75:
            edge_class = "STRONG_YES"
            best_market = {"market": "PITCHES_INTO_6TH_YES",
                           "p": round(p_16plus, 3),
                           "fair_odds": _american(p_16plus)}
        elif 0.45 <= p_no <= 0.60:
            edge_class = "STRONG_NO"
            best_market = {"market": "PITCHES_INTO_6TH_NO",
                           "p": round(p_no, 3),
                           "fair_odds": _american(p_no)}

        out_rows.append({
            "matchup": r.get("matchup"),
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "expected_outs": round(x_outs, 2),
            "sigma_outs": sigma_outs,
            "p_pitches_into_6th": round(p_16plus, 3),
            "p_no_pitches_into_6th": round(p_no, 3),
            "fair_yes": _american(p_16plus),
            "fair_no": _american(p_no),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_pitches_into_6th"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "P(pitches into 6th) = P(outs >= 16) via Normal CDF from "
                       "expected_outs + sigma. Different threshold than 6+ IP (which "
                       "requires 18+ outs). STRONG_YES p in [0.60, 0.75] vs -150 book.",
        "rows": out_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[6th-inn] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
