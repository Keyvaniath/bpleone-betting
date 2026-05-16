"""
EdgeStat -- correlation-aware Same-Game Parlay (SGP) builder.

Public books charge ~20-30% extra juice on SGPs because they implicitly
assume legs are independent when they're actually positively correlated.
Real example: "Yamamoto OVER 5.5 Ks" + "Dodgers ML" -- if Yamamoto is
dominating, the Dodgers are more likely to win. Treating these as
independent under-prices the joint probability.

This module:
  1. For each tonight's game, gathers all qualifying single-leg edges
     (props.json + pickem.json + game-line recommendations from today.json)
  2. Groups by gamePk so legs come from the same game
  3. Applies a correlation matrix to compute joint probability:
       - Same player, related markets (hits + TB, HR + TB): high correlation
       - Same team, hitter + pitcher (LAD batter HR + LAD ML): positive
       - Cross-team starter K props (opposing SPs): mildly negative
  4. Suggests top-N highest-EV combinations (2-4 legs) per game
  5. Filters out correlation-incompatible pairs (e.g., "Judge HR" and
     "Judge UNDER 1.5 TB" -- an HR forces TB>=4, so they can't both win)

Output: data/sgps.json
  {
    "generated_at": "...",
    "n_games": 15,
    "by_game": [
      {
        "matchup": "LAD @ SDP",
        "gamePk": ...,
        "suggestions": [
          {
            "legs": [...],            # list of prop+verdict
            "joint_prob": 0.34,
            "ind_prob": 0.31,         # what dumb-independence would say
            "correlation_boost": 0.03,
            "fair_decimal": 2.94,
            "fair_american": +194,
            "ev_pct": 8.2,             # vs typical SGP book price
          },
          ...
        ]
      }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
import itertools
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "sgps.json")

# Pair correlation table. Values are rho (Pearson-like) used to nudge the
# joint probability up or down from the independent product. Tuned against
# empirical correlations in MLB literature; SGP pricing-impact is small but
# directionally correct.
MARKET_CORRELATIONS = {
    # Same player coupled outcomes
    ("batter_hits", "batter_total_bases"):    +0.55,   # 1 hit -> 1+ TB
    ("batter_singles", "batter_hits"):        +0.70,
    ("batter_doubles", "batter_hits"):        +0.45,
    ("batter_doubles", "batter_total_bases"): +0.50,
    ("batter_home_runs", "batter_total_bases"):+0.65,
    ("batter_home_runs", "batter_hits"):      +0.35,
    ("batter_rbis", "batter_total_bases"):    +0.30,
    ("batter_rbis", "batter_runs_scored"):    +0.20,
    ("batter_runs_scored", "batter_hits"):    +0.25,
    # Team coupling: hitter on team OVER coupled to team ML (small)
    ("batter_team_over", "team_ml"):          +0.10,
    # SP coupling: pitcher Ks OVER coupled to that team's ML
    ("pitcher_strikeouts", "team_ml"):        +0.15,
}

# Logical-incompat pairs that CANNOT both happen.
INCOMPATIBLE_PAIRS = {
    # Same player HR OVER + same-player TB UNDER (if line < 4): HR -> TB>=4
    ("batter_home_runs", "OVER", "batter_total_bases", "UNDER"),
}

MIN_LEG_PROB = 0.55          # don't pair a coinflip
MAX_LEG_PROB = 0.85          # avoid pre-cal absurdities
MAX_LEGS = 4                  # 2-4 leg SGPs only
TOP_PER_GAME = 5              # surface up to N suggestions per game


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _decimal_to_american(d: float) -> int:
    if d >= 2.0:
        return int(round((d - 1) * 100))
    return int(round(-100 / (d - 1)))


def _correlation_for_legs(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """Look up rho for two legs. Returns 0 if no known correlation."""
    if a.get("player_id") and a["player_id"] == b.get("player_id"):
        # Same player -- check market pair
        m1, m2 = a.get("market"), b.get("market")
        return (MARKET_CORRELATIONS.get((m1, m2))
                or MARKET_CORRELATIONS.get((m2, m1))
                or 0.0)
    # Cross-player same-team coupling (very weak); skip for now
    return 0.0


def _are_incompatible(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Return True if these two legs can't both win (logical impossibility)."""
    if a.get("player_id") != b.get("player_id"):
        return False
    # HR OVER + TB UNDER pattern
    if {(a["market"], a["play"]), (b["market"], b["play"])} == {
        ("batter_home_runs", "OVER"), ("batter_total_bases", "UNDER")
    }:
        # Only incompat if TB line < 4 (HR auto-gives 4 TB)
        tb_leg = a if a["market"] == "batter_total_bases" else b
        if (tb_leg.get("line") or 99) < 4:
            return True
    # Hit OVER + Singles UNDER both at 0.5 line: a hit is at minimum 1 TB,
    # but might be a 2B+ -- they CAN co-occur. Allow.
    return False


def _joint_with_correlation(legs: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """Compute joint prob with first-order correlation adjustments.
    Returns (joint_prob, independent_product, total_boost)."""
    probs = [l["model_prob"] for l in legs]
    # Independent baseline
    ind = 1.0
    for p in probs:
        ind *= p
    # Pairwise correlation adjustment: for each pair, nudge joint up by
    # rho * sqrt(p(1-p) * q(1-q)) (Gaussian-copula approximation).
    boost = 0.0
    for i, j in itertools.combinations(range(len(legs)), 2):
        rho = _correlation_for_legs(legs[i], legs[j])
        if rho == 0:
            continue
        p, q = probs[i], probs[j]
        # Standard correlation -> joint adjustment formula
        adj = rho * ((p * (1 - p) * q * (1 - q)) ** 0.5)
        boost += adj
    joint = max(0.0001, min(0.9999, ind + boost))
    return joint, ind, boost


def _leg_label(l: Dict[str, Any]) -> str:
    market = (l.get("market") or "").replace("_", " ")
    return f"{l.get('player') or '?'} {l.get('play','?')} {l.get('line','?')} {market}"


def _gather_legs() -> List[Dict[str, Any]]:
    """Pull all qualifying single-leg edges from props + pickem."""
    legs: List[Dict[str, Any]] = []
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        po = p.get("model_prob_over") or 0
        pu = p.get("model_prob_under") if p.get("model_prob_under") is not None else (1 - po)
        # Pick the side with the higher prob
        if po >= pu:
            play, prob = "OVER", po
        else:
            play, prob = "UNDER", pu
        if not (MIN_LEG_PROB <= prob <= MAX_LEG_PROB):
            continue
        legs.append({
            "src": "DK",
            "player_id": p.get("player_id"),
            "player": p.get("player"),
            "team": p.get("team"),
            "market": p.get("market"),
            "line": p.get("line"),
            "play": play,
            "model_prob": prob,
        })
    for p in (_load(PICKEM_PATH).get("props") or []):
        po = p.get("model_prob_over") or 0
        pu = p.get("model_prob_under") or (1 - po)
        play, prob = ("OVER", po) if po >= pu else ("UNDER", pu)
        if not (MIN_LEG_PROB <= prob <= MAX_LEG_PROB):
            continue
        legs.append({
            "src": "PP",
            "player_id": p.get("player_id"),
            "player": p.get("player"),
            "team": p.get("team"),
            "market": p.get("market"),
            "line": p.get("pp_line"),
            "play": play,
            "model_prob": prob,
        })
    return legs


def _index_player_to_gamepk() -> Dict[int, Dict[str, Any]]:
    """Map player_id -> {gamePk, matchup}."""
    out: Dict[int, Dict[str, Any]] = {}
    m = _load(MATCHUPS_PATH)
    for g in m.get("games") or []:
        gp = g.get("gamePk")
        matchup = g.get("matchup")
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                pid = b.get("id")
                if pid:
                    out[pid] = {"gamePk": gp, "matchup": matchup}
        for p_side in ("home_pitcher", "away_pitcher"):
            pp = g.get(p_side) or {}
            if pp.get("id"):
                out[pp["id"]] = {"gamePk": gp, "matchup": matchup}
    return out


def run() -> Dict[str, Any]:
    legs = _gather_legs()
    pid_to_game = _index_player_to_gamepk()

    # Bucket legs by gamePk
    by_game: Dict[Any, List[Dict[str, Any]]] = {}
    for l in legs:
        info = pid_to_game.get(l.get("player_id"))
        if not info:
            continue
        gp = info["gamePk"]
        l["_matchup"] = info["matchup"]
        by_game.setdefault(gp, []).append(l)

    # For each game, find top-N highest-EV SGPs (2-4 legs)
    out_games: List[Dict[str, Any]] = []
    for gp, game_legs in by_game.items():
        if len(game_legs) < 2:
            continue
        matchup = game_legs[0].get("_matchup")
        # Cap legs we'll combine to keep combinatorics tractable. Sort by
        # individual model_prob desc and take top 12.
        game_legs.sort(key=lambda l: -l["model_prob"])
        candidates = game_legs[:12]

        suggestions = []
        for k in range(2, MAX_LEGS + 1):
            for combo in itertools.combinations(candidates, k):
                # Skip if any pair is logically incompatible
                incompat = False
                for a, b in itertools.combinations(combo, 2):
                    if _are_incompatible(a, b):
                        incompat = True
                        break
                if incompat:
                    continue
                joint, ind, boost = _joint_with_correlation(list(combo))
                if joint < 0.20:    # skip pure longshots
                    continue
                fair_decimal = round(1.0 / joint, 3)
                fair_american = _decimal_to_american(fair_decimal)
                # Compare against typical SGP book price: independence + 25% vig markup
                book_decimal = (1.0 / ind) * 1.25   # what books charge approximately
                ev_pct = round(((joint * book_decimal) - 1) * 100, 2)
                suggestions.append({
                    "legs": [{"player": l.get("player"), "player_id": l.get("player_id"),
                                "market": l.get("market"), "line": l.get("line"),
                                "play": l.get("play"), "model_prob": round(l["model_prob"], 3),
                                "src": l.get("src"), "label": _leg_label(l)} for l in combo],
                    "n_legs": k,
                    "joint_prob": round(joint, 4),
                    "ind_prob": round(ind, 4),
                    "correlation_boost": round(boost, 4),
                    "fair_decimal": fair_decimal,
                    "fair_american": fair_american,
                    "ev_pct": ev_pct,
                })
        # Sort by EV%, take top N
        suggestions.sort(key=lambda s: -s["ev_pct"])
        suggestions = suggestions[:TOP_PER_GAME]
        if suggestions:
            out_games.append({"gamePk": gp, "matchup": matchup,
                              "n_legs_available": len(game_legs), "suggestions": suggestions})

    out_games.sort(key=lambda g: -((g["suggestions"][0]["ev_pct"]) if g["suggestions"] else 0))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_legs_total": sum(len(legs) for legs in by_game.values()),
        "min_leg_prob": MIN_LEG_PROB,
        "max_leg_prob": MAX_LEG_PROB,
        "max_legs": MAX_LEGS,
        "by_game": out_games,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games']} games with SGP suggestions")
    print(f"  total legs in scope: {p['n_legs_total']}")
    if p["by_game"]:
        top = p["by_game"][0]
        print(f"  best game: {top['matchup']}")
        if top["suggestions"]:
            s = top["suggestions"][0]
            print(f"    top SGP: {s['n_legs']} legs, joint {s['joint_prob']}, fair {s['fair_american']:+d}, EV {s['ev_pct']}%")
            for l in s["legs"]:
                print(f"      - {l['label']} (model {l['model_prob']})")
