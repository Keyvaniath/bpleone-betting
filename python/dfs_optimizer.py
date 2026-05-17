"""
EdgeStat -- DFS-style lineup optimizer for PrizePicks Power Plays.

PrizePicks uses fixed payouts based on # of legs and how many hit:
  2-leg Power: 3x both correct
  3-leg Power: 6x all 3, 1x if 2/3
  4-leg Power: 10x all 4, 0.4x if 3/4
  5-leg Power: 20x all 5, 1.5x if 4/5
  6-leg Power: 35x all 6, 0.4x if 5/6, 2x if 4/6

For each combo size, picks the top legs from across all player props
that maximize expected value at the fixed-payout structure.

Legs sourced from:
  - lol_player_props.json
  - cs_player_props.json
  - kbo_player_props.json

Output: data/dfs_optimizer.json
"""
from __future__ import annotations
import os, json, math, datetime as dt
from itertools import combinations
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "dfs_optimizer.json")

# PrizePicks Power Play payouts (perfect / partial)
PAYOUTS = {
    2: [3.0, 0],
    3: [6.0, 0, 0],
    4: [10.0, 0, 0, 0],
    5: [20.0, 0, 0, 0, 0],
    6: [35.0, 0, 0, 0, 0, 0],
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _ev_perfect(legs: List[Dict[str, Any]], payout: float) -> float:
    """EV of perfect lineup (all hit) = product of probabilities x payout - 1."""
    joint = 1.0
    for l in legs:
        joint *= l["prob"]
    return round(joint * payout - 1, 4)


PROB_MIN = 0.58
PROB_MAX = 0.78    # Cap at 78% -- anything higher is "lock" territory books won't offer

# Only elite / tier-1 league players for DFS (avoid tier-3 LoL leagues where models are noisy)
TIER1_LOL_LEAGUES = {"LCK", "LPL", "LEC", "LCS", "MSI", "Worlds", "First Stand"}


def _collect_player_legs() -> List[Dict[str, Any]]:
    """Pull strong player props (prob 58-78%) as DFS candidate legs."""
    legs: List[Dict[str, Any]] = []

    # LoL kill props -- tier-1 leagues only, prob in [0.58, 0.78]
    lol = _load(os.path.join(DATA_DIR, "lol_player_props.json"))
    for p in (lol.get("projections") or []):
        if p.get("league") not in TIER1_LOL_LEAGUES: continue
        for kp in (p.get("kill_props") or []):
            if PROB_MIN <= kp.get("p_over", 0) <= PROB_MAX:
                legs.append({
                    "sport": "LOL",
                    "player": p.get("summoner_name"),
                    "team": p.get("team_code"),
                    "market": f"kills_o_{kp.get('line')}",
                    "label": f"{p.get('summoner_name')} OVER {kp.get('line')} Kills",
                    "prob": kp["p_over"],
                })
            elif PROB_MIN <= kp.get("p_under", 0) <= PROB_MAX:
                legs.append({
                    "sport": "LOL",
                    "player": p.get("summoner_name"),
                    "team": p.get("team_code"),
                    "market": f"kills_u_{kp.get('line')}",
                    "label": f"{p.get('summoner_name')} UNDER {kp.get('line')} Kills",
                    "prob": kp["p_under"],
                })

    # CS kill props (top players only, tight band)
    cs = _load(os.path.join(DATA_DIR, "cs_player_props.json"))
    for p in (cs.get("players") or []):
        if p.get("rating", 0) < 1.08: continue
        for kp in (p.get("props_bo3", {}).get("kills") or []):
            if PROB_MIN <= kp.get("p_over", 0) <= PROB_MAX:
                legs.append({
                    "sport": "CS",
                    "player": p.get("name"),
                    "team": p.get("team"),
                    "market": f"cs_kills_o_{kp.get('line')}",
                    "label": f"{p.get('name')} OVER {kp.get('line')} Kills (BO3)",
                    "prob": kp["p_over"],
                })

    # KBO props (tight band)
    kbo = _load(os.path.join(DATA_DIR, "kbo_player_props.json"))
    for p in (kbo.get("players") or []):
        if p.get("kind") == "batter":
            for market in ("two_plus_hits", "one_plus_rbi", "one_plus_tb"):
                pr = p.get("props", {}).get(market) or {}
                if PROB_MIN <= pr.get("p", 0) <= PROB_MAX:
                    legs.append({
                        "sport": "KBO",
                        "player": p["name"],
                        "team": p["team"],
                        "market": f"kbo_{market}",
                        "label": f"{p['name']} {market.replace('_', ' ')} ({p['team']})",
                        "prob": pr["p"],
                    })

    # De-dup by player (keep highest-prob leg per player)
    by_player: Dict[str, Dict[str, Any]] = {}
    for l in legs:
        key = f"{l['sport']}|{l['player']}"
        if key not in by_player or by_player[key]["prob"] < l["prob"]:
            by_player[key] = l
    return list(by_player.values())


def run() -> Dict[str, Any]:
    legs = _collect_player_legs()
    # Sort by prob desc, cap at 20 for combinatorial sanity
    legs.sort(key=lambda l: -l["prob"])
    pool = legs[:20]
    if len(pool) < 2:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": f"not enough qualifying legs (have {len(pool)})",
            "n_pool": len(pool),
            "lineups": {},
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # For each combo size, find best EV lineup
    lineups: Dict[str, List[Dict[str, Any]]] = {}
    for size in (2, 3, 4, 5, 6):
        payout = PAYOUTS[size][0]
        candidates = []
        # Only consider top 10 legs to keep combo count manageable
        sub_pool = pool[:min(12, len(pool))]
        if len(sub_pool) < size: continue
        for combo in combinations(sub_pool, size):
            joint = 1.0
            for l in combo:
                joint *= l["prob"]
            ev = round(joint * payout - 1, 4)
            candidates.append({
                "ev": ev,
                "joint_prob": round(joint, 4),
                "payout_mult": payout,
                "legs": [{
                    "sport": l["sport"],
                    "player": l["player"],
                    "team": l["team"],
                    "label": l["label"],
                    "prob": round(l["prob"], 4),
                } for l in combo],
            })
        candidates.sort(key=lambda c: -c["ev"])
        lineups[f"{size}_leg"] = candidates[:5]    # top 5 per size

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_pool": len(pool),
        "pool": pool,
        "lineups": lineups,
        "payouts": PAYOUTS,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"DFS optimizer: {p['n_pool']} legs in pool")
    for size in (2, 3, 4, 5, 6):
        key = f"{size}_leg"
        ls = p.get("lineups", {}).get(key) or []
        if not ls: continue
        top = ls[0]
        print(f"  {size}-leg best: joint {top['joint_prob']*100:.1f}%, payout {top['payout_mult']}x, EV {top['ev']*100:+.1f}%")
        for l in top["legs"]:
            print(f"    - [{l['sport']:4}] {l['label']} (p={l['prob']*100:.1f}%)")
