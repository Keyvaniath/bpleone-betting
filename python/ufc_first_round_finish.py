"""
EdgeStat -- UFC fight first round finish yes/no prop.

Popular DK alt: 'Fight ends in 1st round yes/no'. Common pricing:
  - Heavy striker matchups: +280 to +400 YES
  - Avg matchup: +500 to +700
  - Submission specialists: +400 to +550

Method:
  Pull total finish probability + num_rounds from ufc_method_of_victory.
  P(finish in R1) = 1 - (1 - p_finish_per_round)^1 = p_finish_per_round
  where p_finish_per_round = 1 - (p_distance ** (1/num_rounds))

  STRONG_YES at p in [0.18, 0.32] (vs +300 book = 25% breakeven)

Output: data/ufc_first_round_finish.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_first_round_finish.json")


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
    src = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    fights = src.get("rows") or src.get("fights") or []

    rows: List[Dict[str, Any]] = []
    for f in fights:
        if not isinstance(f, dict): continue
        p_finish_total = _safe(f.get("p_finish") or f.get("p_total_finish"), 0.55)
        num_rounds = int(_safe(f.get("rounds") or f.get("num_rounds"), 3))
        p_distance = 1 - p_finish_total

        if p_distance <= 0:
            p_finish_per_round = 0.99
        else:
            p_finish_per_round = 1 - (p_distance ** (1.0 / num_rounds))

        # P(finish in R1) = probability that fight ends in 1st round
        p_r1_finish = p_finish_per_round
        p_no_r1 = 1 - p_r1_finish

        edge_class = "NONE"
        best_market = None
        if 0.18 <= p_r1_finish <= 0.32:
            edge_class = "STRONG_YES"
            best_market = {"market": "FIGHT_R1_FINISH_YES",
                           "p": round(p_r1_finish, 3),
                           "fair_odds": _american(p_r1_finish)}

        rows.append({
            "fight": f.get("fight") or f.get("matchup"),
            "fighter_a": f.get("fighter_a") or f.get("p1"),
            "fighter_b": f.get("fighter_b") or f.get("p2"),
            "num_rounds": num_rounds,
            "p_finish_total": round(p_finish_total, 3),
            "p_finish_per_round": round(p_finish_per_round, 3),
            "p_r1_finish": round(p_r1_finish, 3),
            "p_no_r1_finish": round(p_no_r1, 3),
            "fair_yes_r1": _american(p_r1_finish),
            "fair_no_r1": _american(p_no_r1),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_r1_finish"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fights": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(R1 finish) = p_finish_per_round, derived from fight's total "
                       "finish prob and num_rounds. STRONG_YES p in [0.18, 0.32] vs "
                       "+300 book breakeven 25%.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-r1] {o['n_fights']} fights, {o['n_strong_edges']} strong -> {OUT}")
