"""
EdgeStat - Risk & bankroll Monte Carlo.

Three exposures every serious bettor needs to know:
  1. Bankroll path distribution - where am I likely to be in 200 plays?
  2. Maximum drawdown distribution - what's the worst likely losing streak?
  3. Risk of ruin - probability of busting before recovering.

We Monte Carlo all three over realistic plays-per-year volume.
"""
from __future__ import annotations

import random
import statistics
import json
import os
from typing import List, Dict, Tuple


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1.0 + am / 100.0 if am > 0 else 1.0 + 100.0 / abs(am)


def kelly_full(p: float, am: int) -> float:
    b = american_to_decimal(am) - 1
    if b <= 0: return 0.0
    return max(0.0, (b * p - (1 - p)) / b)


# --------------------------- Single bankroll path ---------------------------

def simulate_path(p_win: float, american_price: int,
                  n_plays: int, kelly_fraction: float,
                  bankroll_start: float = 100.0,
                  ruin_threshold: float = 25.0,
                  rng: random.Random = None) -> Tuple[List[float], float, bool]:
    """Return (bankroll_path, max_dd_pct, ruined)."""
    rng = rng or random
    bankroll = bankroll_start
    path = [bankroll]
    peak = bankroll
    max_dd = 0.0
    ruined = False
    dec = american_to_decimal(american_price)
    f_full = kelly_full(p_win, american_price)
    f_used = f_full * kelly_fraction
    for _ in range(n_plays):
        stake = bankroll * f_used
        won = rng.random() < p_win
        bankroll += stake * (dec - 1) if won else -stake
        path.append(bankroll)
        peak = max(peak, bankroll)
        dd = (peak - bankroll) / peak * 100
        max_dd = max(max_dd, dd)
        if bankroll <= ruin_threshold:
            ruined = True
    return path, max_dd, ruined


# --------------------------- Monte Carlo over many paths ---------------------------

def monte_carlo_bankroll(p_win: float = 0.55, american_price: int = -110,
                         n_plays: int = 200, kelly_fraction: float = 0.25,
                         n_sims: int = 2000, seed: int = 7) -> Dict:
    rng = random.Random(seed)
    finals = []
    max_dds = []
    n_ruined = 0
    path_samples = []
    for i in range(n_sims):
        path, max_dd, ruined = simulate_path(p_win, american_price, n_plays,
                                             kelly_fraction, rng=rng)
        finals.append(path[-1])
        max_dds.append(max_dd)
        if ruined:
            n_ruined += 1
        if i < 25:   # keep a few sample paths for the chart
            path_samples.append([round(x, 2) for x in path])
    finals.sort()
    return {
        "n_sims": n_sims,
        "n_plays": n_plays,
        "median_final": round(statistics.median(finals), 2),
        "mean_final":   round(statistics.mean(finals), 2),
        "p10_final":    round(finals[int(0.10 * n_sims)], 2),
        "p25_final":    round(finals[int(0.25 * n_sims)], 2),
        "p75_final":    round(finals[int(0.75 * n_sims)], 2),
        "p90_final":    round(finals[int(0.90 * n_sims)], 2),
        "ruin_prob":    round(n_ruined / n_sims * 100, 2),
        "max_dd_median": round(statistics.median(max_dds), 2),
        "max_dd_p90":    round(sorted(max_dds)[int(0.90 * n_sims)], 2),
        "path_samples": path_samples,
        "config": {
            "p_win": p_win, "american_price": american_price,
            "kelly_fraction": kelly_fraction,
        }
    }


# --------------------------- Optimal Kelly heatmap ---------------------------

def kelly_heatmap(price: int = -110,
                  win_probs: List[float] = None,
                  fractions: List[float] = None,
                  n_plays: int = 200, n_sims: int = 800) -> Dict:
    """Grid over (win_prob, kelly_fraction) returning median final bankroll."""
    win_probs = win_probs or [0.51, 0.53, 0.55, 0.57, 0.59, 0.61]
    fractions = fractions or [0.10, 0.20, 0.25, 0.33, 0.50, 0.75, 1.00]
    grid = []
    for p in win_probs:
        row = []
        for f in fractions:
            res = monte_carlo_bankroll(p, price, n_plays, f, n_sims, seed=21)
            row.append({"median": res["median_final"],
                        "ruin": res["ruin_prob"],
                        "max_dd": res["max_dd_p90"]})
        grid.append({"p_win": p, "cells": row})
    return {"price": price, "win_probs": win_probs, "fractions": fractions, "grid": grid}


def write_artifact(payload: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    print("=== Bankroll Monte Carlo (default sharp profile) ===")
    out = monte_carlo_bankroll(p_win=0.55, american_price=-110,
                               n_plays=200, kelly_fraction=0.25,
                               n_sims=2000, seed=99)
    for k, v in out.items():
        if k != "path_samples":
            print(f"  {k:>16}: {v}")
    write_artifact(out, "../data/bankroll_mc.json")
    print()
    print("=== Computing Kelly fraction heatmap (this takes ~30s)…")
    heat = kelly_heatmap(price=-110, n_plays=200, n_sims=400)
    write_artifact(heat, "../data/kelly_heatmap.json")
    print("Kelly heatmap rows:")
    for row in heat["grid"]:
        print(f"  p_win={row['p_win']:.2f}: ", end="")
        for i, cell in enumerate(row["cells"]):
            f = heat["fractions"][i]
            print(f"f={f:.2f}→${cell['median']:.0f}", end="  ")
        print()
