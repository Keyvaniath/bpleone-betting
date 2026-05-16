"""
EdgeStat -- portfolio Monte Carlo for tonight's plays.

Given the current best_bets list + a configured bankroll + Kelly fraction,
simulates the night's outcome distribution 10K times to produce:
  - Expected P&L (mean)
  - 5th / 25th / 50th / 75th / 95th percentile P&L
  - P(profit), P(ruin), worst-case drawdown
  - Per-bet contribution to portfolio variance

The output drives a /bankroll-sim card showing Brandon what tonight's
slate is REALLY worth in dollar terms with proper confidence bounds.

Inputs:
  best_bets.json: top-quality plays with model_prob + edge_pct
  data/runtime_config.json: optional bankroll + kelly_fraction overrides
                            (falls back to BANKROLL_DEFAULT)

Output: data/bankroll_sim.json
"""
from __future__ import annotations

import os
import json
import random
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BEST_BETS_PATH = os.path.join(DATA_DIR, "best_bets.json")
RUNTIME_PATH = os.path.join(DATA_DIR, "runtime_config.json")
OUT_PATH = os.path.join(DATA_DIR, "bankroll_sim.json")

N_TRIALS = 10000
BANKROLL_DEFAULT = 1000.0
KELLY_FRACTION_DEFAULT = 0.25
MAX_BET_FRAC = 0.05    # cap any single bet at 5% of bankroll regardless of Kelly
MAX_BETS_PER_NIGHT = 25


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _kelly_stake(p_win: float, american_price: int, bankroll: float, frac: float) -> float:
    """Standard Kelly: f = (bp - q) / b where b = decimal odds - 1, p = win prob, q = lose."""
    if p_win <= 0 or p_win >= 1:
        return 0.0
    b = (american_price / 100.0) if american_price >= 0 else (100.0 / abs(american_price))
    q = 1 - p_win
    f = (b * p_win - q) / b
    f = max(0.0, f) * frac
    f = min(f, MAX_BET_FRAC)
    return round(bankroll * f, 2)


def run() -> Dict[str, Any]:
    bb = _load(BEST_BETS_PATH).get("bets") or []
    rt = _load(RUNTIME_PATH)
    bankroll = float(rt.get("bankroll.starting_units", BANKROLL_DEFAULT))
    kelly_frac = float(rt.get("plays.kelly_fraction", KELLY_FRACTION_DEFAULT))

    # Convert candidate bets into (player, win_prob, american_price, stake)
    book_price = -110   # conservative typical prop price assumption
    portfolio: List[Dict[str, Any]] = []
    for b in bb[:MAX_BETS_PER_NIGHT]:
        p = b.get("model_prob")
        if p is None or p < 0.50 or p > 0.95:
            continue
        # Accept DK + PP + NRFI flat plays (treat at -110). Skip SGPs (price
        # is inherently structured, embedded in the leg list).
        if b.get("source") not in ("DK", "PP", "NRFI"):
            continue
        stake = _kelly_stake(p, book_price, bankroll, kelly_frac)
        if stake <= 0:
            continue
        portfolio.append({
            "rank": b.get("rank"),
            "label": b.get("label"),
            "player_id": b.get("player_id"),
            "market": b.get("market"),
            "p_win": round(p, 4),
            "american_price": book_price,
            "stake": stake,
            "max_profit": round(stake * ((book_price / 100.0) if book_price >= 0 else (100.0 / abs(book_price))), 2),
            "max_loss": -stake,
        })

    if not portfolio:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_bets": 0, "bankroll": bankroll, "kelly_fraction": kelly_frac,
            "note": "No qualifying bets in best_bets for the simulator (need DK/PP source with model_prob 0.50-0.95)",
        }
    else:
        # Monte Carlo
        random.seed(42)
        total_pls: List[float] = []
        per_bet_wins = [0] * len(portfolio)
        for _ in range(N_TRIALS):
            pl = 0.0
            for i, b in enumerate(portfolio):
                if random.random() < b["p_win"]:
                    pl += b["max_profit"]
                    per_bet_wins[i] += 1
                else:
                    pl += b["max_loss"]
            total_pls.append(pl)
        total_pls.sort()
        def pct(v):
            i = int(len(total_pls) * v)
            return total_pls[min(max(i, 0), len(total_pls) - 1)]
        mean_pl = sum(total_pls) / len(total_pls)
        n_profit = sum(1 for x in total_pls if x > 0)
        n_ruin = sum(1 for x in total_pls if x <= -bankroll * 0.5)
        # Per-bet contribution = variance contribution
        for i, b in enumerate(portfolio):
            p = b["p_win"]
            var_contrib = (b["max_profit"] - b["max_loss"]) ** 2 * p * (1 - p)
            b["hit_rate_sim"] = round(per_bet_wins[i] / N_TRIALS, 3)
            b["variance_contrib"] = round(var_contrib, 2)
            b["ev"] = round(p * b["max_profit"] + (1 - p) * b["max_loss"], 2)
        total_stake = sum(b["stake"] for b in portfolio)
        total_ev = sum(b["ev"] for b in portfolio)
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_bets": len(portfolio),
            "bankroll": bankroll,
            "kelly_fraction": kelly_frac,
            "total_stake": round(total_stake, 2),
            "stake_pct_of_bankroll": round(total_stake / bankroll * 100, 2),
            "expected_pl": round(total_ev, 2),
            "ev_roi_pct": round((total_ev / total_stake) * 100, 2) if total_stake else 0,
            "n_trials": N_TRIALS,
            "p_profit": round(n_profit / N_TRIALS, 3),
            "p_significant_loss": round(n_ruin / N_TRIALS, 4),
            "percentiles": {
                "p05": round(pct(0.05), 2),
                "p25": round(pct(0.25), 2),
                "p50": round(pct(0.50), 2),
                "p75": round(pct(0.75), 2),
                "p95": round(pct(0.95), 2),
            },
            "histogram": _histogram(total_pls, 20),
            "portfolio": portfolio,
        }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


def _histogram(values: List[float], bins: int) -> List[Dict[str, Any]]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [{"bin_lo": lo, "bin_hi": hi, "count": len(values)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return [{"bin_lo": round(lo + i * width, 2),
              "bin_hi": round(lo + (i + 1) * width, 2),
              "count": counts[i]} for i in range(bins)]


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p.get('n_bets', 0)} bets sized")
    if p.get("n_bets"):
        print(f"  bankroll: ${p['bankroll']}")
        print(f"  total stake: ${p['total_stake']} ({p['stake_pct_of_bankroll']}%)")
        print(f"  expected P&L: ${p['expected_pl']} (ROI {p['ev_roi_pct']}%)")
        print(f"  P(profit):  {p['p_profit']*100:.1f}%")
        print(f"  percentiles: p05=${p['percentiles']['p05']} p50=${p['percentiles']['p50']} p95=${p['percentiles']['p95']}")
