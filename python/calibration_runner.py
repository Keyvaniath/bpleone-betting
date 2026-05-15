"""
EdgeStat -- calibration runner.

Reads data/track_record.json (the growing settled-bets log), computes per-market
calibration metrics on the trailing 30 days, and writes data/calibration_live.json
that pipeline.py and props_pipeline.py read to apply corrections to tomorrow's
projections.

Metrics:
  - hit_rate: actual hit rate of OVER plays
  - implied_hit_rate: weighted avg model probability assigned to OVER
  - bias: implied / actual -- multiplicative correction to apply going forward
  - brier: mean squared error between model_prob and outcome
  - log_loss: cross-entropy
  - ece: expected calibration error (bin-based)
  - roi: simple ROI from following the model's plays
  - sample_n: how many settled records contributed

The "bias" correction is applied as a multiplicative scaling of the next day's
model probabilities. If the model has been overstating Ks Overs by 10%, we
shrink tomorrow's Over probs by 1/1.10.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")

LOOKBACK_DAYS = 30
# Old behavior was a hard cutoff: zero correction below n=30, then full bias
# correction once you crossed. That meant the first 29 settled outcomes literally
# could not move the model -- a multi-week wasted-learning window.
#
# New behavior: Bayesian shrinkage with an n_prior anchor of N_PRIOR=30.
#   effective_cf = (n / (n + N_PRIOR)) * raw_cf + (N_PRIOR / (n + N_PRIOR)) * 1.0
# So at n=0 the correction is exactly 1.0 (trust prior, no change), and as n
# grows the model trusts the empirical bias more. By n=30 we're 50/50, by
# n=120 we're 80/20 toward the data. No more hard cutoff.
N_PRIOR = 30                     # how strongly to anchor toward "no correction" (1.0)
MIN_SAMPLE_FOR_ANY_CORRECTION = 3  # below this, still bypass entirely (too noisy)
MAX_CORRECTION = 1.25            # cap correction at ±25% to avoid runaway adjustment
MIN_CORRECTION = 1.0 / 1.25


def _within_window(date_str: str, today: dt.date, n_days: int) -> bool:
    try:
        d = dt.date.fromisoformat(date_str)
        return (today - d).days <= n_days
    except Exception:
        return False


def compute_metrics(records: List[Dict[str, Any]], today: Optional[dt.date] = None) -> Dict[str, Any]:
    """Brier, log loss, ECE, hit rate, ROI on a list of settled OVER-side projections."""
    today = today or dt.date.today()
    sample = [r for r in records if r.get("date") and _within_window(r["date"], today, LOOKBACK_DAYS)
              and r.get("model_prob_over") is not None]
    n = len(sample)
    if n == 0:
        return {"n": 0}

    # Brier / log loss on model_prob_over vs over_hit
    brier = 0.0
    ll = 0.0
    eps = 1e-9
    sum_p, sum_actual = 0.0, 0.0
    bins: List[List[Tuple[float, int]]] = [[] for _ in range(10)]
    for r in sample:
        p = float(r["model_prob_over"])
        y = 1 if r.get("over_hit") else 0
        brier += (p - y) ** 2
        ll += -(y * math.log(max(eps, p)) + (1 - y) * math.log(max(eps, 1 - p)))
        sum_p += p
        sum_actual += y
        bins[min(9, int(p * 10))].append((p, y))
    brier /= n
    ll /= n
    implied_rate = sum_p / n
    actual_rate = sum_actual / n
    # Bias = (implied OVER rate) / (actual OVER rate). On thin samples
    # actual_rate can be 0 (every OVER missed) or 1 (every OVER hit), which
    # would divide by zero / give infinite bias. Use add-one Laplace smoothing
    # against a 50/50 prior so the bias is well-defined and bounded:
    #
    #   smoothed_bias = (sum_p + 0.5) / (sum_actual + 0.5)
    #
    # Example: 4 props, sum_p=2.09 (avg 0.52), sum_actual=0 (all missed)
    #   raw: undefined; smoothed: 2.59/0.5 = 5.18 -> capped to MAX_CORRECTION
    # Example: 4 props, sum_p=2.09, sum_actual=4 (all hit)
    #   raw: 0.52; smoothed: 2.59/4.5 = 0.576 -> shrink OVER (model underconfident)
    bias = (sum_p + 0.5) / (sum_actual + 0.5)
    # ECE
    ece = 0.0
    for b in bins:
        if not b:
            continue
        bp = sum(p for p, _ in b) / len(b)
        by = sum(y for _, y in b) / len(b)
        ece += (len(b) / n) * abs(bp - by)
    # ROI of model's plays (OVER/UNDER), assumes American odds payouts
    roi_stake = 0.0
    roi_pl = 0.0
    plays_won = plays_lost = 0
    for r in sample:
        play = r.get("play")
        if play not in ("OVER", "UNDER"):
            continue
        hit = r.get("play_hit")
        if hit is None:
            continue
        price = r.get(f"dk_{play.lower()}")
        if price is None:
            continue
        # Stake $1 unit each
        roi_stake += 1.0
        if hit:
            # Payout = decimal * stake - stake (= profit per $1 stake)
            payout = (price / 100.0) if price >= 0 else (100.0 / -price)
            roi_pl += payout
            plays_won += 1
        else:
            roi_pl -= 1.0
            plays_lost += 1
    roi_pct = (roi_pl / roi_stake * 100.0) if roi_stake > 0 else 0.0

    # Per-projection RMSE: how far is the model's expected stat value from actual?
    proj_samples = [r for r in sample
                    if r.get("model_projection") is not None and r.get("actual") is not None]
    rmse = None
    if proj_samples:
        sq = sum((r["actual"] - r["model_projection"]) ** 2 for r in proj_samples)
        rmse = round((sq / len(proj_samples)) ** 0.5, 3)
    return {
        "n": n,
        "n_with_projection": len(proj_samples),
        "implied_over_rate": round(implied_rate, 4),
        "actual_over_rate": round(actual_rate, 4),
        "bias": round(bias, 4),
        "brier": round(brier, 4),
        "log_loss": round(ll, 4),
        "ece": round(ece, 4),
        "rmse": rmse,
        "plays_n": plays_won + plays_lost,
        "plays_won": plays_won,
        "plays_lost": plays_lost,
        "roi_pct": round(roi_pct, 2),
    }


def correction_factor(metrics: Dict[str, Any]) -> float:
    """Translate bias into a multiplicative correction with Bayesian shrinkage.

    Shrinkage formula:
        effective_cf = (n / (n + N_PRIOR)) * raw_cf + (N_PRIOR / (n + N_PRIOR)) * 1.0

    - n=0 or n<MIN_SAMPLE_FOR_ANY_CORRECTION -> 1.0 (no change, trust prior)
    - n=N_PRIOR -> half data, half prior
    - n>>N_PRIOR -> mostly trust empirical bias
    - raw_cf is still capped to [MIN_CORRECTION, MAX_CORRECTION] BEFORE shrinkage
      so a thin-sample outlier can't drive the shrunk correction past the cap.
    """
    n = metrics.get("n", 0)
    if n < MIN_SAMPLE_FOR_ANY_CORRECTION:
        return 1.0
    bias = metrics.get("bias", 1.0)
    if not bias or bias <= 0:
        return 1.0
    raw_cf = max(MIN_CORRECTION, min(MAX_CORRECTION, 1.0 / bias))
    w = n / (n + N_PRIOR)
    shrunk = w * raw_cf + (1.0 - w) * 1.0
    return round(shrunk, 4)


def run(today: Optional[dt.date] = None) -> Dict[str, Any]:
    today = today or dt.date.today()
    if not os.path.exists(TR_PATH):
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "warning": "no track_record.json yet",
                   "markets": {}, "games_overall": {}}
        _write(payload)
        return payload

    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props", [])
    games = tr.get("games", [])

    # Per-market metrics for props
    markets: Dict[str, Any] = {}
    for market_key in {r.get("market") for r in props if r.get("market")}:
        subset = [r for r in props if r.get("market") == market_key]
        m = compute_metrics(subset, today)
        m["correction_factor"] = correction_factor(m)
        # Make the shrinkage transparent: how much of the raw bias is we trusting?
        n = m.get("n", 0)
        m["data_weight"] = round(n / (n + N_PRIOR), 4) if n > 0 else 0.0
        m["raw_correction"] = round(max(MIN_CORRECTION, min(MAX_CORRECTION, 1.0 / m.get("bias", 1.0))), 4) if m.get("bias") else 1.0
        markets[market_key] = m

    # Game-line over/under metrics
    # Adapter: shape game records like props for compute_metrics
    game_for_metrics = []
    for g in games:
        if g.get("model_p_over_market") is None or g.get("over_hit") is None:
            continue
        game_for_metrics.append({
            "date": g.get("date"),
            "model_prob_over": g["model_p_over_market"],
            "over_hit": g["over_hit"],
            "play": None, "play_hit": None,
            "dk_over": None, "dk_under": None,
        })
    games_overall = compute_metrics(game_for_metrics, today)
    games_overall["correction_factor"] = correction_factor(games_overall)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "lookback_days": LOOKBACK_DAYS,
        "shrinkage_n_prior": N_PRIOR,
        "shrinkage_min_n": MIN_SAMPLE_FOR_ANY_CORRECTION,
        "shrinkage_note": (
            f"Per-market correction = data_weight * raw_correction + (1 - data_weight) * 1.0; "
            f"data_weight = n / (n + {N_PRIOR}). Below n={MIN_SAMPLE_FOR_ANY_CORRECTION} the factor is forced to 1.0. "
            f"Caps at +/- 25%."
        ),
        "markets": markets,
        "games_overall": games_overall,
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CAL_PATH, "w") as f:
        json.dump(payload, f, indent=2)


def load_corrections() -> Dict[str, float]:
    """Return {market_key: correction_factor} dict for next-day projections."""
    if not os.path.exists(CAL_PATH):
        return {}
    try:
        with open(CAL_PATH) as f:
            p = json.load(f)
    except Exception:
        return {}
    out: Dict[str, float] = {}
    for k, v in (p.get("markets") or {}).items():
        cf = v.get("correction_factor")
        if cf is not None:
            out[k] = cf
    return out


if __name__ == "__main__":
    p = run()
    print(f"Wrote {CAL_PATH}")
    print(f"  Markets calibrated: {len(p.get('markets', {}))}")
    for k, v in p.get("markets", {}).items():
        print(f"    {k}: n={v.get('n')}, bias={v.get('bias')}, "
              f"correction_factor={v.get('correction_factor')}, "
              f"ROI={v.get('roi_pct')}%, ECE={v.get('ece')}")
    g = p.get("games_overall") or {}
    if g.get("n"):
        print(f"  Games overall: n={g['n']}, bias={g.get('bias')}, ECE={g.get('ece')}")
