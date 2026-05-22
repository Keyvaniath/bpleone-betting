"""
EdgeStat -- NHL skater 2+ goals alternate market.

DK common lines:
  - McDavid / Draisaitl / Matthews 2+ goals: +400 to +500 (16.7-20% breakeven)
  - Pastrnak / Kucherov 2+ goals: +500 to +650 (13-16.7%)
  - Most other forwards: +800 to +1500 (6-11%)

Method:
  Inherits expected_goals from nhl_anytime_goal_props (already computed with
  opp goalie factor). P(>= 2) at Poisson(lambda = expected_goals).

  Top NHL scorers have GPG ~0.55-0.70, so expected_goals after goalie adj
  is roughly 0.45-0.75. Poisson(0.60) P(>=2) = 12.2% — modest STRONG zone.

  STRONG_YES at p in [0.18, 0.30] (vs +400 book = 20% breakeven). Anyone
  >30% would be flagged as model overconfidence and excluded.

Output: data/nhl_skater_2plus_goals.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_2plus_goals.json")


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
    src = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    rows = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict): continue
        name = r.get("player") or r.get("skater")
        team = r.get("team")
        expected_goals = r.get("expected_goals")
        if expected_goals is None: continue
        try:
            expected_goals = float(expected_goals)
        except Exception:
            continue

        p_2plus = _poisson_at_least(2, expected_goals)
        # Hat trick alternate
        p_3plus = _poisson_at_least(3, expected_goals)

        p_no_2 = 1 - p_2plus

        edge_class = "NONE"
        best_market = None
        # STRONG_YES at p in [0.18, 0.30] (vs +400 book = 20%)
        if 0.18 <= p_2plus <= 0.30:
            edge_class = "STRONG_YES"
            best_market = {"market": "GOALS_2PLUS_YES",
                           "p": round(p_2plus, 3),
                           "fair_odds": _american(p_2plus)}

        out_rows.append({
            "player": name,
            "team": team,
            "matchup": r.get("matchup") or "",
            "expected_goals": round(expected_goals, 3),
            "p_2plus_goals": round(p_2plus, 3),
            "p_3plus_goals": round(p_3plus, 3),
            "p_no_2plus": round(p_no_2, 3),
            "fair_yes_2plus": _american(p_2plus),
            "fair_yes_hat_trick": _american(p_3plus) if p_3plus > 0.005 else None,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_2plus_goals"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_goals) >= 2; expected_goals inherited "
                       "from nhl_anytime_goal_props (with opp_goalie adj). "
                       "STRONG_YES at p in [0.18, 0.30] (vs +400 book = 20%). "
                       "Also exposes p_3plus_goals for hat-trick alternate.",
        "top_15_by_p_2plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-2g] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
