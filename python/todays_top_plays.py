"""
EdgeStat -- TODAY'S TOP PLAYS unified board.

Brandon's curated list of ONLY the picks worth betting today:
  - Probability >= 70% (no coin-flip noise)
  - Across all sports / sources
  - Ranked by Kelly-adjusted unit size, NOT just probability
  - Top 25 only

Pulls from slate_player_pot.json + slate_team_pot.json (already aggregated).
Computes Kelly-fraction unit size assuming a typical -110 line:

  kelly_f = (b*p - q) / b  where p = model_prob, q = 1-p, b = decimal_odds-1
  For -110 fair price: b = 0.909

Result: ranked by (prob - 0.524) * unit_weight   -- effectively edge.

Output: data/todays_top_plays.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "todays_top_plays.json")

MIN_PROB = 0.70   # Tighter than slate aggregator (60%) -- Brandon's real bet board


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _kelly_fraction(p, decimal_odds):
    """Standard Kelly: f = (b*p - q) / b where b = decimal_odds - 1"""
    if not decimal_odds or decimal_odds <= 1: return 0
    b = decimal_odds - 1
    q = 1 - p
    f = (b * p - q) / b
    return max(0, min(0.25, f))    # cap at 25% (fractional Kelly)


def _edge_pct(p, decimal_odds):
    """Edge = (p * decimal_odds) - 1 (Kelly EV at $1 bet)."""
    if not decimal_odds or decimal_odds <= 1: return 0
    return p * decimal_odds - 1


def run() -> Dict[str, Any]:
    player_pot = _load(os.path.join(DATA_DIR, "slate_player_pot.json"))
    team_pot = _load(os.path.join(DATA_DIR, "slate_team_pot.json"))

    candidates = []
    for src, doc in (("player", player_pot), ("team", team_pot)):
        items = doc.get("all_picks") or doc.get("top_50") or doc.get("top_30") or []
        for x in items:
            prob = x.get("prob")
            if not prob or prob < MIN_PROB: continue
            # Assume -110 line if no fair_american provided
            fair = x.get("fair_american") or -110
            dec_odds = _american_to_decimal(fair) or 1.91
            edge = _edge_pct(prob, dec_odds)
            kelly = _kelly_fraction(prob, dec_odds)
            if edge <= 0: continue   # only +EV plays
            candidates.append({
                "src": src,
                "sport": x.get("sport"),
                "player_or_matchup": x.get("player") or x.get("matchup"),
                "team": x.get("team"),
                "market": x.get("market"),
                "prob": prob,
                "fair_american": fair,
                "decimal_odds": round(dec_odds, 3),
                "edge_pct": round(edge * 100, 1),
                "kelly_fraction": round(kelly, 4),
                "unit_size_quarter_kelly": round(kelly * 0.25, 3),   # conservative
                "source": x.get("source"),
            })

    # Rank by edge_pct desc (real value, not just probability)
    candidates.sort(key=lambda c: -c["edge_pct"])

    # By sport summary
    by_sport: Dict[str, int] = {}
    for c in candidates:
        by_sport[c["sport"]] = by_sport.get(c["sport"], 0) + 1

    # Top 25
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_prob": MIN_PROB,
        "n_total_plays": len(candidates),
        "by_sport": by_sport,
        "top_25": candidates[:25],
        "top_5_by_kelly": sorted(candidates, key=lambda c: -c["kelly_fraction"])[:5],
        "all_plays": candidates[:100],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Today's top plays: {p['n_total_plays']} +EV picks at >={p['min_prob']:.0%} prob")
    print(f"  By sport: {p['by_sport']}")
    print(f"\nTop 15 by edge_pct:")
    for c in p["top_25"][:15]:
        print(f"  [{c['sport']:7s}] {(c['player_or_matchup'] or '?')[:30]:30s} "
              f"{(c['market'] or '?')[:30]:30s} p={c['prob']*100:.0f}% edge={c['edge_pct']:+.1f}% "
              f"kelly={c['kelly_fraction']*100:.1f}% qK_unit={c['unit_size_quarter_kelly']:.2f}u")
    print(f"\nTop 5 by Kelly fraction (size up):")
    for c in p["top_5_by_kelly"]:
        print(f"  {c['player_or_matchup']:30s} {c['market']:30s} "
              f"kelly={c['kelly_fraction']*100:.1f}%  qK_unit={c['unit_size_quarter_kelly']:.2f}u")
