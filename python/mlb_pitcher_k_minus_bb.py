"""
EdgeStat -- MLB pitcher K minus BB differential O/U prop.

DK has lines like "Strikeouts minus Walks over/under N.5" — measures pitcher
efficiency. High-K low-BB aces (Skubal, Wheeler, Skenes) often have
K-BB lines at 5.5-7.5; mid-tier pitchers 3.5-4.5; control-issue or low-K
starters 1.5-2.5.

Method:
  Inherits expected_K from mlb_pitcher_strikeouts_props + expected_BB from
  mlb_pitcher_walks_props. Differential = K - BB. Sigma combined via
  sqrt(sigma_K^2 + sigma_BB^2) * 0.95 (slight negative correlation since
  efficient outings = more K and fewer BB).

  Normal CDF at typical 0.5-step lines. STRONG when 10%+ edge.

Output: data/mlb_pitcher_k_minus_bb.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_k_minus_bb.json")


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
    k_src = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    bb_src = _load(os.path.join(DATA_DIR, "mlb_pitcher_walks_props.json"))

    k_rows = k_src.get("rows") or k_src.get("starters") or []
    bb_rows = bb_src.get("rows") or bb_src.get("starters") or []

    # Index by pitcher name
    k_idx = {(r.get("pitcher") or "").lower(): r for r in k_rows if isinstance(r, dict)}
    bb_idx = {(r.get("pitcher") or "").lower(): r for r in bb_rows if isinstance(r, dict)}
    common = set(k_idx.keys()) & set(bb_idx.keys())

    out_rows: List[Dict[str, Any]] = []
    for name in common:
        kr = k_idx[name]
        br = bb_idx[name]
        x_k = _safe(kr.get("expected_k") or kr.get("xK") or kr.get("expected_strikeouts") or kr.get("projected_k"))
        x_bb = _safe(br.get("expected_bb") or br.get("expected_walks"))
        sig_k = _safe(kr.get("sigma"), 1.6)
        sig_bb = _safe(br.get("sigma"), 0.9)
        if x_k <= 0 or x_bb <= 0: continue

        diff = x_k - x_bb
        sigma_diff = math.sqrt(sig_k**2 + sig_bb**2) * 0.95

        base_line = round(diff * 2) / 2
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        for offset in (-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5):
            line = base_line + offset
            if line < 0.5: continue
            p_over = _p_over(diff, sigma_diff, line)
            p_under = 1 - p_over
            for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                if 0.62 <= p <= 0.72:
                    edge_amt = p - 0.545
                    if edge_amt > best_edge:
                        best_edge = edge_amt
                        best_market = {"market": f"K_MINUS_BB_{direction}_{line}",
                                       "line": line, "direction": direction,
                                       "p": round(p, 3),
                                       "fair_odds": _american(p)}
                        edge_class = "STRONG"

        out_rows.append({
            "matchup": kr.get("matchup"),
            "pitcher": kr.get("pitcher"),
            "team": kr.get("team"),
            "expected_K": round(x_k, 2),
            "expected_BB": round(x_bb, 2),
            "K_minus_BB": round(diff, 2),
            "sigma_diff": round(sigma_diff, 2),
            "best_market": best_market,
            "edge_class": edge_class,
        })

    out_rows.sort(key=lambda r: -r["K_minus_BB"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "K - BB differential (efficiency proxy). Sigma_diff = "
                       "sqrt(sig_K^2 + sig_BB^2) * 0.95 for slight negative correlation. "
                       "STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": out_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[k-bb] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
