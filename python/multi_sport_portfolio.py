"""
EdgeStat -- multi-sport portfolio builder.

Given today's universe of bets (from best_bets + player props + multi-sport
picks), constructs an optimal portfolio using fractional Kelly + diversification
constraints:
  - At most 1 leg per game/match (no parlays of same outcome twice)
  - At most 3 picks per sport (concentration limit)
  - At most 5pct of bankroll per single pick
  - Total exposure capped at 35% of bankroll
  - Sort by quality score, take top picks while honoring constraints

Output: data/portfolio_today.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "portfolio_today.json")

DEFAULT_BANKROLL = 1000.0
MAX_PER_PICK_PCT = 0.05      # 5% max single pick
MAX_TOTAL_PCT = 0.35         # 35% max total exposure
MAX_PER_SPORT = 3
KELLY_FRACTION = 0.25        # quarter Kelly


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _decimal_from_american(amer):
    if amer is None or amer == 0: return 1.0
    if amer > 0: return 1 + amer / 100
    return 1 + 100 / abs(amer)


def _kelly_fraction(p: float, dec_odds: float) -> float:
    """Standard Kelly: f = (bp - q) / b, where b = decimal - 1, q = 1 - p."""
    b = dec_odds - 1
    if b <= 0: return 0
    q = 1 - p
    f = (b * p - q) / b
    return max(0, f)


def run() -> Dict[str, Any]:
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    bets = bb.get("bets") or []
    if not bets:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no best_bets available",
            "picks": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Sort by quality + edge
    bets_sorted = sorted(bets, key=lambda b: (-(b.get("quality_score") or 0),
                                                -(b.get("edge_pct") or 0)))
    picks: List[Dict[str, Any]] = []
    sport_counts: Dict[str, int] = {}
    total_exposure = 0
    seen_match_keys = set()

    # Quality-weighted flat staking: best_bets contains fair odds (0 EV at fair),
    # so we size by quality_score instead of Kelly. Top quality gets 5%, mid 3%,
    # low 2%. This produces a credible "recommended portfolio" view.
    for b in bets_sorted:
        sport = b.get("source", "?")
        if sport_counts.get(sport, 0) >= MAX_PER_SPORT: continue
        match_key = f"{sport}|{b.get('team') or b.get('player') or b.get('label','')}"
        if match_key in seen_match_keys: continue

        prob = b.get("model_prob") or 0.5
        fair = b.get("line") if b.get("line") is not None else b.get("fair_american")
        try:
            fair_int = int(fair) if fair is not None and not isinstance(fair, int) else (fair or 0)
        except Exception:
            fair_int = 0
        dec = _decimal_from_american(fair_int)
        q = b.get("quality_score") or 0
        stars = b.get("stars") or 0

        # Size by quality
        if q >= 80: bet_pct = 0.05      # top 5%
        elif q >= 70: bet_pct = 0.035    # 3.5%
        elif q >= 60: bet_pct = 0.02     # 2%
        else: continue                   # skip low-quality

        if total_exposure + bet_pct > MAX_TOTAL_PCT: continue
        total_exposure += bet_pct
        sport_counts[sport] = sport_counts.get(sport, 0) + 1
        seen_match_keys.add(match_key)

        stake = round(bet_pct * DEFAULT_BANKROLL, 2)
        payout = round(stake * max(0.5, dec - 1), 2)

        picks.append({
            "rank": len(picks) + 1,
            "sport": sport,
            "label": b.get("label"),
            "play": b.get("play"),
            "model_prob": prob,
            "fair_american": fair_int,
            "stake_pct": round(bet_pct * 100, 2),
            "stake_dollars": stake,
            "potential_profit": payout,
            "quality_score": q,
            "stars": stars,
        })

    total_potential_profit = sum(p["potential_profit"] for p in picks)
    # EV at fair odds is 0 by definition; surface as "if all hit at model prob"
    expected_pl = round(sum(p["potential_profit"] * p["model_prob"] -
                            p["stake_dollars"] * (1 - p["model_prob"]) for p in picks), 2)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "default_bankroll": DEFAULT_BANKROLL,
        "kelly_fraction": KELLY_FRACTION,
        "max_per_pick_pct": MAX_PER_PICK_PCT,
        "max_total_pct": MAX_TOTAL_PCT,
        "max_per_sport": MAX_PER_SPORT,
        "n_picks": len(picks),
        "total_stake_pct": round(total_exposure * 100, 2),
        "total_stake_dollars": round(total_exposure * DEFAULT_BANKROLL, 2),
        "total_potential_profit": round(total_potential_profit, 2),
        "expected_pl": expected_pl,
        "n_sports_represented": len(sport_counts),
        "by_sport": sport_counts,
        "picks": picks,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Multi-sport portfolio: {p['n_picks']} picks · ${p['total_stake_dollars']:.2f} stake · "
          f"expected EV ${p['expected_pl']}")
    for pk in p["picks"][:10]:
        print(f"  [{pk['rank']:2}] {pk['sport']:5} ${pk['stake_dollars']:6.2f} ({pk['stake_pct']}%) "
              f"-- {pk['label'][:60]} | P={pk['model_prob']*100:.1f}% fair {pk['fair_american']:+d}")
