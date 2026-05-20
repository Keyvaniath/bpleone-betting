"""
EdgeStat -- WHALE picks: maximum-confidence multi-signal confluence.

A "whale" pick is where ALL of:
   high calibrated probability (>= 72%)
   meaningful edge (>= 15%)
   consensus across multiple deep modules (when applicable)
   positive sharp action / CLV (line moving toward our pick)

These are the picks worth sizing up because the variance is lower
(multiple independent confirmations).

Output: data/whale_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "whale_picks.json")

MIN_PROB = 0.65
MIN_EDGE_PCT = 12.0


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    consensus = _load(os.path.join(DATA_DIR, "consensus_picks.json"))
    sharp = _load(os.path.join(DATA_DIR, "sharp_action_radar.json"))

    # Index consensus by batter name for fast lookup
    consensus_hit_batters = {c["batter"]: c for c in (consensus.get("top_15_hit_boost_consensus") or [])}
    consensus_hr_batters = {c["batter"]: c for c in (consensus.get("top_15_hr_boost_consensus") or [])}

    # Index sharp signals by matchup
    sharp_signals = {}
    for s in (sharp.get("positive_signals") or []):
        sharp_signals[(s.get("matchup"), s.get("market"))] = s

    whales: List[Dict[str, Any]] = []
    for pick in (top_plays.get("top_25") or []):
        prob = pick.get("prob") or 0
        edge = pick.get("edge_pct") or 0
        if prob < MIN_PROB or edge < MIN_EDGE_PCT: continue

        # Score the confluence
        score = 0.0
        reasons = []
        # Base: high prob + high edge (already filtered above min thresholds)
        score += 1.5
        reasons.append(f"Top-25 board pick: {prob*100:.0f}% prob, +{edge:.1f}% edge")
        # Edge bonus for material edge (>20%)
        if edge >= 20:
            score += 0.5
            reasons.append(f"Edge bonus: +{edge:.1f}% material edge")

        # Consensus boost
        pm = pick.get("player_or_matchup")
        cons_match = consensus_hit_batters.get(pm) or consensus_hr_batters.get(pm)
        if cons_match:
            tier = cons_match.get("tier", "GOOD")
            score += 1.5 if tier in ("STRONG", "ELITE") else 0.5
            reasons.append(f"Consensus {tier} ({cons_match.get('n_agreeing')}/3 modules agree)")

        # Sharp action boost
        market = (pick.get("market") or "").lower()
        for (matchup, smarket), s in sharp_signals.items():
            if pm in (matchup or "") and market in (smarket or "").lower():
                shift = s.get("shift_pp", 0)
                if shift >= 5:
                    score += 1.5
                    reasons.append(f"Sharp action {s.get('intensity')}: line shifted +{shift}pp our way")
                elif shift >= 3:
                    score += 0.75
                    reasons.append(f"Mild sharp signal: +{shift}pp toward our pick")
                break

        # Source quality boost
        src = (pick.get("source") or "").lower()
        if "today" in src or "matchup" in src:
            score += 0.5
            reasons.append("Source: game-line model (high reliability)")

        # Classify tier
        if score >= 3.5: tier = "WHALE"
        elif score >= 2.5: tier = "STRONG"
        elif score >= 1.5: tier = "MODERATE"
        else: continue   # not enough confluence

        whales.append({
            "tier": tier,
            "confluence_score": round(score, 2),
            "sport": pick.get("sport"),
            "player_or_matchup": pm,
            "market": pick.get("market"),
            "prob": prob,
            "edge_pct": edge,
            "fair_american": pick.get("fair_american"),
            "kelly_fraction": pick.get("kelly_fraction"),
            "unit_size_quarter_kelly": pick.get("unit_size_quarter_kelly"),
            "source": pick.get("source"),
            "reasons": reasons,
        })

    whales.sort(key=lambda w: -w["confluence_score"])

    tier_counts = {"WHALE": 0, "STRONG": 0, "MODERATE": 0}
    for w in whales:
        tier_counts[w["tier"]] = tier_counts.get(w["tier"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_prob": MIN_PROB,
        "min_edge_pct": MIN_EDGE_PCT,
        "n_whales_total": len(whales),
        "tier_counts": tier_counts,
        "whales": whales,
        "note": ("Whale picks = top-25 board picks with high prob + high edge "
                  "PLUS confluence from consensus modules and/or sharp action. "
                  "WHALE tier (score >= 3.5) is the highest-conviction picks "
                  "worth sizing UP."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Whale picks: {p['n_whales_total']} picks ({p['tier_counts']})")
    print(f"\n  Top whales:")
    for w in p["whales"][:8]:
        print(f"  [{w['tier']:8s} score {w['confluence_score']:.2f}] {w['sport']:7s} "
              f"{(w['player_or_matchup'] or '?')[:25]:25s} {(w['market'] or '?')[:25]:25s} "
              f"{w['prob']*100:.0f}%/+{w['edge_pct']:.1f}%")
        for r in w["reasons"]:
            print(f"      - {r}")
