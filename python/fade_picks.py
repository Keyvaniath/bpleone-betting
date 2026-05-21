"""
EdgeStat -- Fade Picks of the Day.

Identifies plays where the BOOK is over-pricing a side relative to the
model. We bet AGAINST the book's favorite ("fade" it) when:
  - Model assigns lower probability than the book's implied price
  - Edge is at least 5% in the underdog direction
  - Probability is in a livable band (30-50% so it's not a true longshot)

These are the inverse of Alpha Pick / POD — instead of finding where the
model loves a side, we find where the model says "the book has this side
overrated; the other side is live."

Method:
  Scan todays_top_plays.json. Each pick has:
    prob (model)
    decimal_odds (model fair odds)
  Currently we don't pull live book odds, so we use model decimal_odds
  as a baseline and look for plays the model thinks are LIVE underdogs
  (probability 0.30-0.50, fair_american positive).

  When live book odds are wired later (the-odds-api integration), this
  module will compare model_prob to (1/book_decimal) and surface fades
  where the gap is genuine.

  For now: surface picks where model_prob is 0.30-0.50 (live underdogs
  the model thinks are reasonable bets at +150 to +233).

Output: data/fade_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "fade_picks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(a):
    if a is None or not isinstance(a, (int, float)): return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _decimal_to_american(d):
    if d is None or d <= 1.0: return None
    if d >= 2.0: return int(round((d - 1) * 100))
    return -int(round(100 / (d - 1)))


def run() -> Dict[str, Any]:
    top = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    plays = top.get("top_25") or []

    fades: List[Dict[str, Any]] = []
    for p in plays:
        prob = p.get("prob")
        if prob is None: continue

        # FADE = live underdog the model thinks has fair value
        # Model says 30-50% on a side that book likely prices as a dog
        if 0.30 <= prob <= 0.50:
            dec = p.get("decimal_odds") or _american_to_decimal(p.get("fair_american"))
            if not dec or dec < 2.0: continue   # not actually a dog
            roi = prob * dec - 1
            if roi < 0.05: continue   # need 5%+ edge in dog direction
            fades.append({
                "sport": p.get("sport"),
                "player_or_matchup": p.get("player_or_matchup"),
                "team": p.get("team"),
                "market": p.get("market"),
                "market_family": p.get("market_family"),
                "model_prob": round(prob, 4),
                "fair_american": p.get("fair_american"),
                "decimal_odds": round(dec, 3),
                "roi_per_dollar": round(roi, 4),
                "edge_pct": p.get("edge_pct"),
                "kelly_fraction": p.get("kelly_fraction"),
                "unit_size_quarter_kelly": p.get("unit_size_quarter_kelly"),
                "source_module": p.get("source"),
                "fade_type": (
                    "live_dog" if prob < 0.40 else "coinflip_dog"
                ),
            })

    fades.sort(key=lambda c: -c["roi_per_dollar"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fades": len(fades),
        "top_5_fades": fades[:5],
        "all_fades": fades,
        "method_note": "Fade Picks = live underdogs (model_prob 30-50%) with 5%+ ROI. "
                       "Inverse of Alpha Pick — these are bets AGAINST the book's "
                       "favorite. Will get stronger when live book odds wired in.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[fade-picks] {o['n_fades']} fades found -> {OUT}")
    for f in o['top_5_fades']:
        print(f"  {f['sport']} {f['player_or_matchup'][:24]} {f['market'][:24]} "
              f"p={f['model_prob']:.1%} odds={f['fair_american']:+d} "
              f"ROI={f['roi_per_dollar']:+.1%}")
