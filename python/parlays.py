"""
EdgeStat -- parlay engine.

Builds 2-leg and 3-leg parlay suggestions from the highest-edge game-line +
player-prop plays. Cross-game parlays use independent multiplication of
probabilities; same-game parlays apply a correlation haircut (using the
existing Gaussian-copula machinery in correlations.py when available).

Filters:
  - Each leg must be a "PLAY" (not SKIP) with positive single-leg edge
  - Total parlay payout must beat the implied break-even by >= MIN_PARLAY_EDGE
  - Skip same-game-parlays where correlation pushes EV below break-even

Writes data/parlays.json sorted by EV. Front-end (parlays.html) reads it.
"""
from __future__ import annotations

import os
import json
import math
import itertools
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "parlays.json")

MIN_LEG_EDGE_PCT = 3.0        # each leg needs at least +3% solo edge
MAX_LEG_EDGE_PCT = 25.0       # legs with edges over this are likely phantom (pre-calibration model noise); skip them
MIN_PARLAY_EDGE_PCT = 8.0     # total parlay needs >= +8% EV to surface
MAX_PARLAY_EDGE_PCT = 50.0    # parlays above this are showing pre-calibration noise; suppress
MAX_PARLAYS = 30              # cap output rows
MAX_LEGS = 3                  # 2- and 3-leg only for v1


def american_to_dec(price: int) -> float:
    """American price -> decimal payout multiplier (includes stake)."""
    if price >= 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / -price


def dec_to_american(dec: float) -> int:
    """Decimal multiplier -> American price."""
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100 / (dec - 1.0)))


def implied_prob(price: int) -> float:
    if price >= 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


# -------------------- Load candidate legs --------------------

def _load_props_legs() -> List[Dict[str, Any]]:
    """Read props.json and return per-leg dicts for the side the model likes."""
    path = os.path.join(DATA_DIR, "props.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            payload = json.load(f)
    except Exception:
        return []
    legs = []
    for r in payload.get("top_edges", []):
        play = r.get("play")
        if play not in ("OVER", "UNDER"):
            continue
        leg_edge = r.get("best_edge_pct") or 0
        if leg_edge < MIN_LEG_EDGE_PCT or leg_edge > MAX_LEG_EDGE_PCT:
            continue
        if r.get("low_confidence"):
            continue
        price = r.get(f"dk_{play.lower()}")
        if price is None:
            continue
        prob = r.get("model_prob_over") if play == "OVER" else 1.0 - (r.get("model_prob_over") or 0.0)
        legs.append({
            "type": "prop",
            "label": f"{r['player']} {play} {r['line']} {r['market']}",
            "matchup": r.get("matchup"),
            "market": r.get("market"),
            "side": play,
            "line": r.get("line"),
            "price": int(price),
            "model_prob": float(prob),
            "edge_pct": r.get("best_edge_pct"),
            "game_id": r.get("matchup"),  # used for SGP detection
        })
    return legs


def _load_game_legs() -> List[Dict[str, Any]]:
    """Read today.json and return per-leg dicts for highest-edge game-line plays."""
    path = os.path.join(DATA_DIR, "today.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            payload = json.load(f)
    except Exception:
        return []
    legs = []
    for g in payload.get("games", []):
        recs = g.get("recommendations", []) or []
        for r in recs:
            leg_edge = r.get("edge_pct") or 0
            if leg_edge < MIN_LEG_EDGE_PCT or leg_edge > MAX_LEG_EDGE_PCT:
                continue
            legs.append({
                "type": "game",
                "label": f"{g['matchup']} {r.get('label')}",
                "matchup": g.get("matchup"),
                "market": r.get("label"),
                "side": None,
                "line": None,
                "price": int(r.get("market_price", -110)),
                "model_prob": float(r.get("model_prob", 0)),
                "edge_pct": r.get("edge_pct"),
                "game_id": g.get("matchup"),
            })
    return legs


# -------------------- Parlay math --------------------

def parlay_payout(prices: List[int]) -> float:
    """Decimal payout of an N-leg parlay (multiplicative)."""
    p = 1.0
    for x in prices:
        p *= american_to_dec(x)
    return p


def parlay_prob(legs: List[Dict[str, Any]], corr_haircut: float = 0.0) -> float:
    """Product of leg probabilities. Subtract a fixed haircut for SGP correlation."""
    p = 1.0
    for leg in legs:
        p *= leg["model_prob"]
    return max(0.0, p - corr_haircut)


def parlay_edge_pct(legs: List[Dict[str, Any]], corr_haircut: float = 0.0) -> float:
    payout = parlay_payout([l["price"] for l in legs])
    prob = parlay_prob(legs, corr_haircut)
    return round((prob * payout - 1.0) * 100.0, 2)


def is_sgp(legs: List[Dict[str, Any]]) -> bool:
    """All legs from the same game?"""
    game_ids = {l.get("game_id") for l in legs if l.get("game_id")}
    return len(game_ids) == 1


def sgp_correlation_haircut(legs: List[Dict[str, Any]]) -> float:
    """Rough correlation haircut for same-game-parlays.

    Heuristic: each additional same-game leg drops effective independence by
    a fixed amount. A proper correlation model lives in correlations.py
    (Gaussian copula on labeled correlation matrix) -- this is a stand-in
    until we wire it in.
    """
    if len(legs) < 2:
        return 0.0
    # 5% absolute haircut per additional leg in same game.
    return 0.05 * (len(legs) - 1)


# -------------------- Main builder --------------------

def build_parlays() -> Dict[str, Any]:
    props_legs = _load_props_legs()
    game_legs = _load_game_legs()
    all_legs = props_legs + game_legs
    if len(all_legs) < 2:
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "fewer than 2 qualifying legs", "parlays": []}

    candidates: List[Dict[str, Any]] = []
    # 2-leg parlays
    for combo in itertools.combinations(all_legs, 2):
        haircut = sgp_correlation_haircut(list(combo)) if is_sgp(list(combo)) else 0.0
        edge = parlay_edge_pct(list(combo), haircut)
        if edge < MIN_PARLAY_EDGE_PCT or edge > MAX_PARLAY_EDGE_PCT:
            continue
        candidates.append({
            "n_legs": 2,
            "legs": [{"label": l["label"], "price": l["price"],
                      "model_prob": round(l["model_prob"], 4),
                      "matchup": l.get("matchup"), "market": l.get("market"),
                      "type": l["type"]} for l in combo],
            "parlay_price": dec_to_american(parlay_payout([l["price"] for l in combo])),
            "parlay_prob": round(parlay_prob(list(combo), haircut), 4),
            "edge_pct": edge,
            "sgp": is_sgp(list(combo)),
            "correlation_haircut": haircut,
        })

    # 3-leg parlays. Bounded so we don't explode combinatorially.
    if len(all_legs) <= 14:  # C(14,3) = 364, manageable
        for combo in itertools.combinations(all_legs, 3):
            haircut = sgp_correlation_haircut(list(combo)) if is_sgp(list(combo)) else 0.0
            edge = parlay_edge_pct(list(combo), haircut)
            if edge < MIN_PARLAY_EDGE_PCT or edge > MAX_PARLAY_EDGE_PCT:
                continue
            candidates.append({
                "n_legs": 3,
                "legs": [{"label": l["label"], "price": l["price"],
                          "model_prob": round(l["model_prob"], 4),
                          "matchup": l.get("matchup"), "market": l.get("market"),
                          "type": l["type"]} for l in combo],
                "parlay_price": dec_to_american(parlay_payout([l["price"] for l in combo])),
                "parlay_prob": round(parlay_prob(list(combo), haircut), 4),
                "edge_pct": edge,
                "sgp": is_sgp(list(combo)),
                "correlation_haircut": haircut,
            })

    candidates.sort(key=lambda x: x["edge_pct"], reverse=True)
    candidates = candidates[:MAX_PARLAYS]

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_leg_edge_pct": MIN_LEG_EDGE_PCT,
        "min_parlay_edge_pct": MIN_PARLAY_EDGE_PCT,
        "legs_evaluated": len(all_legs),
        "parlays": candidates,
    }


def write_parlays(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote parlays -> {path}")
    print(f"  Legs evaluated: {payload.get('legs_evaluated', 0)}")
    print(f"  Qualifying parlays: {len(payload.get('parlays', []))}")
    for c in payload.get("parlays", [])[:5]:
        legs = ' | '.join(l['label'] for l in c['legs'])
        print(f"    {c['n_legs']}-leg {'(SGP)' if c['sgp'] else '   '} @ "
              f"{c['parlay_price']:>+5} | prob {c['parlay_prob']:.3f} | edge +{c['edge_pct']}%")
        print(f"      legs: {legs}")


if __name__ == "__main__":
    payload = build_parlays()
    write_parlays(payload)
