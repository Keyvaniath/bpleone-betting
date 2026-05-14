"""
EdgeStat - Arbitrage / middle / scalp / low-vig detector.

Pulls a synthetic cross-book line snapshot and finds:
  * ARB  - true arbitrage (sum implied probs < 1).  Guaranteed profit.
  * REDUCED VIG - 2-way market with vig under 3% (still risk, but a +EV play
                  if you have an edge).
  * MIDDLE - spread/total markets where you can bet BOTH sides with two
             different books and have a free roll on the games landing in
             the middle.
  * SCALP  - opposite of middle: small guaranteed profit when one side wins
             on book A and the other side wins on book B.

This is the fastest, lowest-variance form of betting -- but books are quick
to ban arbers, so it's used carefully.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1.0 + am / 100.0 if am > 0 else 1.0 + 100.0 / abs(am)


def american_to_implied(am: int) -> float:
    return 100 / (am + 100) if am > 0 else abs(am) / (abs(am) + 100)


@dataclass
class BookQuote:
    book: str
    side: str         # e.g. "LAD" or "OVER 8.0" or "LAD -1.5"
    line: Optional[float]   # for spread/total; None for ML
    price: int


@dataclass
class Market:
    matchup: str
    market_type: str   # "ML" | "spread" | "total"
    quotes: List[BookQuote]


# --------------------------- Arb math ---------------------------

def find_arbs(market: Market) -> List[dict]:
    """Find pairs of opposite-side quotes from different books with implied
    probability sum < 1.  Each found arb returns the optimal stake split.

    For ML markets: pair quotes that are on opposite teams.
    For spreads / totals: pair the OVER and UNDER (or favorite + dog) at the
    same line.
    """
    arbs = []
    # Group quotes by "opposite-side" key.
    if market.market_type == "ML":
        sides = list({q.side for q in market.quotes})
        if len(sides) < 2: return arbs
        side_a, side_b = sides[0], sides[1]
        for qa in [q for q in market.quotes if q.side == side_a]:
            for qb in [q for q in market.quotes if q.side == side_b]:
                if qa.book == qb.book: continue
                ia = american_to_implied(qa.price)
                ib = american_to_implied(qb.price)
                if ia + ib < 1.0:
                    profit = round((1 - (ia + ib)) * 100, 3)
                    # Stake split: weight inverse to decimal odds.
                    dec_a = american_to_decimal(qa.price)
                    dec_b = american_to_decimal(qb.price)
                    s_a = (1 / dec_a) / (1 / dec_a + 1 / dec_b)
                    s_b = 1 - s_a
                    arbs.append({
                        "side_a": f"{qa.book} {qa.side} {qa.price:+d}",
                        "side_b": f"{qb.book} {qb.side} {qb.price:+d}",
                        "implied_sum_pct": round((ia + ib) * 100, 2),
                        "profit_pct": profit,
                        "stake_split": [round(s_a * 100, 1), round(s_b * 100, 1)],
                    })
    elif market.market_type in ("spread", "total"):
        # Pair opposite sides at the same line.
        sides = list({(q.side, q.line) for q in market.quotes})
        for (side_a, line_a) in sides:
            for (side_b, line_b) in sides:
                if side_a == side_b: continue
                if line_a != line_b: continue
                for qa in [q for q in market.quotes if q.side == side_a and q.line == line_a]:
                    for qb in [q for q in market.quotes if q.side == side_b and q.line == line_b]:
                        if qa.book == qb.book: continue
                        ia = american_to_implied(qa.price)
                        ib = american_to_implied(qb.price)
                        if ia + ib < 1.0:
                            profit = round((1 - (ia + ib)) * 100, 3)
                            dec_a = american_to_decimal(qa.price)
                            dec_b = american_to_decimal(qb.price)
                            s_a = (1 / dec_a) / (1 / dec_a + 1 / dec_b)
                            s_b = 1 - s_a
                            arbs.append({
                                "side_a": f"{qa.book} {qa.side} {qa.line}",
                                "side_b": f"{qb.book} {qb.side} {qb.line}",
                                "prices": [qa.price, qb.price],
                                "profit_pct": profit,
                                "stake_split": [round(s_a * 100, 1), round(s_b * 100, 1)],
                            })
    return arbs


def find_middles(market: Market) -> List[dict]:
    """Find spread/total middle opportunities.

    A middle exists when:
      * Book A has the favorite/over at a softer line (e.g. -5)
      * Book B has the dog/under at a harder line (e.g. +7)
    If the game lands between (5 < margin < 7), BOTH bets win.
    """
    if market.market_type not in ("spread", "total"):
        return []
    middles = []
    # Pair quotes from different books where lines create a window.
    for qa in market.quotes:
        for qb in market.quotes:
            if qa.book == qb.book: continue
            if qa.side == qb.side: continue
            if qa.line is None or qb.line is None: continue
            # For totals: OVER X.5 vs UNDER Y.5 where X < Y is a middle.
            if market.market_type == "total":
                if qa.side.upper().startswith("OVER") and qb.side.upper().startswith("UNDER"):
                    if qa.line < qb.line:
                        middles.append({
                            "type": "TOTAL MIDDLE",
                            "side_a": f"{qa.book} {qa.side} {qa.line} ({qa.price:+d})",
                            "side_b": f"{qb.book} {qb.side} {qb.line} ({qb.price:+d})",
                            "middle_window": f"{qa.line} - {qb.line}",
                            "risk_pct": round((american_to_implied(qa.price)
                                              + american_to_implied(qb.price) - 1) * 100, 2),
                        })
            elif market.market_type == "spread":
                # Favorite at -X.5 with dog at +(X+w).5 = middle window of w runs.
                # We expect like "LAD -1.5" form. For brevity, just flag pairs
                # where one quote's line < other's by 1+ and they're opposite directions.
                if qa.line < qb.line:
                    middles.append({
                        "type": "RUNLINE MIDDLE",
                        "side_a": f"{qa.book} {qa.side} {qa.line} ({qa.price:+d})",
                        "side_b": f"{qb.book} {qb.side} {qb.line} ({qb.price:+d})",
                        "middle_window": f"{qa.line} - {qb.line}",
                    })
    return middles


def find_low_vig(market: Market, max_vig_pct: float = 3.0) -> List[dict]:
    """Find 2-way market pairings with combined vig under threshold."""
    out = []
    if market.market_type != "ML":
        return out
    sides = list({q.side for q in market.quotes})
    if len(sides) < 2: return out
    a_quotes = [q for q in market.quotes if q.side == sides[0]]
    b_quotes = [q for q in market.quotes if q.side == sides[1]]
    for qa in a_quotes:
        for qb in b_quotes:
            if qa.book == qb.book: continue
            vig = (american_to_implied(qa.price) + american_to_implied(qb.price) - 1) * 100
            if vig <= max_vig_pct:
                out.append({
                    "side_a": f"{qa.book} {qa.side} {qa.price:+d}",
                    "side_b": f"{qb.book} {qb.side} {qb.price:+d}",
                    "vig_pct": round(vig, 2),
                })
    return out


# --------------------------- Demo snapshot ---------------------------

TODAY_MARKETS = [
    Market(matchup="LAD vs SDP", market_type="ML", quotes=[
        BookQuote("Pinnacle",   "LAD", None, -152), BookQuote("Pinnacle",   "SDP", None, +138),
        BookQuote("DraftKings", "LAD", None, -148), BookQuote("DraftKings", "SDP", None, +126),
        BookQuote("FanDuel",    "LAD", None, -146), BookQuote("FanDuel",    "SDP", None, +124),
        BookQuote("Caesars",    "LAD", None, -150), BookQuote("Caesars",    "SDP", None, +128),
        BookQuote("BetMGM",     "LAD", None, -148), BookQuote("BetMGM",     "SDP", None, +126),
        BookQuote("ESPN BET",   "LAD", None, -145), BookQuote("ESPN BET",   "SDP", None, +132),
        # Arb opportunity hiding here: ESPN BET +132 SDP vs Pinnacle -148 actually arbs vs FanDuel -146/+124 (no)
    ]),
    Market(matchup="NYY vs BOS", market_type="ML", quotes=[
        BookQuote("Pinnacle",   "NYY", None, -138), BookQuote("Pinnacle",   "BOS", None, +128),
        BookQuote("DraftKings", "NYY", None, -130), BookQuote("DraftKings", "BOS", None, +110),
        BookQuote("FanDuel",    "NYY", None, -135), BookQuote("FanDuel",    "BOS", None, +120),
        BookQuote("Caesars",    "NYY", None, -132), BookQuote("Caesars",    "BOS", None, +118),
        BookQuote("BetMGM",     "NYY", None, -128), BookQuote("BetMGM",     "BOS", None, +115),
        # Caesars NYY -132 vs DraftKings BOS +110 -> implied 0.569+0.476 = 1.045 (no arb)
        # but PUSH it: DraftKings BOS +135 (intentionally errored), creates arb.
        BookQuote("Synthetic-Glitch", "BOS", None, +145),   # rare bookkeeping glitch
    ]),
    Market(matchup="HOU vs TEX", market_type="total", quotes=[
        BookQuote("Pinnacle",   "OVER", 7.5, -108),  BookQuote("Pinnacle",   "UNDER", 7.5, -102),
        BookQuote("DraftKings", "OVER", 7.5, -110),  BookQuote("DraftKings", "UNDER", 7.5, -110),
        BookQuote("FanDuel",    "OVER", 8.0, -115),  BookQuote("FanDuel",    "UNDER", 8.0, -105),
        BookQuote("Caesars",    "OVER", 7.5, -112),  BookQuote("Caesars",    "UNDER", 7.5, -108),
        # Middle: DK OVER 7.5 + FanDuel UNDER 8.0 -> if game = exactly 8 (push on under) or
        # actually total exactly 8 hits the middle for over.
    ]),
]


def scan_all() -> dict:
    arbs_all = []
    middles_all = []
    low_vig_all = []
    for m in TODAY_MARKETS:
        for a in find_arbs(m):
            a["market"] = m.matchup
            arbs_all.append(a)
        for mid in find_middles(m):
            mid["market"] = m.matchup
            middles_all.append(mid)
        for lv in find_low_vig(m):
            lv["market"] = m.matchup
            low_vig_all.append(lv)
    return {
        "arbs": arbs_all,
        "middles": middles_all,
        "low_vig": low_vig_all,
        "markets_scanned": len(TODAY_MARKETS),
        "quotes_scanned": sum(len(m.quotes) for m in TODAY_MARKETS),
    }


def write_artifact(out, path="../data/arbitrage.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    out = scan_all()
    print(f"Scanned {out['markets_scanned']} markets, {out['quotes_scanned']} quotes")
    print(f"\nARBS FOUND: {len(out['arbs'])}")
    for a in out['arbs'][:5]:
        print(f"  {a['market']}: {a['side_a']} <> {a['side_b']}  | profit: {a['profit_pct']}%  stake split {a['stake_split']}")
    print(f"\nLOW VIG (under 3%): {len(out['low_vig'])}")
    for lv in out['low_vig'][:5]:
        print(f"  {lv['market']}: {lv['side_a']} <> {lv['side_b']}  | vig: {lv['vig_pct']}%")
    print(f"\nMIDDLES: {len(out['middles'])}")
    for mid in out['middles'][:3]:
        print(f"  {mid['market']}: {mid.get('type','?')} window {mid['middle_window']}")
    write_artifact(out)
