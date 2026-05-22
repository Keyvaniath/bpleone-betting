"""
EdgeStat -- Soccer player 2+ goals (brace) alt market.

Companion to soccer_goalscorer_props. The 2+ goals 'brace' market is high-
value:
  - Elite strikers (Haaland, Mbappe): +280 to +450
  - Top-line forwards: +500 to +800
  - Most players: +1000+

Method:
  Inherits expected_goals (per player) from soccer_goalscorer_props.
  Poisson(>= 2) at lambda.

  STRONG_YES at p in [0.18, 0.32] (vs +400 book = 20% breakeven)

Output: data/soccer_goalscorer_2plus.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_goalscorer_2plus.json")


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
    src = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))
    rows_in = src.get("rows") or []

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        # Expected goals for player (lambda)
        lam = r.get("expected_goals") or r.get("lambda") or r.get("xG")
        if lam is None: continue
        try:
            lam = float(lam)
        except Exception:
            continue

        p_2plus = _poisson_at_least(2, lam)
        p_3plus = _poisson_at_least(3, lam)  # hat-trick

        edge_class = "NONE"
        best_market = None
        if 0.18 <= p_2plus <= 0.32:
            edge_class = "STRONG_YES_2PLUS"
            best_market = {"market": "GOALS_2PLUS_YES",
                           "p": round(p_2plus, 3),
                           "fair_odds": _american(p_2plus)}

        out_rows.append({
            "player": r.get("player") or r.get("name"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or "",
            "expected_goals": round(lam, 3),
            "p_2plus_goals": round(p_2plus, 3),
            "p_3plus_goals": round(p_3plus, 3),
            "fair_yes_2plus": _american(p_2plus),
            "fair_yes_hat_trick": _american(p_3plus) if p_3plus > 0.005 else None,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_2plus_goals"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(>= 2) at expected_goals from soccer_goalscorer_props. "
                       "STRONG_YES_2PLUS p in [0.18, 0.32] vs +400 book. Also exposes "
                       "hat-trick (3+) probability.",
        "top_15_by_p_2plus": out_rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soc-2gls] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
