"""
EdgeStat - Hedging / scalp / middle calculator.

You bet a futures ticket at +1200 in April; by September it's +200.  Do you
hedge?  How much?  This module answers:

  - HEDGE: how much to bet on the opposite side now to lock in profit / minimize loss
  - GUARANTEED_PROFIT: the worst-case outcome assuming optimal hedge
  - EQUAL_PAYOUT: stake that makes the payout identical regardless of outcome
  - SCALP: small guaranteed profit when a 2-way market shows arbitrage

Same math for live in-game hedging — once your team is up 3-0 in the 5th,
the opposite-side hedge price will tell you the break-even hedge.
"""
from __future__ import annotations

import math
import json
import os
from dataclasses import dataclass
from typing import Dict


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1 + am / 100 if am > 0 else 1 + 100 / abs(am)


def hedge_for_equal_payout(original_stake: float, original_price: int,
                           hedge_price: int) -> Dict[str, float]:
    """Stake to put on opposite side so payout is the SAME whichever side wins.

    Common scenario: you have a futures ticket and want to convert it to
    "no matter what, you make $X" regardless of outcome.
    """
    win_payout_original = original_stake * (american_to_decimal(original_price) - 1)
    total_payout_if_orig_wins = original_stake + win_payout_original   # what you receive

    # If you hedge with stake H at hedge_price (decimal d2):
    #   If original wins: you receive (orig_stake + win_payout_original) - H
    #   If hedge wins:    you receive H * (d2 - 1) + H - original_stake
    #
    # Solving for equal payout in both cases:
    #   (orig + win_payout) - H = H * (d2 - 1) + H - orig
    #   2 * orig + win_payout = H * (1 + (d2 - 1) + 1) = H * (d2 + 1)
    #   H = (2 * orig + win_payout) / (d2 + 1)
    #
    # Wait, that's wrong.  Let me redo carefully.
    #
    # Total P&L if original wins:  +win_payout_original - H        (lose hedge)
    # Total P&L if hedge wins:     -original_stake + H * (d2 - 1)  (lose original, win hedge)
    #
    # Set equal:
    #   win_payout_original - H = -original_stake + H * (d2 - 1)
    #   win_payout_original + original_stake = H * d2
    #   H = (win_payout_original + original_stake) / d2
    d2 = american_to_decimal(hedge_price)
    H = (win_payout_original + original_stake) / d2
    pl_each = win_payout_original - H
    return {
        "hedge_stake": round(H, 2),
        "guaranteed_pl": round(pl_each, 2),
        "guaranteed_pl_pct_of_original": round(pl_each / original_stake * 100, 2),
        "hedge_price_decimal": round(d2, 3),
        "if_original_wins_total_pl": round(win_payout_original - H, 2),
        "if_hedge_wins_total_pl":    round(-original_stake + H * (d2 - 1), 2),
    }


def hedge_for_breakeven(original_stake: float, original_price: int,
                        hedge_price: int) -> Dict[str, float]:
    """Stake to ensure you don't LOSE anything no matter what (zero downside).
    The upside is preserved on the original side if it wins.

    Solve: -original_stake + H * (d2 - 1) = 0  =>  H = original_stake / (d2 - 1)
    """
    d2 = american_to_decimal(hedge_price)
    if d2 <= 1.0: return {"error": "Invalid hedge price"}
    H = original_stake / (d2 - 1)
    win_payout_original = original_stake * (american_to_decimal(original_price) - 1)
    pl_if_orig_wins = win_payout_original - H
    pl_if_hedge_wins = 0
    return {
        "hedge_stake": round(H, 2),
        "if_original_wins_pl": round(pl_if_orig_wins, 2),
        "if_hedge_wins_pl":    round(pl_if_hedge_wins, 2),
        "max_upside":  round(pl_if_orig_wins, 2),
        "downside":    0.0,
    }


def arbitrage_check(side_a_price: int, side_b_price: int) -> Dict[str, float]:
    """Two opposite-side prices.  Is there guaranteed profit (sum of implied < 1)?"""
    def implied(am): return 100 / (am + 100) if am > 0 else abs(am) / (abs(am) + 100)
    ia, ib = implied(side_a_price), implied(side_b_price)
    sum_implied = ia + ib
    if sum_implied >= 1.0:
        return {"is_arb": False, "vig_pct": round((sum_implied - 1) * 100, 3),
                "implied_sum": round(sum_implied, 4)}
    # Optimal split: weight inverse to decimal odds.
    da = american_to_decimal(side_a_price)
    db = american_to_decimal(side_b_price)
    weight_a = (1 / da) / (1 / da + 1 / db)
    weight_b = 1 - weight_a
    profit_pct = (1 - sum_implied) * 100
    return {
        "is_arb": True,
        "profit_pct": round(profit_pct, 3),
        "stake_split_pct": [round(weight_a * 100, 2), round(weight_b * 100, 2)],
        "implied_sum": round(sum_implied, 4),
    }


# --------------------------- Demo ---------------------------

if __name__ == "__main__":
    print("=== HEDGE TO EQUAL PAYOUT ===")
    print("You bet $100 on Dodgers to win the World Series at +1400 in April.")
    print("It's now September. Dodgers are +250 to win it all.\n")
    res = hedge_for_equal_payout(original_stake=100, original_price=+1400,
                                  hedge_price=+250)
    for k, v in res.items():
        print(f"  {k:>34}: {v}")
    print()
    print("=== HEDGE TO BREAK-EVEN ONLY ===")
    print("Same situation, but you want to KEEP the upside if LAD wins.")
    print("Just guarantee you don't lose money:\n")
    res2 = hedge_for_breakeven(original_stake=100, original_price=+1400,
                                hedge_price=+250)
    for k, v in res2.items():
        print(f"  {k:>34}: {v}")
    print()
    print("=== ARBITRAGE CHECK ===")
    print("Side A at +145, Side B at -125 across two different books:\n")
    res3 = arbitrage_check(side_a_price=+145, side_b_price=-125)
    for k, v in res3.items():
        print(f"  {k:>30}: {v}")

    os.makedirs("../data", exist_ok=True)
    with open("../data/hedge_examples.json", "w") as f:
        json.dump({
            "examples": {
                "ws_hedge_equal_payout": res,
                "ws_hedge_break_even":   res2,
                "arb_check":             res3,
            }
        }, f, indent=2)
    print("\nWrote ../data/hedge_examples.json")
