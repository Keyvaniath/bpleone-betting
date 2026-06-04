"""
EdgeStat -- NFL Monte Carlo simulator backtest + audit.

Walk-forward (leave-one-out) calibration of nfl_simulator against the normal-CDF
baseline it replaces, on REAL 2025 NFL game logs.

Protocol (no look-ahead):
  For each player with >= MIN_GAMES games, hold out one game at a time. Build the
  player's profile from the OTHER games only, simulate that profile, and for a
  grid of lines around the projection score P(over line) two ways:
    MC   -> share of simulated games over the line
    Norm -> 1 - Phi((line - mean) / sigma), sigma = the current model's cv-sigma
  The outcome is whether the held-out REAL stat cleared the line. Pool the
  (prob, outcome) pairs per market and score calibration:
    Brier (mean squared error), LogLoss, ECE (10-bin expected calibration error),
    and a reliability table. Lower Brier / LogLoss / ECE = better calibrated.

Also reports spread calibration: simulated SD vs the player's empirical
game-to-game SD (does the model disperse like reality?).

Run: python nfl_simulator_backtest.py   (needs data/nfl_player_gamelogs.json)
"""
from __future__ import annotations

import os
import json
import math
from typing import Any, Dict, List, Tuple

import nfl_simulator as S

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MIN_GAMES = 4
N_SIMS = 4000           # per held-out game (speed/precision tradeoff for the backtest)
LINE_OFFSETS = (-1.2, -0.6, 0.0, 0.6, 1.2)   # in units of the normal sigma


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0:
        return 1.0 if mean > line else 0.0
    return 1.0 - _norm_cdf((line - mean) / sigma)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


# Each market: gamelog field, role builder, normal-sigma (floor, cv) from the
# current nfl_player_props model.
SIGMA = {"pass_yds": (45.0, 0.28), "rush_yds": (18.0, 0.45),
         "rec_yds": (18.0, 0.55), "rec": (1.4, 0.35)}


def _profile_qb(games):
    att = _mean([g.get("pass_att") for g in games if g.get("pass_att")])
    cmp_tot = sum(g.get("pass_cmp") or 0 for g in games)
    att_tot = sum(g.get("pass_att") or 0 for g in games)
    yds_tot = sum(g.get("pass_yds") or 0 for g in games)
    comp_pct = (cmp_tot / att_tot) if att_tot else 0.62
    ypc = (yds_tot / cmp_tot) if cmp_tot else 11.5
    return {"att": att or 32, "comp_pct": comp_pct, "ypc": ypc,
            "pass_td_pg": _mean([g.get("pass_td") for g in games]),
            "int_pg": _mean([g.get("pass_int") for g in games])}


def _profile_rb(games):
    car_tot = sum(g.get("rush_att") or 0 for g in games)
    yds_tot = sum(g.get("rush_yds") or 0 for g in games)
    return {"carries": _mean([g.get("rush_att") for g in games if g.get("rush_att")]) or 10,
            "ypc_rush": (yds_tot / car_tot) if car_tot else 4.2,
            "rush_td_pg": _mean([g.get("rush_td") for g in games])}


def _profile_wr(games):
    tgt = _mean([g.get("targets") for g in games if g.get("targets")])
    rec_tot = sum(g.get("rec") or 0 for g in games)
    tgt_tot = sum(g.get("targets") or 0 for g in games)
    yds_tot = sum(g.get("rec_yds") or 0 for g in games)
    return {"targets": tgt or 5, "catch_rate": (rec_tot / tgt_tot) if tgt_tot else 0.65,
            "ypr": (yds_tot / rec_tot) if rec_tot else 11.5,
            "rec_td_pg": _mean([g.get("rec_td") for g in games])}


def _sim_field(profile, role, field, seed):
    if role == "qb":
        return S.simulate_qb(profile, n=N_SIMS, seed=seed)[field]
    if role == "rb":
        return S.simulate_rusher(profile, n=N_SIMS, seed=seed)[field]
    return S.simulate_receiver(profile, n=N_SIMS, seed=seed)[field]


MARKETS = [
    ("pass_yds", "qb", _profile_qb),
    ("rush_yds", "rb", _profile_rb),
    ("rec_yds", "wr", _profile_wr),
    ("rec", "wr", _profile_wr),
]


def _metrics(pairs: List[Tuple[float, float]]):
    if not pairs:
        return None
    n = len(pairs)
    brier = sum((p - a) ** 2 for p, a in pairs) / n
    ll = -sum(a * math.log(min(max(p, 1e-6), 1 - 1e-6)) +
              (1 - a) * math.log(min(max(1 - p, 1e-6), 1 - 1e-6)) for p, a in pairs) / n
    # 10-bin ECE
    bins = [[] for _ in range(10)]
    for p, a in pairs:
        bins[min(9, int(p * 10))].append((p, a))
    ece = sum((len(b) / n) * abs(_mean([p for p, _ in b]) - _mean([a for _, a in b]))
              for b in bins if b)
    return {"n": n, "brier": round(brier, 4), "logloss": round(ll, 4), "ece": round(ece, 4)}


def run():
    gl = json.load(open(os.path.join(DATA_DIR, "nfl_player_gamelogs.json"))).get("by_name") or {}
    mc_pairs: Dict[str, list] = {}
    nm_pairs: Dict[str, list] = {}
    spread: Dict[str, list] = {}      # market -> [(mc_sd, emp_sd)]
    seed = 1
    for name, prec in gl.items():
        all_games = prec.get("games") or []
        for field, role, builder in MARKETS:
            games = [g for g in all_games if g.get(field) is not None]
            if len(games) < MIN_GAMES:
                continue
            emp_sd = _sd([g.get(field) for g in games])
            for i in range(len(games)):
                others = games[:i] + games[i + 1:]
                actualv = games[i].get(field)
                prof = builder(others)
                seed += 1
                samples = _sim_field(prof, role, field, seed)
                if not samples:
                    continue
                mc_mean, mc_sd = _mean(samples), _sd(samples)
                spread.setdefault(field, []).append((mc_sd, emp_sd))
                floor, cv = SIGMA[field]
                sigma = max(floor, cv * mc_mean)
                for off in LINE_OFFSETS:
                    line = mc_mean + off * sigma
                    if line < 0:
                        continue
                    a = 1.0 if actualv > line else 0.0
                    mc_pairs.setdefault(field, []).append((S.prob_over(samples, line), a))
                    nm_pairs.setdefault(field, []).append((_normal_p_over(mc_mean, sigma, line), a))

    print("=" * 72)
    print("NFL MONTE CARLO SIMULATOR -- BACKTEST vs NORMAL-CDF (2025 game logs)")
    print("=" * 72)
    print(f"{'market':10} {'n':>6} | {'MC brier':>9} {'Nm brier':>9} | {'MC ll':>7} {'Nm ll':>7} | {'MC ece':>7} {'Nm ece':>7} | winner")
    agg_mc = {"brier": 0.0, "logloss": 0.0, "ece": 0.0, "n": 0}
    agg_nm = {"brier": 0.0, "logloss": 0.0, "ece": 0.0, "n": 0}
    for field, _, _ in MARKETS:
        m = _metrics(mc_pairs.get(field, []))
        nmt = _metrics(nm_pairs.get(field, []))
        if not m:
            continue
        win = "MC" if m["brier"] < nmt["brier"] else "Norm"
        print(f"{field:10} {m['n']:>6} | {m['brier']:>9} {nmt['brier']:>9} | "
              f"{m['logloss']:>7} {nmt['logloss']:>7} | {m['ece']:>7} {nmt['ece']:>7} | {win}")
        for k in ("brier", "logloss", "ece"):
            agg_mc[k] += m[k] * m["n"]; agg_nm[k] += nmt[k] * nmt["n"]
        agg_mc["n"] += m["n"]; agg_nm["n"] += nmt["n"]
    if agg_mc["n"]:
        print("-" * 72)
        print(f"{'POOLED':10} {agg_mc['n']:>6} | "
              f"{agg_mc['brier']/agg_mc['n']:>9.4f} {agg_nm['brier']/agg_nm['n']:>9.4f} | "
              f"{agg_mc['logloss']/agg_mc['n']:>7.4f} {agg_nm['logloss']/agg_nm['n']:>7.4f} | "
              f"{agg_mc['ece']/agg_mc['n']:>7.4f} {agg_nm['ece']/agg_nm['n']:>7.4f} |")
    print("\nSPREAD CALIBRATION (simulated SD vs empirical game-to-game SD):")
    for field, _, _ in MARKETS:
        sp = spread.get(field, [])
        if sp:
            msd = _mean([a for a, _ in sp]); esd = _mean([b for _, b in sp])
            print(f"  {field:10} sim_sd={msd:6.1f}  emp_sd={esd:6.1f}  ratio={msd/esd:.2f}"
                  + ("  <-- over-disperses" if msd > 1.15 * esd else
                     "  <-- under-disperses" if msd < 0.85 * esd else "  OK"))
    return {"mc": mc_pairs, "nm": nm_pairs, "spread": spread}


if __name__ == "__main__":
    run()
