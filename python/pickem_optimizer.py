"""
EdgeStat -- PrizePicks Power-Play optimizer.

Given today's modeled PrizePicks props, builds optimal 2-/3-/4-/5-/6-leg
Power Plays maximizing expected EV. PrizePicks pays:
  2-leg power: 3x   (breakeven 33.3%)
  3-leg power: 5x   (breakeven 20.0%)
  4-leg power: 10x  (breakeven 10.0%)
  5-leg power: 20x  (breakeven 5.0%)
  6-leg power: 25x  (breakeven 4.0%)

A leg combination's EV = (product of leg probs) * payout - 1.

We rank combinations by EV but require:
  - Each leg's individual model prob >= 0.60 (passes leg-level breakeven)
  - No two legs from the same player (PP disallows)
  - Independence assumption (no SGP correlation -- they're DFS picks)

Writes data/pickem_optimizer.json.
"""
from __future__ import annotations

import os
import json
import itertools
import datetime as dt
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "pickem_optimizer.json")

PAYOUTS = {2: 3.0, 3: 5.0, 4: 10.0, 5: 20.0, 6: 25.0}
MIN_LEG_PROB = 0.60
MAX_LEG_PROB = 0.85    # Cap individual leg probs -- nothing in sports is "100%"
MAX_PER_SIZE = 5   # how many top combos per leg-count


def _load_pickem() -> List[Dict[str, Any]]:
    path = os.path.join(DATA_DIR, "pickem.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f).get("props", [])
    except Exception:
        return []


def _best_side_prob(r: Dict[str, Any]) -> Tuple[str, float]:
    """Return (side, prob) for the side the model favors."""
    p_over = r.get("model_prob_over") or 0.5
    p_under = r.get("model_prob_under") or 0.5
    if p_over >= p_under:
        return ("OVER", p_over)
    return ("UNDER", p_under)


def build_optimal_powerplays() -> Dict[str, Any]:
    props = _load_pickem()
    # Build candidate leg list: best side of each prop that clears MIN_LEG_PROB
    legs = []
    seen_players = set()
    for r in props:
        side, prob = _best_side_prob(r)
        if prob < MIN_LEG_PROB:
            continue
        # Limit to top 1 prop per player to avoid duplicates
        pid = r.get("player_id") or r.get("player")
        key = (pid, r.get("market"))
        if key in seen_players:
            continue
        seen_players.add(key)
        # Cap raw prob to avoid unrealistic "100%" combos from thin-sample players.
        capped_prob = min(prob, MAX_LEG_PROB)
        legs.append({
            "player": r.get("player"),
            "player_id": pid,
            "market": r.get("market"),
            "stat_type": r.get("stat_type"),
            "side": side,
            "line": r.get("pp_line"),
            "prob": round(capped_prob, 4),
            "prob_raw": round(prob, 4),
        })
    # Sort by prob descending so combinations explore highest-conviction first
    legs.sort(key=lambda l: -l["prob"])
    # Cap legs to top 30 to keep combinations manageable
    legs = legs[:30]

    output: Dict[str, List[Dict[str, Any]]] = {}
    for size, payout in PAYOUTS.items():
        if len(legs) < size:
            continue
        combos = []
        # For efficiency only consider combos from top 12-15 legs
        consider = legs[:min(15, len(legs))]
        for combo in itertools.combinations(consider, size):
            # No duplicate players in same parlay
            pids = {l["player_id"] for l in combo}
            if len(pids) != size:
                continue
            prob = 1.0
            for l in combo:
                prob *= l["prob"]
            ev = prob * payout - 1
            combos.append({
                "size": size,
                "payout": payout,
                "combined_prob": round(prob, 4),
                "ev": round(ev, 4),
                "ev_pct": round(ev * 100, 2),
                "legs": list(combo),
            })
        combos.sort(key=lambda c: -c["ev"])
        # Keep top N per size
        output[f"{size}_leg"] = combos[:MAX_PER_SIZE]

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_leg_prob": MIN_LEG_PROB,
        "total_candidate_legs": len(legs),
        "by_size": output,
    }


def write_optimizer(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote pickem_optimizer -> {path}")
    print(f"  Candidate legs (model_prob >= {MIN_LEG_PROB}): {payload.get('total_candidate_legs', 0)}")
    for size_key, combos in (payload.get("by_size") or {}).items():
        if not combos:
            continue
        size = combos[0]["size"]
        top = combos[0]
        print(f"  {size}-leg top EV: +{top['ev_pct']}% (prob {top['combined_prob']:.3f}, payout {top['payout']}x)")
        for l in top["legs"]:
            print(f"    {l['side']} {l['line']} {l['stat_type']} -- {l['player']} (model {l['prob']:.2%})")


if __name__ == "__main__":
    write_optimizer(build_optimal_powerplays())
