"""
EdgeStat -- NHL skater 4+ shots on goal alternate (premium tier).

The 4+ SOG market is a high-volume DK alt for top shot-volume skaters:
  - Elite shooters (Matthews, Pastrnak): +100 to +130
  - Top-line wingers: +200 to +300
  - Mid-tier forwards: +400 to +600

Method:
  Inherits expected_sog from nhl_skater_sog_props. P(>=4) at Poisson(lambda).

  STRONG_YES at p in [0.32, 0.50] (vs +160 book = 38.5% breakeven)
  Note: this market RARELY has STRONG_NO since 4+ SOG is unlikely by default.

Output: data/nhl_skater_4plus_sog.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_4plus_sog.json")


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


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        xsog = r.get("expected_sog") or r.get("xSOG") or r.get("projected_sog")
        if xsog is None: continue
        try:
            xsog = float(xsog)
        except Exception:
            continue

        p_4plus = _poisson_at_least(4, xsog)
        p_5plus = _poisson_at_least(5, xsog)  # Premium alt

        edge_class = "NONE"
        best_market = None
        if 0.32 <= p_4plus <= 0.50:
            edge_class = "STRONG_YES_4PLUS"
            best_market = {"market": "SOG_4PLUS_YES",
                           "p": round(p_4plus, 3),
                           "fair_odds": _american(p_4plus)}

        out_rows.append({
            "skater": r.get("skater") or r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or "",
            "expected_sog": round(xsog, 2),
            "p_4plus_sog": round(p_4plus, 3),
            "p_5plus_sog": round(p_5plus, 3),
            "fair_yes_4plus": _american(p_4plus),
            "fair_yes_5plus": _american(p_5plus) if p_5plus > 0.01 else None,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_4plus_sog"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_sog) >= 4 alt market. Inherits from sog_props. "
                       "STRONG_YES p in [0.32, 0.50] vs +160 book. Also exposes 5+ alt.",
        "top_15_by_p_4plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-sog4+] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
