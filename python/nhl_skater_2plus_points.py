"""
EdgeStat -- NHL skater 2+ points alternate market.

Distinct from `nhl_skater_points_props.py` (which targets the nearest 0.5
line — usually 0.5 or 1.5). This module specifically prices the popular
DK alternate "Player to record 2+ points (G+A)" yes/no market.

Typical book: YES +250 to +600. Elite scorers (McDavid/Draisaitl) approach
+180 to +220 on most nights. STRONG_YES requires p >= 0.30 (vs +180 book =
35.7% breakeven, gives 3-4% edge cushion).

Method:
  Primary: use expected_pts already computed by nhl_skater_points_props
           (loaded from data/nhl_skater_points_props.json -- avoids duplicate
            calc and stays consistent with the main module).
  Compute P(>= 2 points) at Poisson(expected_pts).

Output: data/nhl_skater_2plus_points.json
  Top-25 by p_2plus_points + STRONG_YES list.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_2plus_points.json")


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
    # Source: NHL points props (which already computed expected_pts)
    src = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))
    rows = src.get("rows") or src.get("top_25") or src.get("strong_edges") or []
    # Try multiple keys
    if not rows:
        for k in ("rows_top_25", "all_rows", "top_25_by_expected_pts",
                  "top_25_by_p_anytime"):
            if k in src and isinstance(src[k], list):
                rows = src[k]
                break

    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict): continue
        name = r.get("skater") or r.get("name") or r.get("player")
        team = r.get("team") or r.get("team_abbr")
        expected_pts = r.get("expected_pts") or r.get("xpts") or r.get("proj_pts") or r.get("lam")
        if expected_pts is None: continue
        try:
            expected_pts = float(expected_pts)
        except Exception:
            continue

        p_2plus = _poisson_at_least(2, expected_pts)
        p_no = 1 - p_2plus

        edge_class = "NONE"
        best_market = None
        # STRONG_YES at p in [0.30, 0.55] (vs +180 = 35.7%, +130 = 43.5%)
        if 0.30 <= p_2plus <= 0.55:
            edge_class = "STRONG_YES"
            best_market = {"market": "POINTS_2PLUS_YES",
                           "p": round(p_2plus, 3),
                           "fair_odds": _american(p_2plus)}
        # STRONG_NO at p_no in [0.85, 0.93] (vs -500 = 83.3%)
        elif 0.85 <= p_no <= 0.93:
            edge_class = "STRONG_NO"
            best_market = {"market": "POINTS_2PLUS_NO",
                           "p": round(p_no, 3),
                           "fair_odds": _american(p_no)}

        out_rows.append({
            "skater": name,
            "team": team,
            "matchup": r.get("matchup") or r.get("game") or "",
            "expected_pts": round(expected_pts, 3),
            "p_2plus_points": round(p_2plus, 3),
            "p_no_2plus": round(p_no, 3),
            "fair_yes_odds": _american(p_2plus),
            "fair_no_odds": _american(p_no),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_2plus_points"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_pts) >= 2; expected_pts inherited from "
                       "nhl_skater_points_props (consistency). STRONG_YES at "
                       "p in [0.30, 0.55] (vs +180 book breakeven 35.7%); "
                       "STRONG_NO at p_no in [0.85, 0.93] (vs -500 book).",
        "top_25_by_p_2plus": out_rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-2pt] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
