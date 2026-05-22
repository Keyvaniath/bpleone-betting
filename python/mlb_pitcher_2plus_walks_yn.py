"""
EdgeStat -- MLB pitcher 2+ walks allowed yes/no prop.

Distinct from main walks O/U prop. This is the dedicated alt yes/no market
for "pitcher to allow 2+ walks". Popular DK alt.

Typical pricing:
  - High-BB pitchers (BB/9 >= 3.7): -120 to +110 YES
  - Avg pitchers: +130 to +180
  - Elite control SPs: +220 to +400

Method:
  Inherits expected_walks from mlb_pitcher_walks_props. P(>=2) at Poisson.

  STRONG_YES at p in [0.55, 0.72] (vs -130 book = 56.5% breakeven)
  STRONG_NO at p_no in [0.62, 0.78] (vs +150 NO breakeven 40%)

Output: data/mlb_pitcher_2plus_walks_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_2plus_walks_yn.json")


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "mlb_pitcher_walks_props.json"))
    rows_in = src.get("rows") or src.get("starters") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        expected_walks = (r.get("expected_walks") or r.get("expected_bb") or
                          r.get("projected_walks") or r.get("xBB"))
        if expected_walks is None: continue
        try:
            expected_walks = float(expected_walks)
        except Exception:
            continue

        p_1plus = _poisson_at_least(1, expected_walks)
        p_2plus = _poisson_at_least(2, expected_walks)
        p_3plus = _poisson_at_least(3, expected_walks)
        p_no_2plus = 1 - p_2plus

        edge_class = "NONE"
        best_market = None
        if 0.55 <= p_2plus <= 0.72:
            edge_class = "STRONG_YES_2PLUS"
            best_market = {"market": "WALKS_2PLUS_YES",
                           "p": round(p_2plus, 3),
                           "fair_odds": _american(p_2plus)}
        elif 0.62 <= p_no_2plus <= 0.78:
            edge_class = "STRONG_NO_2PLUS"
            best_market = {"market": "WALKS_2PLUS_NO",
                           "p": round(p_no_2plus, 3),
                           "fair_odds": _american(p_no_2plus)}

        out_rows.append({
            "matchup": r.get("matchup"),
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "expected_walks": round(expected_walks, 3),
            "p_1plus": round(p_1plus, 3),
            "p_2plus_walks": round(p_2plus, 3),
            "p_3plus": round(p_3plus, 3),
            "p_no_2plus": round(p_no_2plus, 3),
            "fair_yes_2plus": _american(p_2plus),
            "fair_no_2plus": _american(p_no_2plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_2plus_walks"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_walks) >= 2 alt market. STRONG_YES_2PLUS "
                       "p in [0.55, 0.72] vs -130 book; STRONG_NO_2PLUS p_no in "
                       "[0.62, 0.78] vs +150 NO.",
        "rows": out_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bb-2+] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
