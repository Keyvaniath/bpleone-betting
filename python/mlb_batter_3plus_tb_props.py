"""
EdgeStat -- MLB batter 3+ total bases yes/no alternate.

Distinct from mlb_total_bases_props.json (which provides P(TB>=1/2/3) inline)
in that this dedicated module surfaces 3+ TB as a YES/NO market with
edge classification + book-comparison fair odds.

Common DK pricing:
  - Elite power bat (Judge / Soto / Ohtani): +200 to +300 (~26% breakeven)
  - Mid power bats: +400 to +550 (15-20% breakeven)
  - Contact-only bats: +900+ (<10% breakeven)

Method:
  Pulls from mlb_total_bases_props.json (which already exposes P(TB >= 3) on
  every row). This module is the dedicated YES/NO classification layer with
  threshold tuning for the 3+ alt-market.

  STRONG_YES at p_tb3 in [0.22, 0.40] (vs +300 book = 25% breakeven)
  STRONG_NO at p_no_tb3 in [0.86, 0.95] (vs -700 book = 87.5%)

Output: data/mlb_batter_3plus_tb_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_3plus_tb_props.json")


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


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json"))
    rows_in = src.get("rows") or src.get("top_25_by_xTB") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        # mlb_total_bases_props uses key names "p_3_plus" and "expected_tb"
        p_tb3 = _safe(r.get("p_3_plus") or r.get("p_tb_3_plus")
                      or r.get("p_tb3plus") or r.get("p_3plus_tb"))
        # Fallback: compute from expected_tb via Poisson if needed
        if p_tb3 <= 0:
            xtb = _safe(r.get("expected_tb") or r.get("xTB"))
            if xtb > 0:
                import math
                cumulative = 0.0
                for i in range(3):
                    cumulative += (xtb ** i) * math.exp(-xtb) / math.factorial(i)
                p_tb3 = max(0.0, min(1.0, 1.0 - cumulative))

        p_no = 1 - p_tb3

        edge_class = "NONE"
        best_market = None
        if 0.22 <= p_tb3 <= 0.40:
            edge_class = "STRONG_YES"
            best_market = {"market": "TB_3PLUS_YES", "p": round(p_tb3, 3),
                           "fair_odds": _american(p_tb3)}
        elif 0.86 <= p_no <= 0.95:
            edge_class = "STRONG_NO"
            best_market = {"market": "TB_3PLUS_NO", "p": round(p_no, 3),
                           "fair_odds": _american(p_no)}

        out_rows.append({
            "matchup": r.get("matchup"),
            "batter": r.get("batter") or r.get("name"),
            "team": r.get("team"),
            "order": r.get("order"),
            "expected_TB": r.get("expected_tb") or r.get("xTB"),
            "p_tb_3plus": round(p_tb3, 3),
            "p_no_tb_3plus": round(p_no, 3),
            "fair_yes_odds": _american(p_tb3),
            "fair_no_odds": _american(p_no),
            "edge_class": edge_class,
            "best_market": best_market,
            "tb_source": r.get("tb_source") or "fallback",
        })

    out_rows.sort(key=lambda r: -r["p_tb_3plus"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Inherits expected_TB from mlb_total_bases_props (uses real "
                       "per-PA TB rates from LvR splits + park). Poisson(>=3). "
                       "STRONG_YES p in [0.22, 0.40] vs +300 book; "
                       "STRONG_NO p_no in [0.86, 0.95] vs -700 book.",
        "top_25_by_p_tb3": out_rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tb3+] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
