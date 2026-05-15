"""
EdgeStat -- model confidence scoring.

Aggregates per-market calibration + residuals into a single overall
"how trustworthy is the model right now?" score (0-100). Surfaces on the
dashboard so the user can see at a glance whether the model is ready to
size real bets vs still in warmup.

Components (each 0-1, weighted):
  1. CALIBRATION QUALITY (40%): inverse Brier across all markets. Brier
     0.25 = baseline (coin flip), 0.18 = strong. We map 0.25 -> 0, 0.10 -> 1.
  2. SAMPLE SUFFICIENCY (25%): how much we trust the empirical bias.
     Avg data_weight across markets. 0.5 -> 0.5, 0.99 -> 0.99.
  3. RESIDUAL STABILITY (20%): inverse of (mean |mean_residual| / market
     std). Lower is better. 1.0 -> 0, 0.2 -> 1.
  4. ROI POSITIVITY (15%): fraction of markets with positive ROI in the
     trailing window. 0.5 -> 0.5, 1.0 -> 1.

The result is mapped to a "training status" label:
   85-100  PRODUCTION-READY  (Kelly sizing OK)
   70-84   GREEN-LIGHT       (capped Kelly, watching residuals)
   50-69   YELLOW            (still learning; small flat plays only)
   <50     RED               (calibration still warming; research signal only)
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")
RES_PATH = os.path.join(DATA_DIR, "residuals.json")
OUT_PATH = os.path.join(DATA_DIR, "model_confidence.json")


def _safe_load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def run() -> Dict[str, Any]:
    cal = _safe_load(CAL_PATH)
    res = _safe_load(RES_PATH)
    markets = cal.get("markets") or {}
    res_markets = res.get("markets") or {}

    # 1. Calibration quality: inverse Brier across all markets
    briers = [m.get("brier") for m in markets.values() if m.get("brier") is not None]
    avg_brier = sum(briers) / len(briers) if briers else None
    if avg_brier is None:
        cal_quality = 0.0
    else:
        # 0.25 -> 0, 0.10 -> 1
        cal_quality = _clamp((0.25 - avg_brier) / 0.15)

    # 2. Sample sufficiency: avg data_weight
    weights = [m.get("data_weight") for m in markets.values() if m.get("data_weight") is not None]
    avg_weight = sum(weights) / len(weights) if weights else 0.0
    sample_suff = _clamp(avg_weight)

    # 3. Residual stability: how close is each market's mean residual to 0?
    stabilities = []
    for mk, m in res_markets.items():
        mean = abs(m.get("mean_residual") or 0)
        std = (m.get("std_residual") or 1e-6)
        # Normalized: ratio of |mean| to std; 0 = perfectly centered, 1 = mean is one std off
        ratio = mean / max(std, 1e-6)
        stabilities.append(1.0 - _clamp(ratio))
    residual_stab = sum(stabilities) / len(stabilities) if stabilities else 0.0

    # 4. ROI positivity: fraction of markets with ROI > 0
    rois = [m.get("roi_pct") for m in markets.values() if m.get("roi_pct") is not None and m.get("plays_n", 0) > 0]
    if not rois:
        roi_pos = 0.5  # neutral when no ROI signal yet
    else:
        positive = sum(1 for r in rois if r > 0)
        roi_pos = positive / len(rois)

    components = {
        "calibration_quality": round(cal_quality, 3),
        "sample_sufficiency": round(sample_suff, 3),
        "residual_stability": round(residual_stab, 3),
        "roi_positivity":     round(roi_pos, 3),
    }
    weights_w = {"calibration_quality": 0.40, "sample_sufficiency": 0.25,
                 "residual_stability": 0.20, "roi_positivity": 0.15}
    score = sum(components[k] * weights_w[k] for k in components) * 100

    if score >= 85:
        tier = "production-ready"
        message = "Calibration tight, sample deep, residuals stable. Kelly sizing OK; production betting unlocked."
    elif score >= 70:
        tier = "green-light"
        message = "Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further."
    elif score >= 50:
        tier = "yellow"
        message = "Still learning. Small flat plays only; treat anything >+10% edge as suspect."
    else:
        tier = "red"
        message = "Calibration warming up. Research signal only; no real-money sizing yet."

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "score": round(score, 1),
        "tier": tier,
        "message": message,
        "components": components,
        "weights": weights_w,
        "diagnostics": {
            "n_markets_calibrated": len(markets),
            "avg_brier": round(avg_brier, 4) if avg_brier is not None else None,
            "avg_data_weight": round(avg_weight, 3),
            "n_markets_positive_roi": sum(1 for r in rois if r > 0),
            "n_markets_with_roi": len(rois),
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Model Confidence: {p['score']}/100  [{p['tier'].upper()}]")
    print(f"  {p['message']}")
    print()
    for k, v in p["components"].items():
        w = p["weights"][k]
        print(f"  {k:25} {v:.3f}  (weight {w})")
    print()
    print(f"  diagnostics: {p['diagnostics']}")
