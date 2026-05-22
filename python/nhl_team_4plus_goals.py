"""
EdgeStat -- NHL team to score 4+ goals yes/no alt market.

Common DK alt: 'Team to score 4+ goals yes/no'. Typical pricing:
  - High-scoring offense vs weak goalie: +100 to +130
  - Average matchup: +180 to +250
  - Strong defense vs weak offense: +400+

Method:
  Inherits expected_goals from nhl_team_total_edge. Poisson(>=4) at
  expected_team_goals.

  STRONG_YES at p in [0.36, 0.50] (vs +160 book = 38.5%)
  STRONG_NO at p_no in [0.62, 0.78]

Also exposes 3+/5+/6+ alts for full grid.

Output: data/nhl_team_4plus_goals.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_4plus_goals.json")


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
    src = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        lam = _safe(r.get("model_expected_goals_anchored"),
                    r.get("model_expected_goals_raw"))
        if lam <= 0: continue

        p_3plus = _poisson_at_least(3, lam)
        p_4plus = _poisson_at_least(4, lam)
        p_5plus = _poisson_at_least(5, lam)
        p_6plus = _poisson_at_least(6, lam)
        p_no_4plus = 1 - p_4plus

        edge_class = "NONE"
        best_market = None
        if 0.36 <= p_4plus <= 0.50:
            edge_class = "STRONG_YES_4PLUS"
            best_market = {"market": "TEAM_GOALS_4PLUS_YES",
                           "p": round(p_4plus, 3),
                           "fair_odds": _american(p_4plus)}
        elif 0.62 <= p_no_4plus <= 0.78:
            edge_class = "STRONG_NO_4PLUS"
            best_market = {"market": "TEAM_GOALS_4PLUS_NO",
                           "p": round(p_no_4plus, 3),
                           "fair_odds": _american(p_no_4plus)}

        out_rows.append({
            "matchup": r.get("matchup"),
            "side": r.get("side"),
            "team": r.get("team"),
            "expected_goals": round(lam, 2),
            "p_3plus": round(p_3plus, 3),
            "p_4plus": round(p_4plus, 3),
            "p_5plus": round(p_5plus, 3),
            "p_6plus": round(p_6plus, 3),
            "fair_yes_4plus": _american(p_4plus),
            "fair_no_4plus": _american(p_no_4plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_4plus"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(>= N) at expected_team_goals (from nhl_team_total_edge). "
                       "STRONG_YES_4PLUS p in [0.36, 0.50] vs +160 book; "
                       "STRONG_NO_4PLUS p_no in [0.62, 0.78]. Also exposes 3+/5+/6+ alts.",
        "rows": out_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-4goals] {o['n_team_sides']} sides, {o['n_strong_edges']} strong -> {OUT}")
