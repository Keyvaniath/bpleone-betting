"""
EdgeStat -- NHL skater 3+ hits alternate market.

Different from main hits+blocks combined prop. This is the 3+ hits alt for
heavy hitters / grinders. Common DK pricing:
  - Tom Wilson, Brady Tkachuk, Matthew Tkachuk: -110 to +130
  - Mid-tier grinders: +180 to +280
  - Skill forwards: +400+

Method:
  Inherits expected_hits from nhl_skater_hits_blocks_props (or computes from
  per-game hits average if not available). Poisson(>=3) at expected hits.

  STRONG_YES at p in [0.40, 0.58] (vs +100 book = 50% breakeven)

Output: data/nhl_skater_3plus_hits.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_3plus_hits.json")


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
    src = _load(os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json"))
    rows_in = src.get("rows") or src.get("skaters") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        x_hits = (r.get("expected_hits") or r.get("xHits") or
                  r.get("projected_hits") or r.get("hits_per_game"))
        if x_hits is None: continue
        try:
            x_hits = float(x_hits)
        except Exception:
            continue

        p_2plus = _poisson_at_least(2, x_hits)
        p_3plus = _poisson_at_least(3, x_hits)
        p_4plus = _poisson_at_least(4, x_hits)
        p_no_3plus = 1 - p_3plus

        edge_class = "NONE"
        best_market = None
        if 0.40 <= p_3plus <= 0.58:
            edge_class = "STRONG_YES_3PLUS"
            best_market = {"market": "HITS_3PLUS_YES",
                           "p": round(p_3plus, 3),
                           "fair_odds": _american(p_3plus)}

        out_rows.append({
            "skater": r.get("skater") or r.get("player") or r.get("name"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or r.get("game") or "",
            "expected_hits": round(x_hits, 2),
            "p_2plus_hits": round(p_2plus, 3),
            "p_3plus_hits": round(p_3plus, 3),
            "p_4plus_hits": round(p_4plus, 3),
            "p_no_3plus": round(p_no_3plus, 3),
            "fair_yes_3plus": _american(p_3plus),
            "fair_no_3plus": _american(p_no_3plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_3plus_hits"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_hits) >= 3 from nhl_skater_hits_blocks_props. "
                       "STRONG_YES_3PLUS p in [0.40, 0.58] vs +100 book breakeven 50%. "
                       "Also exposes 2+ and 4+ alts.",
        "top_15_by_p_3plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-hits3] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
