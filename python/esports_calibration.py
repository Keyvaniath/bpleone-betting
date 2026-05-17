"""
EdgeStat -- self-learning calibration for new sports (LoL, CS, KBO).

For each sport, walks the rolling POT history + ELO-store processed matches
and computes:
  - Reliability bins (do 60% predictions actually win 60% of the time?)
  - Brier score (lower = more accurate)
  - Log loss
  - ECE (Expected Calibration Error)
  - Per-source calibration multiplier (recommendation to shift model output)

Output: data/esports_calibration.json (one block per sport: lol / cs / kbo)
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "esports_calibration.json")

SPORTS = [
    ("lol", "lol_pot_history.json", "lol_state.json", "lol_elo.json"),
    ("cs",  "cs_pot_history.json",  "cs_state.json",  "cs_elo.json"),
    ("kbo", "kbo_pot_history.json", "kbo_state.json", "kbo_elo.json"),
]
N_BINS = 10
MIN_SAMPLE_FOR_RECO = 20    # need 20 settled bets before recommending shift


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _reliability_bins(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For each probability bin, compute predicted vs actual hit rate."""
    bins = [{"low": i / N_BINS, "high": (i + 1) / N_BINS,
             "n": 0, "expected": 0.0, "actual_wins": 0} for i in range(N_BINS)]
    for r in records:
        prob = r.get("prob")
        outcome = r.get("outcome")
        if prob is None or outcome not in ("WIN", "LOSS"):
            continue
        bin_idx = min(int(prob * N_BINS), N_BINS - 1)
        b = bins[bin_idx]
        b["n"] += 1
        b["expected"] += prob
        b["actual_wins"] += 1 if outcome == "WIN" else 0
    for b in bins:
        if b["n"] > 0:
            b["expected_rate"] = round(b["expected"] / b["n"], 4)
            b["actual_rate"] = round(b["actual_wins"] / b["n"], 4)
            b["delta"] = round(b["actual_rate"] - b["expected_rate"], 4)
        else:
            b["expected_rate"] = None
            b["actual_rate"] = None
            b["delta"] = None
    return bins


def _metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Brier score, log loss, ECE."""
    settled = [r for r in records if r.get("outcome") in ("WIN", "LOSS")]
    if not settled:
        return {"n_settled": 0, "brier": None, "log_loss": None, "ece": None}

    brier_sum = 0.0
    ll_sum = 0.0
    for r in settled:
        p = r.get("prob") or 0.5
        actual = 1.0 if r["outcome"] == "WIN" else 0.0
        brier_sum += (p - actual) ** 2
        p_clip = max(1e-6, min(1 - 1e-6, p))
        ll_sum += -(actual * math.log(p_clip) + (1 - actual) * math.log(1 - p_clip))

    n = len(settled)
    brier = brier_sum / n
    log_loss = ll_sum / n

    # ECE = weighted avg of |expected_rate - actual_rate| per bin
    bins = _reliability_bins(records)
    ece = 0.0
    for b in bins:
        if b["n"] > 0 and b["delta"] is not None:
            ece += (b["n"] / n) * abs(b["delta"])

    return {
        "n_settled": n,
        "brier": round(brier, 4),
        "log_loss": round(log_loss, 4),
        "ece": round(ece, 4),
    }


def _recommend_multiplier(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """If model is systematically over- or under-confident, suggest a
    one-shot probability shift to apply at the next inference."""
    settled = [r for r in records if r.get("outcome") in ("WIN", "LOSS")]
    if len(settled) < MIN_SAMPLE_FOR_RECO:
        return {"applied": False, "note": f"need >= {MIN_SAMPLE_FOR_RECO} settled bets (have {len(settled)})"}
    pred_mean = sum(r.get("prob", 0) for r in settled) / len(settled)
    actual_mean = sum(1.0 if r["outcome"] == "WIN" else 0.0 for r in settled) / len(settled)
    shift = actual_mean - pred_mean
    if abs(shift) < 0.02:
        return {"applied": False, "note": "model is well-calibrated (|shift| < 2pp)"}
    return {
        "applied": True,
        "predicted_mean_winprob": round(pred_mean, 4),
        "actual_hit_rate": round(actual_mean, 4),
        "recommended_shift_pp": round(shift * 100, 2),
        "note": ("Model under-confident; add " if shift > 0 else "Model over-confident; subtract ") +
                f"{abs(shift)*100:.1f}pp at next inference",
    }


def run() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sports": {},
    }
    for sport, hist_file, _state, _elo in SPORTS:
        hist = _load(os.path.join(DATA_DIR, hist_file)).get("history") or []
        metrics = _metrics(hist)
        bins = _reliability_bins(hist)
        reco = _recommend_multiplier(hist)
        out["sports"][sport] = {
            "n_total": len(hist),
            **metrics,
            "reliability_bins": [b for b in bins if b["n"] > 0],
            "calibration_recommendation": reco,
        }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    p = run()
    for sport, data in p["sports"].items():
        print(f"  {sport.upper()}: n_settled={data['n_settled']}  brier={data['brier']}  ece={data['ece']}")
        if data.get("calibration_recommendation", {}).get("applied"):
            print(f"    -> {data['calibration_recommendation']['note']}")
