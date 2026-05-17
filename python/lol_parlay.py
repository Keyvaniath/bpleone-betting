"""
EdgeStat -- LoL 2-3 leg parlay builder.

Builds parlays from upcoming LoL series. Leg types:
  - ML (team to win series)
  - SWEEP (favorite to win 2-0 / 3-0 in BO3/BO5)

Joint probability assumes legs are mostly independent (different matches),
which is reasonable for LoL since each series is independent.

Output: data/lol_parlays.json
"""
from __future__ import annotations
import os, json, datetime as dt, math
from itertools import combinations
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "lol_props.json")
OUT_PATH = os.path.join(DATA_DIR, "lol_parlays.json")

MAX_LEGS = 3
MAX_PARLAYS = 12


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _decimal(american) -> float:
    if american is None or american == 0: return 1.0
    if american > 0: return 1 + (american / 100)
    return 1 + (100 / abs(american))


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    matches = [m for m in (props.get("predictions") or [])
                if not m.get("is_completed")]
    legs: List[Dict[str, Any]] = []
    for m in matches:
        for side, prob, fair, team, opp in (
            ("A", m.get("p_series_a"), m.get("fair_a_american"), m.get("team_a"), m.get("team_b")),
            ("B", m.get("p_series_b"), m.get("fair_b_american"), m.get("team_b"), m.get("team_a")),
        ):
            if prob is None or prob < 0.30: continue
            legs.append({
                "kind": "ML",
                "match_id": m.get("id"),
                "team": team, "opponent": opp,
                "prob": prob,
                "fair_american": fair,
                "label": f"{team} ML vs {opp} ({m.get('league')} BO{m.get('best_of',1)})",
            })
        # Sweep candidate for clear favorites
        if (m.get("p_sweep_a") or 0) >= 0.25:
            legs.append({
                "kind": "SWEEP",
                "match_id": m.get("id"),
                "team": m.get("team_a"), "opponent": m.get("team_b"),
                "prob": m.get("p_sweep_a"),
                "fair_american": m.get("fair_sweep_a_american"),
                "label": f"{m.get('team_a')} {(m.get('best_of',3)+1)//2}-0 sweep ({m.get('league')})",
            })

    # De-dup: only one leg per match_id (can't parlay both sides of same series)
    by_match: Dict[str, Dict[str, Any]] = {}
    for leg in legs:
        key = str(leg.get("match_id", id(leg)))
        # Keep the higher-prob leg
        if key not in by_match or by_match[key]["prob"] < leg["prob"]:
            by_match[key] = leg
    pool = list(by_match.values())

    parlays: List[Dict[str, Any]] = []
    for n in range(2, MAX_LEGS + 1):
        for combo in combinations(pool[:30], n):    # cap pool
            joint = 1.0
            decimal = 1.0
            for leg in combo:
                joint *= leg["prob"]
                decimal *= _decimal(leg["fair_american"])
            if joint < 0.01: continue
            ev_pct = round(100 * (joint * decimal - 1), 1)
            sweet = 1.0 / (1.0 + abs(joint - 0.10) * 3)
            quality = sweet * (1.0 + (n - 2) * 0.08)
            parlays.append({
                "n_legs": n,
                "joint_prob": round(joint, 4),
                "parlay_fair_decimal": round(decimal, 2),
                "parlay_fair_american": _american(joint),
                "ev_pct": ev_pct,
                "quality_score": round(quality, 4),
                "legs": [{
                    "kind": l["kind"],
                    "label": l["label"],
                    "team": l["team"],
                    "opponent": l["opponent"],
                    "prob": round(l["prob"], 4),
                    "fair_american": l["fair_american"],
                } for l in combo],
            })
    parlays.sort(key=lambda p: (-p["quality_score"], -p["ev_pct"]))
    top = parlays[:MAX_PARLAYS]
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_legs_in_pool": len(pool),
        "n_parlays_evaluated": len(parlays),
        "n_parlays": len(top),
        "parlays": top,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"LoL parlays: {p['n_parlays']} top of {p['n_parlays_evaluated']} evaluated, {p['n_legs_in_pool']} legs in pool")
    for i, par in enumerate(p["parlays"][:5], 1):
        print(f"  [{i}] {par['n_legs']}-leg @ {par['parlay_fair_american']:+d} -- joint {par['joint_prob']*100:.2f}%")
