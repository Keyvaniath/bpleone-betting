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

(2026-11-03) Sized ONLY from best bets with an actionable DraftKings quote
(quotes.py), at that quote's price, EV > 0; otherwise "no priced picks".
best_bets `line` is a model fair price / prop line / parlay decimal -- never a price.

Output: data/portfolio_today.json
"""
from __future__ import annotations

import os
import sys
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


def _book_quote(b: Dict[str, Any]):
    """(2026-11-03) The DK quote behind a best bet, or None. A row's `line` is a
    model fair price, a prop line (3.5) or a parlay decimal -- never a price.
    Accept only an explicit book quote (quotes.py contract), re-checked live."""
    try:
        import quotes as Q
    except Exception:
        sys.path.insert(0, os.path.dirname(__file__))
        import quotes as Q
    q = b.get("quote") if isinstance(b.get("quote"), dict) else None
    if q is None and b.get("matchup") and b.get("market"):
        q, _ = Q.find_quote(b.get("sport") or "", b.get("matchup"), b.get("market"))
    if q is None:
        return None, "no sportsbook quote"
    ok, why = Q.actionable(q)
    return (q, None) if ok else (None, why)


def run() -> Dict[str, Any]:
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    bets = bb.get("bets") or []
    # (2026-11-03) Size ONLY picks with an actionable DraftKings quote, at that
    # quote's price. No quote -> not sized. Off-season this is empty, honestly.
    priced, n_unpriced = [], 0
    for b in bets:
        q, _why = _book_quote(b)
        if q is None:
            n_unpriced += 1
            continue
        priced.append((b, q))
    if not priced:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no priced picks -- a portfolio is sized only from picks with an actionable DraftKings quote",
            "rule": bb.get("rule"),
            "excluded_unpriced": bb.get("excluded_unpriced") or {},
            "n_best_bets_without_quote": n_unpriced,
            "n_picks": 0,
            "picks": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Sort by quality + edge
    priced.sort(key=lambda bq: (-(bq[0].get("quality_score") or 0), -(bq[0].get("edge_pct") or 0)))
    picks: List[Dict[str, Any]] = []
    sport_counts: Dict[str, int] = {}
    total_exposure = 0
    seen_match_keys = set()

    for b, q in priced:
        sport = b.get("sport") or b.get("source", "?")
        if (sport_counts.get(sport) or 0) >= MAX_PER_SPORT: continue
        match_key = f"{sport}|{q.get('event_id') or b.get('team') or b.get('player') or b.get('label','')}"
        if match_key in seen_match_keys: continue

        prob = b.get("model_prob")
        if prob is None: continue
        dec = q["decimal"]
        ev = prob * dec - 1                     # EV at the REAL DK price (2026-11-03)
        if ev <= 0: continue
        q_score = b.get("quality_score") or 0
        stars = b.get("stars") or 0

        # Size by quality, capped by quarter-Kelly at the DK price
        if q_score >= 80: bet_pct = 0.05
        elif q_score >= 70: bet_pct = 0.035
        elif q_score >= 60: bet_pct = 0.02
        else: continue
        bet_pct = min(bet_pct, KELLY_FRACTION * _kelly_fraction(prob, dec), MAX_PER_PICK_PCT)
        if bet_pct <= 0: continue

        if total_exposure + bet_pct > MAX_TOTAL_PCT: continue
        total_exposure += bet_pct
        sport_counts[sport] = (sport_counts.get(sport) or 0) + 1
        seen_match_keys.add(match_key)

        stake = round(bet_pct * DEFAULT_BANKROLL, 2)
        payout = round(stake * (dec - 1), 2)

        picks.append({
            "rank": len(picks) + 1,
            "sport": sport,
            "label": b.get("label"),
            "play": b.get("play"),
            "model_prob": prob,
            "book": q.get("book"),
            "book_american": q.get("american"),
            "observed_at": q.get("observed_at"),
            "scheduled_start": q.get("scheduled_start"),
            "ev_at_book": round(ev, 4),
            "stake_pct": round(bet_pct * 100, 2),
            "stake_dollars": stake,
            "potential_profit": payout,
            "quality_score": q_score,
            "stars": stars,
        })

    total_potential_profit = sum(p["potential_profit"] for p in picks)
    expected_pl = round(sum(p["potential_profit"] * p["model_prob"] -
                            p["stake_dollars"] * (1 - p["model_prob"]) for p in picks), 2)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "default_bankroll": DEFAULT_BANKROLL,
        "kelly_fraction": KELLY_FRACTION,
        "max_per_pick_pct": MAX_PER_PICK_PCT,
        "max_total_pct": MAX_TOTAL_PCT,
        "max_per_sport": MAX_PER_SPORT,
        "price_rule": "sized only at an actionable DraftKings quote (quotes.py)",
        "n_picks": len(picks),
        "note": None if picks else "no priced picks with positive EV at the DraftKings price",
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
    print(f"Multi-sport portfolio: {p.get('n_picks', 0)} priced picks -- {p.get('note') or ''}")
    for pk in p["picks"][:10]:
        print(f"  [{pk['rank']:2}] {pk['sport']:5} ${pk['stake_dollars']:6.2f} ({pk['stake_pct']}%) "
              f"-- {(pk['label'] or '')[:60]} | P={pk['model_prob']*100:.1f}% DK {pk['book_american']:+d}")
