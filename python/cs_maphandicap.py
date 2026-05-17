"""
EdgeStat -- CS map handicap props (BO3 -1.5 / +1.5, BO5 -2.5 / +2.5).

For each upcoming CS match, computes:
  - P(team wins 2-0 in BO3) = p_map^2
  - P(team wins 2-1 in BO3) = 2*p_map^2*(1-p_map)
  - P(team wins 3-0 in BO5) = p_map^3
  - Map total over/under projections (P(total maps > 2.5))

Output: data/cs_maphandicap.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "cs_props.json")
OUT_PATH = os.path.join(DATA_DIR, "cs_maphandicap.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    matches = [m for m in (props.get("predictions") or []) if not m.get("is_completed")]
    out: List[Dict[str, Any]] = []
    for m in matches:
        p = m.get("p_map_a") or 0.5
        best_of = m.get("best_of") or 3
        target = (best_of + 1) // 2
        # Sweep prob = p^target
        sweep_a = p ** target
        sweep_b = (1 - p) ** target
        # Goes-the-distance prob = decisive game 3 (BO3) or game 5 (BO5)
        # = P(series ends in exactly best_of maps)
        # For BO3 = 2 * p * (1-p)  (one win each in games 1-2, then game 3)
        if best_of == 3:
            distance = 2 * p * (1 - p)    # P(2-1 series in either direction)
            # Map total OVER 2.5 = same as distance
            p_over_2_5 = distance
        elif best_of == 5:
            # P(series ends in 5 = 6 * p^2 * (1-p)^2 ... binomial complement)
            # P(over 4.5 maps) = P(reaches game 5)
            # Both teams need 2 wins in first 4
            p_over_4_5 = 6 * (p ** 2) * ((1 - p) ** 2)
            distance = p_over_4_5
            p_over_2_5 = 1 - sweep_a - sweep_b    # any time series > target maps
        else:
            distance = 0
            p_over_2_5 = 0

        out.append({
            "team_a": m["team_a"],
            "team_b": m["team_b"],
            "best_of": best_of,
            "p_map_a": p,
            "elo_a": m.get("elo_a"),
            "elo_b": m.get("elo_b"),
            "p_sweep_a": round(sweep_a, 4),
            "p_sweep_b": round(sweep_b, 4),
            "p_goes_distance": round(distance, 4),
            "fair_sweep_a_american": _american(sweep_a),
            "fair_sweep_b_american": _american(sweep_b),
            "fair_distance_american": _american(distance),
            "p_total_over_2_5": round(p_over_2_5, 4) if best_of >= 3 else None,
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_matches": len(out),
        "matches": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"CS map handicap: {p['n_matches']} matches")
    for m in p["matches"][:5]:
        print(f"  {m['team_a']:18} vs {m['team_b']:18} BO{m['best_of']}  "
              f"sweep_a {m['p_sweep_a']*100:.1f}%  distance {m['p_goes_distance']*100:.1f}%")
