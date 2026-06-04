"""
EdgeStat -- NFL player-prop Monte Carlo simulator.

Replaces the normal-CDF approximation in nfl_player_props with a play-level Monte
Carlo, the way mlb_model uses a PA-level simulator. Instead of pretending a
player's stat is Normal(mu, sigma), we simulate the actual generative process and
read the empirical distribution -- which gets the SKEW (yards are right-skewed),
the COUNT x PER-EVENT compounding (attempts x yards/attempt), and the DISCRETE
markets (anytime TD, 2+ pass TD, longest reception) right, none of which a single
Gaussian can.

Generative model (per simulated game):
  Counts (attempts / carries / targets) ~ Negative Binomial, parameterised by a
    mean and a variance-to-mean ratio (VMR > 1 = overdispersed; NFL volume swings
    game to game with script/pace). NB is sampled as a Gamma-Poisson mixture:
      lam ~ Gamma(shape=r, scale=mean/r),  count ~ Poisson(lam),  r = mean/(VMR-1)
    so E=mean, Var=mean*VMR exactly.
  Completions / catches ~ Binomial(attempts, completion_rate).
  Per-event yards ~ Gamma(mean, CV). Gamma is the standard right-skewed
    nonnegative yardage model; the sum of N of them is the yardage total and the
    MAX is the "longest" market. Rushing allows a small negative (TFL) via a shift.
  Touchdowns / interceptions ~ Poisson(per-game rate).

Everything is pure-Python + seedable, so a backtest is reproducible. See
nfl_simulator_backtest.py for the walk-forward calibration vs the Normal baseline.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

N_SIMS_DEFAULT = 10000

# Variance-to-mean ratios + per-event coefficients of variation. CALIBRATED to
# 2025 NFL game-log dispersion via nfl_simulator_backtest.py so the simulated SD
# matches the player's empirical game-to-game SD (ratio ~1.0). Refreshed in-season.
VMR_ATT = 1.45       # pass attempts game-to-game overdispersion
VMR_CARRIES = 1.35
VMR_TARGETS = 1.22
CV_PASS_YDS_PER_CMP = 0.88   # a single completion is highly variable (screens .. bombs)
CV_RUSH_PER_CARRY = 0.95     # carries are heavy-tailed (stuffs .. breakaways)
CV_REC_PER_CATCH = 0.75
RUSH_SHIFT = 2.5             # carries can lose yards: yards = Gamma(mean+shift) - shift


def _poisson(lam: float, rng: random.Random) -> int:
    """Knuth's Poisson sampler."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def _negbin(mean: float, vmr: float, rng: random.Random) -> int:
    """Negative Binomial via Gamma-Poisson: E=mean, Var=mean*vmr."""
    if mean <= 0:
        return 0
    if vmr <= 1.0:
        return _poisson(mean, rng)
    r = mean / (vmr - 1.0)              # NB "size"
    lam = rng.gammavariate(r, mean / r)  # Gamma(shape=r, scale=mean/r) -> E=mean
    return _poisson(lam, rng)


def _gamma_mean_cv(mean: float, cv: float, rng: random.Random) -> float:
    """Gamma draw with a target mean and coefficient of variation."""
    if mean <= 0:
        return 0.0
    shape = 1.0 / (cv * cv)
    scale = mean * cv * cv
    return rng.gammavariate(shape, scale)


# ---------------------------------------------------------------------------
def simulate_qb(p: Dict[str, float], n: int = N_SIMS_DEFAULT, seed: Optional[int] = 0) -> Dict[str, List[float]]:
    """p: att, comp_pct, ypc (yards per completion), pass_td_pg, int_pg."""
    rng = random.Random(seed)
    att_m = p.get("att", 33.0)
    cpct = min(0.85, max(0.45, p.get("comp_pct", 0.65)))
    ypc = p.get("ypc", 11.5)
    pass_yds, pass_cmp, pass_att, pass_td, pass_int, longest = [], [], [], [], [], []
    for _ in range(n):
        a = max(1, _negbin(att_m, VMR_ATT, rng))
        c = sum(1 for _ in range(a) if rng.random() < cpct)
        tot, lng = 0.0, 0.0
        for _ in range(c):
            y = _gamma_mean_cv(ypc, CV_PASS_YDS_PER_CMP, rng)
            tot += y
            if y > lng:
                lng = y
        pass_att.append(a); pass_cmp.append(c); pass_yds.append(tot); longest.append(lng)
        pass_td.append(_poisson(p.get("pass_td_pg", 1.6), rng))
        pass_int.append(_poisson(p.get("int_pg", 0.7), rng))
    return {"pass_yds": pass_yds, "pass_att": pass_att, "pass_cmp": pass_cmp,
            "pass_td": pass_td, "pass_int": pass_int, "longest_completion": longest}


def simulate_rusher(p: Dict[str, float], n: int = N_SIMS_DEFAULT, seed: Optional[int] = 0) -> Dict[str, List[float]]:
    """p: carries, ypc_rush (yards per carry), rush_td_pg [+ optional receiving]."""
    rng = random.Random(seed)
    car_m = p.get("carries", 14.0)
    ypc = p.get("ypc_rush", 4.3)
    rush_yds, rush_att, rush_td, longest = [], [], [], []
    for _ in range(n):
        a = max(1, _negbin(car_m, VMR_CARRIES, rng))
        tot, lng = 0.0, -99.0
        for _ in range(a):
            y = _gamma_mean_cv(ypc + RUSH_SHIFT, CV_RUSH_PER_CARRY, rng) - RUSH_SHIFT
            y = max(-8.0, y)
            tot += y
            if y > lng:
                lng = y
        rush_att.append(a); rush_yds.append(tot); longest.append(lng)
        rush_td.append(_poisson(p.get("rush_td_pg", 0.4), rng))
    return {"rush_yds": rush_yds, "rush_att": rush_att, "rush_td": rush_td,
            "longest_rush": longest}


def simulate_receiver(p: Dict[str, float], n: int = N_SIMS_DEFAULT, seed: Optional[int] = 0) -> Dict[str, List[float]]:
    """p: targets, catch_rate, ypr (yards per reception), rec_td_pg."""
    rng = random.Random(seed)
    tgt_m = p.get("targets", 7.0)
    crate = min(0.95, max(0.4, p.get("catch_rate", 0.65)))
    ypr = p.get("ypr", 12.0)
    rtd_pg = p.get("rec_td_pg", 0.4)
    rec, rec_yds, longest, rec_td = [], [], [], []
    for _ in range(n):
        t = max(0, _negbin(tgt_m, VMR_TARGETS, rng))
        c = sum(1 for _ in range(t) if rng.random() < crate)
        tot, lng = 0.0, 0.0
        for _ in range(c):
            y = _gamma_mean_cv(ypr, CV_REC_PER_CATCH, rng)
            tot += y
            if y > lng:
                lng = y
        rec.append(c); rec_yds.append(tot); longest.append(lng)
        rec_td.append(_poisson(rtd_pg, rng))   # share the loop rng (NOT a fresh seed per draw)
    return {"rec": rec, "rec_yds": rec_yds, "longest_reception": longest,
            "rec_td": rec_td}


# ---------------------------------------------------------------------------
def prob_over(samples: List[float], line: float) -> float:
    """P(stat > line) from the simulated distribution (pushes split out)."""
    n = len(samples)
    if not n:
        return 0.5
    over = sum(1 for s in samples if s > line)
    return over / n


def prob_at_least(samples: List[float], k: float) -> float:
    return sum(1 for s in samples if s >= k) / max(1, len(samples))


def quantiles(samples: List[float], qs=(0.1, 0.25, 0.5, 0.75, 0.9)) -> Dict[str, float]:
    if not samples:
        return {}
    s = sorted(samples)
    out = {}
    for q in qs:
        i = min(len(s) - 1, int(q * len(s)))
        out[f"p{int(q*100)}"] = round(s[i], 1)
    return out


def summarize(samples: List[float]) -> Dict[str, Any]:
    n = len(samples) or 1
    mean = sum(samples) / n
    var = sum((x - mean) ** 2 for x in samples) / n
    return {"mean": round(mean, 2), "sd": round(var ** 0.5, 2), **quantiles(samples)}


if __name__ == "__main__":
    # Sanity demo: a workhorse QB.
    qb = {"att": 34, "comp_pct": 0.66, "ypc": 11.8, "pass_td_pg": 1.9, "int_pg": 0.7}
    sim = simulate_qb(qb, n=20000)
    print("QB pass_yds:", summarize(sim["pass_yds"]))
    print("  P(over 274.5) =", round(prob_over(sim["pass_yds"], 274.5), 3))
    print("  P(2+ pass TD) =", round(prob_at_least(sim["pass_td"], 2), 3))
    print("  longest completion:", summarize(sim["longest_completion"]))
