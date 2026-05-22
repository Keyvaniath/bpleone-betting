"""
EdgeStat -- MLB pitcher 9+/10+/11+ K alternate market.

Premium K alt for elite strikeout aces. Common DK pricing:
  - 9+ Ks: Skubal/Wheeler/Skenes -130 to +160 YES
  - 10+ Ks: +200 to +400
  - 11+ Ks: +500 to +1000

Method:
  Inherits expected_K from mlb_pitcher_strikeouts_props.
  Poisson(>= N) at lambda.

  STRONG_YES_9 at p in [0.35, 0.55]
  STRONG_YES_10 at p in [0.20, 0.38]
  STRONG_YES_11 at p in [0.08, 0.20]

Output: data/mlb_pitcher_9plus_K_alt.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_9plus_K_alt.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    rows_in = src.get("rows") or src.get("starters") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        lam = _safe(r.get("expected_k") or r.get("xK"))
        if lam <= 0: continue

        p_9 = _poisson_at_least(9, lam)
        p_10 = _poisson_at_least(10, lam)
        p_11 = _poisson_at_least(11, lam)
        p_12 = _poisson_at_least(12, lam)

        edges: List[Dict[str, Any]] = []
        if 0.35 <= p_9 <= 0.55:
            edges.append({"market": "K_9PLUS_YES",
                          "p": round(p_9, 3),
                          "fair_odds": _american(p_9)})
        if 0.20 <= p_10 <= 0.38:
            edges.append({"market": "K_10PLUS_YES",
                          "p": round(p_10, 3),
                          "fair_odds": _american(p_10)})
        if 0.08 <= p_11 <= 0.20:
            edges.append({"market": "K_11PLUS_YES",
                          "p": round(p_11, 3),
                          "fair_odds": _american(p_11)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "matchup": r.get("matchup"),
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "expected_K": round(lam, 2),
            "p_9plus_K": round(p_9, 3),
            "p_10plus_K": round(p_10, 3),
            "p_11plus_K": round(p_11, 3),
            "p_12plus_K": round(p_12, 3),
            "fair_yes_9plus": _american(p_9),
            "fair_yes_10plus": _american(p_10),
            "fair_yes_11plus": _american(p_11) if p_11 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
        })

    out_rows.sort(key=lambda r: -r["p_9plus_K"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(>=N) at expected_K from mlb_pitcher_strikeouts_props. "
                       "STRONG_YES_9 [0.35, 0.55], _10 [0.20, 0.38], _11 [0.08, 0.20].",
        "top_15_by_p_9plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[K-9+] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
