"""
EdgeStat -- UFC fight rounds total over/under prop.

DK market: "Total rounds in fight over/under X.5" — common for 3-round fights
at 2.5 line (i.e. does fight reach the 3rd round?). For 5-round mains at 3.5
or 4.5.

Typical pricing:
  - 3rd round 2.5 line: -110 / -110 (close to coinflip)
  - 5-round main 3.5 line: -150 to +130 depending on fighter styles

Method:
  Inherits from ufc_method_of_victory output (which has finish probabilities
  per fighter). P(reaches round N) = P(no_finish_in_round_1..N-1).

  Per-round finish rate estimated from fighter career finish rate:
    base_finish_per_round = combined_finish_rate / num_rounds

  STRONG_OVER when 5%+ edge vs typical -120 book (54.5% breakeven)
  STRONG_UNDER similarly

Output: data/ufc_rounds_over_under_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_rounds_over_under_props.json")


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
    """Build per-fight rounds over/under from method_of_victory data."""
    src = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    fights = src.get("rows") or src.get("fights") or []

    rows: List[Dict[str, Any]] = []
    for f in fights:
        if not isinstance(f, dict): continue
        # Total fight finish probability (sum of KO + Sub for both fighters)
        p_finish_total = _safe(f.get("p_finish") or f.get("p_total_finish"), 0.55)
        p_distance = 1 - p_finish_total
        num_rounds = int(_safe(f.get("rounds") or f.get("num_rounds"), 3))

        # Per-round finish rate (assuming uniform distribution within distance shortfall)
        # If P(distance) = 0.45, P(finish per round) = 1 - (0.45 ** (1/3)) ~ 0.234
        if p_distance > 0:
            p_finish_per_round = 1 - (p_distance ** (1.0 / num_rounds))
        else:
            p_finish_per_round = 0.99

        # P(reach round R) = (1 - p_finish_per_round)^(R-1)
        # For round 2 (i.e. enters R2): (1 - p_finish_per_round)^1
        # For round 3: (1 - p)^2
        # P(fight goes >= X.5 rounds) = P(R(X+1) happens) * 0.5 + P(R(X+1) finishes >= halfway)
        # Simplified: P(reach end of round X) = (1 - p)^X for X complete rounds finishing

        p_reach_r2 = (1 - p_finish_per_round) ** 1
        p_reach_r3 = (1 - p_finish_per_round) ** 2
        p_reach_r4 = (1 - p_finish_per_round) ** 3
        p_reach_r5 = (1 - p_finish_per_round) ** 4

        # Over 1.5 rounds = enters R2 = p_reach_r2
        # Over 2.5 rounds = enters R3 = p_reach_r3
        # etc.
        edges: List[Dict[str, Any]] = []
        # Test 1.5, 2.5, 3.5, 4.5 lines
        for line, p_over in (
            ("1.5", p_reach_r2), ("2.5", p_reach_r3),
            ("3.5", p_reach_r4), ("4.5", p_reach_r5)
        ):
            if float(line) >= num_rounds: continue  # skip impossible
            p_under = 1 - p_over
            for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                if 0.58 <= p <= 0.72:
                    edges.append({
                        "market": f"ROUNDS_{direction}_{line}",
                        "line": float(line),
                        "direction": direction,
                        "p": round(p, 3),
                        "fair_odds": _american(p),
                    })

        # Best edge per fight
        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG" if best_edge else "NONE"

        rows.append({
            "fight": f.get("fight") or f.get("matchup"),
            "fighter_a": f.get("fighter_a") or f.get("p1"),
            "fighter_b": f.get("fighter_b") or f.get("p2"),
            "num_rounds": num_rounds,
            "p_finish_total": round(p_finish_total, 3),
            "p_distance": round(p_distance, 3),
            "p_finish_per_round": round(p_finish_per_round, 3),
            "p_reach_r2": round(p_reach_r2, 3),
            "p_reach_r3": round(p_reach_r3, 3),
            "p_reach_r4": round(p_reach_r4, 3),
            "p_reach_r5": round(p_reach_r5, 3),
            "best_edge": best_edge,
            "edge_class": edge_class,
            "all_edges": edges,
        })

    rows.sort(key=lambda r: -(r.get("best_edge") or {}).get("p", 0))
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fights": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(reach round R) = (1 - p_finish_per_round)^(R-1) where "
                       "p_finish_per_round = 1 - (p_distance ** (1/num_rounds)). "
                       "STRONG when 5%+ edge vs -120 book (p in [0.58, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-rounds] {o['n_fights']} fights, {o['n_strong_edges']} strong -> {OUT}")
