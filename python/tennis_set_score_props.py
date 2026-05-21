"""
EdgeStat -- Tennis set-score / straight-sets prop projections.

Common DK lines (best-of-3):
  - Correct set score 2-0 (A wins)
  - Correct set score 2-1 (A wins)
  - Player A straight sets yes/no (2-0)
  - Match goes to deciding set yes/no

Method:
  P(player wins set) approximated from match ELO -> per-set prob = p_match ^ (1/1.5)
  (since winning a match requires winning at least 2 of 3 sets)
  Solve: p_match = p^2 + 2*p^2*q where q=1-p
       = p^2 * (1 + 2q) = p^2 * (3 - 2p)

  Use numerical search for per-set p given p_match.
  Then:
    P(2-0) = p^2
    P(2-1) = 2 * p^2 * q
    P(straight sets A) = p^2
    P(goes to 3 sets) = 2 * p^2 * q + 2 * q^2 * p = 2*p*q*(p+q) = 2*p*q

Output: data/tennis_set_score_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_set_score_props.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _solve_set_prob(p_match: float) -> float:
    """Given P(match win), solve for P(any individual set win).
    bo3: p_match = p^2 + 2*p^2*q = p^2*(3-2p). Use binary search.
    """
    if p_match >= 0.99: return 0.95
    if p_match <= 0.01: return 0.05
    lo, hi = 0.01, 0.99
    for _ in range(50):
        mid = (lo + hi) / 2
        f = mid * mid * (3 - 2 * mid)
        if f < p_match:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    matches = state.get("rows") or []

    rows: List[Dict[str, Any]] = []

    for m in matches:
        p_match_a = m.get("p_p1_wins")
        p_match_b = m.get("p_p2_wins")
        if p_match_a is None or p_match_b is None: continue
        format_bo = m.get("format") or "bo3"
        if format_bo == "bo5":
            # bo5 set prob: p_match = p^3 * (1 + 3q + 6q^2). Skip bo5 for simplicity.
            continue

        p_set_a = _solve_set_prob(p_match_a)
        p_set_b = 1 - p_set_a

        # Probabilities of each set score
        p_20 = p_set_a ** 2
        p_21 = 2 * (p_set_a ** 2) * p_set_b
        p_02 = p_set_b ** 2
        p_12 = 2 * (p_set_b ** 2) * p_set_a
        p_straight_a = p_20
        p_straight_b = p_02
        p_three_sets = p_21 + p_12

        # STRONG flags
        edge_class = "NONE"
        best_market = None
        # Straight sets favorite: typical book -150 (60%) for 2-0 fav. STRONG when 65%+ for fav.
        if p_match_a >= 0.65 and 0.55 <= p_straight_a <= 0.72:
            edge_class = "STRONG_A_STRAIGHT_SETS"
            best_market = {"market": "STRAIGHT_SETS_PLAYER1_YES", "p": round(p_straight_a, 3),
                           "fair_odds": _american(p_straight_a)}
        elif p_match_b >= 0.65 and 0.55 <= p_straight_b <= 0.72:
            edge_class = "STRONG_B_STRAIGHT_SETS"
            best_market = {"market": "STRAIGHT_SETS_PLAYER2_YES", "p": round(p_straight_b, 3),
                           "fair_odds": _american(p_straight_b)}
        elif 0.50 <= p_match_a <= 0.55 and 0.46 <= p_three_sets <= 0.55:
            # Even matches: bet THREE SETS YES (book typically pays +120ish)
            edge_class = "STRONG_THREE_SETS"
            best_market = {"market": "GOES_TO_3_SETS_YES", "p": round(p_three_sets, 3),
                           "fair_odds": _american(p_three_sets)}

        rows.append({
            "matchup": m.get("matchup"),
            "surface": m.get("surface"),
            "p_match_a": p_match_a,
            "p_set_a": round(p_set_a, 3),
            "p_2_0": round(p_20, 3),
            "p_2_1": round(p_21, 3),
            "p_1_2": round(p_12, 3),
            "p_0_2": round(p_02, 3),
            "p_straight_a": round(p_straight_a, 3),
            "p_three_sets": round(p_three_sets, 3),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Set-prob solved from match-prob via p_match = p^2*(3-2p) (bo3). "
                       "STRONG = strong fav (65%+) likely straight sets, or even match "
                       "(~50-55%) likely to go 3 sets.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-sets] {o['n_matches']} matches, {o['n_strong_edges']} strong edges -> {OUT}")
