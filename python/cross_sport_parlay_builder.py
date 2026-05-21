"""
EdgeStat -- cross-sport PARLAY builder.

Combines top locks from todays_top_plays.json into 2-leg and 3-leg
parlays. Two legs across different sports/games are essentially
independent -- joint probability = product of individual probabilities.

Within the same game (e.g. both legs on MLB HOU @ MIN), the legs are
correlated -- we conservatively apply a 0.10 correlation penalty.

For each candidate parlay:
  joint_prob   = p1 * p2 * (1 - corr_penalty if same_game else 1)
  fair_decimal = decimal_odds_1 * decimal_odds_2
  joint_fair_american = decimal_to_american(fair_decimal)
  edge_pct = joint_prob * fair_decimal - 1

We surface parlays where:
  joint_prob >= 35% (otherwise variance too high)
  edge_pct >= 5% (otherwise not worth the parlay tax)
  No more than 1 leg per same player (avoid degenerate correlation)

Output: data/cross_sport_parlays.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from itertools import combinations
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_parlays.json")

MIN_JOINT_PROB_2 = 0.35
MIN_JOINT_PROB_3 = 0.20
MIN_EDGE_PCT = 5.0
SAME_GAME_CORR_PENALTY = 0.10  # legacy default — only used as last-resort fallback
MAX_PARLAYS_PER_SIZE = 25

# 2026-05-21: Market-type correlation matrix.
# Returns joint-prob multiplier for a pair of legs IN THE SAME GAME.
# > 1.0 = legs help each other (negative real-world correlation -> higher joint prob)
# < 1.0 = legs penalize each other (positive correlation -> lower joint prob)
# = 1.0 = independent
def _direction(market: str) -> str:
    """Return 'over', 'under', 'yes', 'no', or '' from market string."""
    if not market: return ""
    m = market.upper()
    if "_OVER_" in m or m.endswith("_OVER") or "OVER_" in m: return "over"
    if "_UNDER_" in m or m.endswith("_UNDER") or "UNDER_" in m: return "under"
    if "_YES" in m: return "yes"
    if "_NO" in m: return "no"
    return ""


def _correlation_factor(legA, legB) -> float:
    """Compute joint-prob multiplier for two same-game legs."""
    famA = (legA.get("market_family") or "").lower()
    famB = (legB.get("market_family") or "").lower()
    dirA = _direction(legA.get("market") or "")
    dirB = _direction(legB.get("market") or "")
    teamA = (legA.get("team") or "").upper()
    teamB = (legB.get("team") or "").upper()
    same_team = teamA and teamB and teamA == teamB

    # Pitcher dominance + opp-team UNDER are negatively correlated in reality
    # (a dominant K performance suppresses opp runs). Boost joint prob.
    pitch_dom = any(k in famA for k in ("pitcher_k", "pitcher_outs", "pitcher_quality_start", "pitcher_er")) \
                or any(k in famB for k in ("pitcher_k", "pitcher_outs", "pitcher_quality_start", "pitcher_er"))
    team_total = "team_total" in famA or "team_total" in famB or "first5" in famA or "first5" in famB

    if pitch_dom and team_total:
        # Pitcher OVER + opp team UNDER: same-direction event, correlated
        # (already same-direction = factor 1.05 boost)
        if (dirA == "over" and dirB == "under") or (dirA == "under" and dirB == "over"):
            return 1.05

    # Two over/two under on different players on SAME team
    if same_team and dirA == dirB and dirA in ("over", "under", "yes"):
        # Both bullish on same team -> positive correlation -> penalty
        return 0.90

    # Two NOs on same team = same direction = correlated
    if same_team and dirA == "no" and dirB == "no":
        return 0.92

    # Two same-player same-direction legs would have been filtered upstream
    # by _player_key dedup, so we don't handle that here.

    # Two anytime-goal/first-goalscorer in same game = positive corr
    if "anytime_goal" in famA + famB or "fgs" in famA + famB:
        if "anytime_goal" in famA and "anytime_goal" in famB:
            return 0.94  # both depend on scoring environment
        if ("fgs" in famA and "anytime_goal" in famB) or ("anytime_goal" in famA and "fgs" in famB):
            return 0.96

    # Two PRA-family props on same team = positive corr
    pra_keys = ("pra", "double_double", "triple_double", "points", "rebounds", "assists")
    if same_team and any(k in famA for k in pra_keys) and any(k in famB for k in pra_keys):
        return 0.92

    # Default same-game penalty
    return 1.0 - SAME_GAME_CORR_PENALTY  # 0.90


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _decimal_to_american(decimal):
    if decimal is None or decimal <= 1.0: return None
    if decimal >= 2.0:
        return int(round((decimal - 1) * 100))
    return -int(round(100 / (decimal - 1)))


def _game_key(leg):
    """Return a key that identifies the leg's GAME (so same-game legs match).
    For team markets: matchup string. For player props: typically still
    matchup-level since player belongs to a game."""
    return (leg.get("sport"), leg.get("player_or_matchup", "").split(" vs ")[0].split(" @ ")[0])


def _player_key(leg):
    return (leg.get("sport"), leg.get("player_or_matchup"))


def _build_parlay(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute joint probability + fair parlay odds for a tuple of legs."""
    if not legs: return None
    probs = []
    decimal_odds = []
    for L in legs:
        p = L.get("prob")
        f = L.get("fair_american")
        d = _american_to_decimal(f)
        if not p or not d: return None
        probs.append(p)
        decimal_odds.append(d)

    # 2026-05-21: apply pairwise market-aware correlation factor.
    # For each pair of same-game legs, look up the correlation multiplier
    # and apply it. Different-game pairs are independent (factor 1.0).
    game_keys = [_game_key(L) for L in legs]
    corr_factor = 1.0
    correlation_notes = []
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            if game_keys[i] == game_keys[j]:
                f = _correlation_factor(legs[i], legs[j])
                corr_factor *= f
                if abs(f - 1.0) > 0.001:
                    correlation_notes.append({
                        "legA_market": legs[i].get("market"),
                        "legB_market": legs[j].get("market"),
                        "factor": round(f, 3),
                    })
    same_game = corr_factor != 1.0

    joint_prob = corr_factor
    for p in probs:
        joint_prob *= p

    fair_decimal = 1.0
    for d in decimal_odds:
        fair_decimal *= d

    edge = joint_prob * fair_decimal - 1
    return {
        "n_legs": len(legs),
        "legs": [{
            "sport": L.get("sport"),
            "player_or_matchup": L.get("player_or_matchup"),
            "market": L.get("market"),
            "prob": L.get("prob"),
            "fair_american": L.get("fair_american"),
        } for L in legs],
        "joint_prob": round(joint_prob, 4),
        "fair_parlay_decimal": round(fair_decimal, 3),
        "fair_parlay_american": _decimal_to_american(fair_decimal),
        "edge_pct": round(edge * 100, 1),
        "same_game_penalty_applied": same_game,
        "correlation_factor": round(corr_factor, 3),
        "correlation_notes": correlation_notes,
        "implied_payout_per_dollar": round(fair_decimal - 1, 2),
    }


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    # Use top_25 (already deduped + diversified)
    legs = top_plays.get("top_25") or []
    if not legs:
        out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "note": "No top plays available to build parlays from",
                "n_2_leg": 0, "n_3_leg": 0,
                "parlays_2_leg": [], "parlays_3_leg": []}
        with open(OUT, "w") as f: json.dump(out, f, indent=2)
        return out

    # Only consider legs with explicit fair_american -- needed for parlay pricing
    legs_with_odds = [L for L in legs if isinstance(L.get("fair_american"), (int, float))]

    # 2-leg parlays
    parlays_2: List[Dict[str, Any]] = []
    for L1, L2 in combinations(legs_with_odds, 2):
        # Skip if same player (degenerate correlation)
        if _player_key(L1) == _player_key(L2): continue
        p = _build_parlay([L1, L2])
        if not p: continue
        if p["joint_prob"] >= MIN_JOINT_PROB_2 and p["edge_pct"] >= MIN_EDGE_PCT:
            parlays_2.append(p)
    parlays_2.sort(key=lambda x: -x["edge_pct"])

    # 3-leg parlays (more restrictive — too many combos otherwise)
    parlays_3: List[Dict[str, Any]] = []
    # Cap at top 12 individual legs for combinatorial sanity (12 choose 3 = 220)
    legs_for_3 = legs_with_odds[:12]
    for trio in combinations(legs_for_3, 3):
        # Skip if any pair has same player
        player_keys = [_player_key(L) for L in trio]
        if len(set(player_keys)) < len(player_keys): continue
        p = _build_parlay(list(trio))
        if not p: continue
        if p["joint_prob"] >= MIN_JOINT_PROB_3 and p["edge_pct"] >= MIN_EDGE_PCT:
            parlays_3.append(p)
    parlays_3.sort(key=lambda x: -x["edge_pct"])

    # Best balanced suggestions: highest edge + reasonable variance (joint_prob 40-65%)
    balanced_2 = [p for p in parlays_2 if 0.40 <= p["joint_prob"] <= 0.65]
    balanced_2.sort(key=lambda x: -x["edge_pct"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_input_legs": len(legs_with_odds),
        "n_2_leg": len(parlays_2),
        "n_3_leg": len(parlays_3),
        "min_joint_prob_2_leg": MIN_JOINT_PROB_2,
        "min_joint_prob_3_leg": MIN_JOINT_PROB_3,
        "min_edge_pct": MIN_EDGE_PCT,
        "same_game_correlation_penalty": SAME_GAME_CORR_PENALTY,
        "top_2_leg_parlays": parlays_2[:MAX_PARLAYS_PER_SIZE],
        "top_3_leg_parlays": parlays_3[:MAX_PARLAYS_PER_SIZE],
        "balanced_2_leg_picks": balanced_2[:10],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Cross-sport parlay builder: {p.get('n_input_legs',0)} input legs")
    print(f"  2-leg parlays meeting criteria: {p['n_2_leg']}")
    print(f"  3-leg parlays meeting criteria: {p['n_3_leg']}")
    print(f"\n  Top 5 2-leg parlays (by edge):")
    for x in p["top_2_leg_parlays"][:5]:
        labels = " + ".join([f"{L['sport']} {L['player_or_matchup'][:15]} {L['market'][:18]}" for L in x['legs']])
        print(f"    {labels}")
        print(f"      joint={x['joint_prob']*100:.0f}% fair={x['fair_parlay_american']} edge={x['edge_pct']:+.1f}%")
    print(f"\n  Top 3 3-leg parlays:")
    for x in p["top_3_leg_parlays"][:3]:
        labels = " + ".join([f"{L['sport']} {L['player_or_matchup'][:12]}" for L in x['legs']])
        print(f"    {labels}")
        print(f"      joint={x['joint_prob']*100:.0f}% fair={x['fair_parlay_american']} edge={x['edge_pct']:+.1f}%")
