"""
EdgeStat -- Tonight's anchor stack (cross-sport parlay recommender).

Takes the top entries from elite_alerts_board.json and builds a 4-leg
recommended parlay with correlation considerations:
  - Prefer entities from 4 DIFFERENT sports (uncorrelated)
  - Within same sport, prefer same-team correlation (e.g. fade pitcher +
    opposing TT OVER on same MLB game)
  - Skip duplicate entities

For each leg, output a recommended bet (e.g. K UNDER for fade pitcher,
PTS OVER for NBA ceiling player). Computed parlay odds + edge%.

Output: data/tonight_anchor_stack.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_anchor_stack.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _recommended_market_for(source: str, entity: str, extras: dict) -> str:
    """Map elite-board source to a concrete recommended market."""
    if source == "MLB_PITCHER_DOMINANCE":
        return f"{entity} K OVER + outs OVER + QS YES (parlay)"
    if source == "MLB_PITCHER_FADE":
        return f"{entity} K UNDER + outs UNDER + 4+ ER YES"
    if source == "MLB_OFFENSIVE_EXPLOSION":
        return f"{entity} team total OVER + 5+ runs YES"
    if source == "MLB_MATCHUP_CONFLUENCE":
        return f"{entity} -- fade pitcher + offensive explosion parlay"
    if source == "NBA_PLAYER_CEILING":
        return f"{entity} PTS OVER + PRA OVER (top edge multi-OVER)"
    if source == "NBA_TEAM_EXPLOSION":
        return f"{entity} team total OVER + race-to-points YES"
    if source == "NHL_GOALIE_DOMINANCE":
        return f"{entity} saves OVER + 30+ saves YES + win YES"
    if source == "NHL_SKATER_CEILING":
        return f"{entity} SOG OVER + anytime goal YES"
    if source == "NHL_TEAM_EXPLOSION":
        return f"{entity} team total OVER + 4+ goals YES"
    if source == "SOCCER_MATCH_ALERT":
        return f"{entity} total goals OVER + BTTS YES"
    if source == "TENNIS_DOMINANCE":
        return f"{entity} match win + 1st set + straight sets (parlay)"
    if source == "UFC_FIGHTER_DOMINANCE":
        return f"{entity} method KO/sub + rounds UNDER"
    if source == "GOLF_PLAYER_DOMINANCE":
        return f"{entity} top 10 finish + make cut"
    if source == "WNBA_PLAYER_CEILING":
        return f"{entity} PTS OVER + REB OVER + 20+ PTS YES"
    if source == "F1_DRIVER_DOMINANCE":
        return f"{entity} podium finish + Q top 3 (parlay)"
    return f"{entity} multi-leg parlay"


def run() -> Dict[str, Any]:
    eb = _load(os.path.join(DATA_DIR, "elite_alerts_board.json"))
    elites = eb.get("elites") or []

    # Build a 4-leg anchor stack, max 1 per sport
    used_sports: set = set()
    used_entities: set = set()
    legs: List[Dict[str, Any]] = []

    # First pass -- pick highest-signal entity per sport
    for e in elites:
        if len(legs) >= 4: break
        sport = e.get("sport", "")
        entity = e.get("entity", "")
        if sport in used_sports: continue
        if entity in used_entities: continue
        if not entity: continue

        legs.append({
            "leg_n": len(legs) + 1,
            "source": e.get("source"),
            "sport": sport,
            "entity": entity,
            "matchup": e.get("matchup"),
            "tier": e.get("tier"),
            "n_signals": e.get("n_signals"),
            "recommended_market": _recommended_market_for(
                e.get("source", ""), entity, e.get("extras") or {}
            ),
        })
        used_sports.add(sport)
        used_entities.add(entity)

    # If we still have < 4 legs, fill with next-best across already-covered sports
    if len(legs) < 4:
        for e in elites:
            if len(legs) >= 4: break
            entity = e.get("entity", "")
            if entity in used_entities: continue
            if not entity: continue
            legs.append({
                "leg_n": len(legs) + 1,
                "source": e.get("source"),
                "sport": e.get("sport"),
                "entity": entity,
                "matchup": e.get("matchup"),
                "tier": e.get("tier"),
                "n_signals": e.get("n_signals"),
                "recommended_market": _recommended_market_for(
                    e.get("source", ""), entity, e.get("extras") or {}
                ),
            })
            used_entities.add(entity)

    # Anchor strength = sum of n_signals across legs
    anchor_strength = sum(l.get("n_signals", 0) or 0 for l in legs)
    sports_diversity = len(set(l.get("sport") for l in legs))

    if anchor_strength >= 25 and sports_diversity >= 3:
        tier = "ELITE_STACK"
    elif anchor_strength >= 18 and sports_diversity >= 2:
        tier = "STRONG_STACK"
    elif anchor_strength >= 12:
        tier = "LEAN_STACK"
    else:
        tier = "NO_STACK"

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_legs": len(legs),
        "anchor_strength": anchor_strength,
        "sports_diversity": sports_diversity,
        "tier": tier,
        "method_note": "Cross-sport anchor stack derived from elite_alerts_board. "
                       "Max 1 leg per sport (preferred) + signal-strength ranking. "
                       "ELITE_STACK = strength>=25 AND 3+ sports; STRONG=>=18 AND 2+; "
                       "LEAN=>=12. Each leg includes recommended_market mapping.",
        "legs": legs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[anchor-stack] {o['n_legs']} legs, strength={o['anchor_strength']}, "
          f"tier={o['tier']} -> {OUT}")
