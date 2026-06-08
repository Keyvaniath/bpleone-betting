"""
EdgeStat -- Props-ONLY parlay builder.

Many states (and the PrizePicks / Underdog pick'em format) only allow parlays
built from PLAYER PROPS -- you can't mix a game moneyline/total with props. The
existing parlays.py mixes game lines into its legs, so this is a dedicated builder
that uses player props ONLY.

It takes the high-confidence prop pool, forms 2- and 3-leg combos (never two legs
on the same player), and prices each parlay:
  combined_decimal = product(leg decimal odds)
  joint_prob = product(leg model probs) * correlation_haircut
The haircut nudges same-game combos DOWN (legs in one game aren't independent --
two unders in the same low-scoring game move together), so we don't overstate a
parlay's true hit probability.

Output: data/props_parlay.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from itertools import combinations
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "props_parlay.json")

MAX_LEG_POOL = 12          # cap combinatorics
SAME_GAME_HAIRCUT = 0.94   # per same-game leg beyond the first (positive-correlation discount)
PROP_FAMILIES = ("pitcher", "batter", "player")


def _load(name: str) -> Any:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _dec(american) -> Optional[float]:
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    return 1 + (a / 100 if a >= 0 else 100 / abs(a))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.01 or p >= 0.99:
        return None
    return -int(round(100 / ((1 / p) - 1))) if p >= 0.5 else int(round(((1 / p) - 1) * 100))


def _build(legs: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    out = []
    for combo in combinations(legs, n):
        subjects = [c.get("subject") for c in combo]
        if len(set(subjects)) < len(subjects):     # no two legs on the same player
            continue
        games = [c.get("matchup") for c in combo if c.get("matchup")]
        n_same = len(games) - len(set(games))       # repeated-matchup leg count
        haircut = SAME_GAME_HAIRCUT ** max(0, n_same)
        decs = [_dec(c.get("fair_odds")) for c in combo]
        if any(d is None for d in decs):
            continue
        joint = 1.0
        for c in combo:
            joint *= (c.get("prob") or 0)
        joint *= haircut
        if joint <= 0:
            continue
        combined_dec = 1.0
        for d in decs:
            combined_dec *= d
        out.append({
            "n_legs": n,
            "legs": [{"sport": c.get("sport"), "subject": c.get("subject"), "market": c.get("market"),
                      "prob": c.get("prob"), "fair_odds": c.get("fair_odds"), "matchup": c.get("matchup")}
                     for c in combo],
            "joint_prob": round(joint, 3),
            "fair_american": _american(joint),
            "payout_multiple": round(combined_dec, 2),
            "same_game": n_same > 0,
            "correlation_note": ("same-game legs -- haircut applied" if n_same else "cross-game -- independent"),
        })
    return out


def run() -> Dict[str, Any]:
    # leg pool: the high-confidence board, props only
    board = _load("high_confidence_board.json").get("board") or []
    legs = [p for p in board if p.get("family") in PROP_FAMILIES and p.get("prob") and p.get("fair_odds")]
    legs = sorted(legs, key=lambda p: -(p.get("confidence") or 0))[:MAX_LEG_POOL]

    # Build each leg-count separately and keep the best of EACH, so the board
    # shows both safer 2-leggers and higher-payout 3-leggers (2-leg always wins on
    # raw joint prob, so a single ranked list would crowd out every 3-leg).
    two = sorted(_build(legs, 2), key=lambda p: (-p["joint_prob"], -p["payout_multiple"])) if len(legs) >= 2 else []
    three = sorted(_build(legs, 3), key=lambda p: (-p["joint_prob"], -p["payout_multiple"])) if len(legs) >= 3 else []
    top = two[:12] + three[:8]
    top.sort(key=lambda p: (p["n_legs"], -p["joint_prob"]))

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "format_note": "PLAYER PROPS ONLY -- no game lines mixed in (legal in prop-only states / "
                       "PrizePicks-Underdog style). Joint prob = product of leg model probs x a "
                       "same-game correlation haircut; payout_multiple is the combined decimal odds.",
        "n_legs_pool": len(legs),
        "n_parlays": len(top),
        "parlays": top,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[props-parlay] {o['n_parlays']} parlays from a {o['n_legs_pool']}-leg pool -> {OUT}")
