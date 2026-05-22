"""
EdgeStat -- NHL skater 4+ hits alternate market.

Premium hits alt for grinders. Common DK pricing:
  - Heavy hitters (Tom Wilson, Tkachuks, Reaves): +110 to +180
  - Mid grinders: +220 to +320
  - Skill forwards: +500+

Method:
  Inherits expected_hits from nhl_skater_hits_blocks_props. Poisson(>=4).

  STRONG_YES_4 at p in [0.30, 0.48]
  STRONG_YES_5 at p in [0.12, 0.25]

Output: data/nhl_skater_4plus_hits.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_4plus_hits.json")


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

        p_4 = _poisson_at_least(4, x_hits)
        p_5 = _poisson_at_least(5, x_hits)
        p_6 = _poisson_at_least(6, x_hits)

        edges: List[Dict[str, Any]] = []
        if 0.30 <= p_4 <= 0.48:
            edges.append({"market": "HITS_4PLUS_YES",
                          "p": round(p_4, 3),
                          "fair_odds": _american(p_4)})
        if 0.12 <= p_5 <= 0.25:
            edges.append({"market": "HITS_5PLUS_YES",
                          "p": round(p_5, 3),
                          "fair_odds": _american(p_5)})

        edge_class = "STRONG_ALT" if edges else "NONE"

        out_rows.append({
            "skater": r.get("skater") or r.get("player") or r.get("name"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or r.get("game") or "",
            "expected_hits": round(x_hits, 2),
            "p_4plus_hits": round(p_4, 3),
            "p_5plus_hits": round(p_5, 3),
            "p_6plus_hits": round(p_6, 3),
            "fair_yes_4plus": _american(p_4),
            "fair_yes_5plus": _american(p_5) if p_5 > 0.005 else None,
            "edge_class": edge_class,
            "alt_edges": edges,
        })

    out_rows.sort(key=lambda r: -r["p_4plus_hits"])
    strong = [r for r in out_rows if r["edge_class"] == "STRONG_ALT"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(>=4) at expected_hits. STRONG_YES_4 [0.30, 0.48], "
                       "_5 [0.12, 0.25]. Also exposes 6+ alt.",
        "top_15_by_p_4plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-hits4] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
