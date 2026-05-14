"""
EdgeStat - Linemaker (bookmaker) engine.

This is the bookie's perspective. Given a fair probability of an outcome, set
an opening line, then adjust as money flows in to keep the book balanced and
hit a target hold percentage.

Three core jobs:
  1. Open the line.  Take fair prob -> add target vig -> publish opening odds.
  2. Re-shade with handle.  As bettors hit one side, move the line to attract
     the other side and stay balanced.
  3. Track exposure.  Live P&L the book faces on each market.

This is the same loop Caesars and Pinnacle run on every game.  Understanding
it makes you a better bettor: you see where the book will move and why.
"""
from __future__ import annotations

import math
import random
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# --------------------------- Math helpers ---------------------------

def prob_to_american(p: float) -> int:
    p = max(0.01, min(p, 0.99))
    dec = 1 / p
    return int(round((dec - 1) * 100)) if dec >= 2 else -int(round(100 / (dec - 1)))


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1.0 + am / 100.0 if am > 0 else 1.0 + 100.0 / abs(am)


def american_to_implied(am: int) -> float:
    return 100 / (am + 100) if am > 0 else abs(am) / (abs(am) + 100)


# --------------------------- Line setting ---------------------------

@dataclass
class Line:
    side_a: str
    side_b: str
    fair_p_a: float            # bookmaker's estimate of true P(side_a wins)
    target_hold_pct: float = 4.5   # target hold = vig %
    # Output
    open_price_a: int = 0
    open_price_b: int = 0
    current_price_a: int = 0
    current_price_b: int = 0
    handle_a: float = 0.0      # dollars bet on side A
    handle_b: float = 0.0
    line_moves: List[dict] = field(default_factory=list)


def open_line(side_a: str, side_b: str, fair_p_a: float,
              target_hold_pct: float = 4.5) -> Line:
    """Set an opening line that builds in `target_hold_pct` vig.

    Method: take fair probabilities, scale up by hold fraction, convert to
    American odds.  The book wants P(A) + P(B) (after vig) = 1 + hold.
    """
    fair_p_b = 1 - fair_p_a
    hold = target_hold_pct / 100
    # Add half the hold to each side.
    p_a_w_vig = fair_p_a * (1 + hold)
    p_b_w_vig = fair_p_b * (1 + hold)
    # Re-normalize to exactly sum to 1 + hold.
    s = p_a_w_vig + p_b_w_vig
    p_a_w_vig = p_a_w_vig / s * (1 + hold)
    p_b_w_vig = p_b_w_vig / s * (1 + hold)
    am_a = prob_to_american(p_a_w_vig)
    am_b = prob_to_american(p_b_w_vig)
    line = Line(
        side_a=side_a, side_b=side_b, fair_p_a=fair_p_a,
        target_hold_pct=target_hold_pct,
        open_price_a=am_a, open_price_b=am_b,
        current_price_a=am_a, current_price_b=am_b,
    )
    line.line_moves.append({
        "timestamp": "open", "trigger": "open",
        "price_a": am_a, "price_b": am_b,
        "imbalance_pct": 0.0,
    })
    return line


# --------------------------- Re-shading ---------------------------

def imbalance_pct(line: Line) -> float:
    """Percentage of total handle on side A.  50% = balanced."""
    total = line.handle_a + line.handle_b
    if total == 0:
        return 50.0
    return line.handle_a / total * 100


def book_exposure(line: Line) -> Dict[str, float]:
    """Estimate book's P&L conditional on each side winning.

    If A wins: book pays out winners on side A their odds × stake.
    If B wins: book pays out winners on side B.
    Pre-game; assumes no settling yet.
    """
    pay_if_a = line.handle_a * (american_to_decimal(line.current_price_a) - 1)
    pay_if_b = line.handle_b * (american_to_decimal(line.current_price_b) - 1)
    total_in = line.handle_a + line.handle_b
    return {
        "pl_if_a_wins": round(total_in - pay_if_a, 2),
        "pl_if_b_wins": round(total_in - pay_if_b, 2),
        "expected_pl":  round(total_in - pay_if_a * line.fair_p_a
                              - pay_if_b * (1 - line.fair_p_a), 2),
    }


def bet_arrives(line: Line, side: str, dollars: float,
                trigger: str = "bet") -> None:
    """Process an incoming wager. Side: 'A' or 'B'."""
    if side == "A":
        line.handle_a += dollars
    else:
        line.handle_b += dollars

    # Re-shade rules - clamped to keep this realistic, not run-away.
    total = line.handle_a + line.handle_b
    if total < 500:
        return
    imb = imbalance_pct(line)
    # Hard cap cumulative movement from opening implied prob to ±5%.
    open_p_a = american_to_implied(line.open_price_a)
    current_p_a = american_to_implied(line.current_price_a)
    moved = abs(current_p_a - open_p_a)
    if moved >= 0.05:
        # At cap. Only record once.
        last = line.line_moves[-1] if line.line_moves else {}
        if last.get("price_a") == line.current_price_a and last.get("price_b") == line.current_price_b:
            return
    # Decide if we move at all this tick.
    if trigger == "SHARP" and (imb > 55 or imb < 45):
        shift = 0.010
    elif imb > 65 or imb < 35:
        shift = 0.004
    else:
        shift = 0.0
    if shift != 0:
        if imb > 50:
            target_p_a = min(open_p_a + 0.05, current_p_a + shift)
        else:
            target_p_a = max(open_p_a - 0.05, current_p_a - shift)
        target_p_a = max(0.05, min(0.95, target_p_a))
        target_p_b = max(0.05, min(0.95, 1 + line.target_hold_pct / 100 - target_p_a))
        line.current_price_a = prob_to_american(target_p_a)
        line.current_price_b = prob_to_american(target_p_b)
    # Only record move if the price actually changed.
    last = line.line_moves[-1] if line.line_moves else {}
    if last.get("price_a") == line.current_price_a and last.get("price_b") == line.current_price_b:
        return
    line.line_moves.append({
        "timestamp": f"+${total:.0f}", "trigger": trigger,
        "price_a": line.current_price_a, "price_b": line.current_price_b,
        "imbalance_pct": round(imb, 1),
        "handle_a": round(line.handle_a, 0),
        "handle_b": round(line.handle_b, 0),
    })


# --------------------------- Simulation: a day in the life ---------------------------

def simulate_market_day(line: Line, n_bets: int = 200,
                        avg_bet_size: float = 50.0,
                        public_lean_side_a: float = 0.55,
                        sharp_window: Tuple[int, int] = (60, 80),
                        seed: int = 17) -> Line:
    """Simulate a typical day of action on this line.

    public_lean_side_a = how much the public favors side A (0.55 = 55% of
    public tickets on A).  Sharp bettors (large tickets) arrive during the
    sharp_window indices and fade the public.
    """
    rng = random.Random(seed)
    for i in range(n_bets):
        in_sharp_window = sharp_window[0] <= i <= sharp_window[1]
        if in_sharp_window:
            # Sharps bet big and against the public.
            side = "B" if rng.random() < public_lean_side_a else "A"
            dollars = rng.gauss(avg_bet_size * 8, avg_bet_size * 2)
            trigger = "SHARP"
        else:
            side = "A" if rng.random() < public_lean_side_a else "B"
            dollars = max(5, rng.gauss(avg_bet_size, avg_bet_size * 0.5))
            trigger = "public"
        bet_arrives(line, side, dollars, trigger=trigger)
    return line


# --------------------------- Artifact writer ---------------------------

def write_linemaker_demo(path: str = "../data/linemaker.json") -> None:
    """Build a demo line and save the full timeline for the front-end."""
    # Demo: LAD/SDP, fair 62% LAD.
    line = open_line("LAD", "SDP", fair_p_a=0.62, target_hold_pct=4.5)
    simulate_market_day(line, n_bets=140, avg_bet_size=40, public_lean_side_a=0.59,
                        sharp_window=(40, 55), seed=21)
    payload = {
        "matchup": "LAD vs SDP",
        "fair_prob_a": line.fair_p_a,
        "open": {"price_a": line.open_price_a, "price_b": line.open_price_b},
        "current": {"price_a": line.current_price_a, "price_b": line.current_price_b},
        "handle": {"a": round(line.handle_a, 0), "b": round(line.handle_b, 0),
                   "imbalance_pct": round(imbalance_pct(line), 1)},
        "exposure": book_exposure(line),
        "moves": line.line_moves,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    line = open_line("LAD", "SDP", fair_p_a=0.62, target_hold_pct=4.5)
    print(f"Open: LAD {line.open_price_a:+d}  |  SDP {line.open_price_b:+d}")
    print(f"Implied: LAD {american_to_implied(line.open_price_a):.3f}  "
          f"+ SDP {american_to_implied(line.open_price_b):.3f}  "
          f"= {american_to_implied(line.open_price_a)+american_to_implied(line.open_price_b):.3f}")
    simulate_market_day(line, n_bets=140, avg_bet_size=40,
                        public_lean_side_a=0.59, sharp_window=(40, 55), seed=21)
    print(f"\nFinal: LAD {line.current_price_a:+d}  |  SDP {line.current_price_b:+d}")
    print(f"Handle: LAD ${line.handle_a:.0f}  |  SDP ${line.handle_b:.0f}  "
          f"(imbalance: {imbalance_pct(line):.1f}%)")
    print(f"Exposure: {book_exposure(line)}")
    print(f"Total moves: {len(line.line_moves)}")
    write_linemaker_demo()
