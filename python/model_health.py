"""
EdgeStat -- single-number model health score.

Aggregates every quality signal into one 0-100 score Brandon can glance at:
  - Calibration freshness (how recent is self_training?)
  - Calibration applied count (how many sports have learned shifts?)
  - Hit rate trend (60-day rolling, are we improving?)
  - Brier trend (lower is better)
  - Pipeline audit status (green/yellow/red ratio)
  - Data health (live source matches)
  - Active picks count (model is finding edges)

Output: data/model_health.json + console one-liner.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "model_health.json")


def _load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _score_calibration_freshness() -> Dict[str, Any]:
    """How fresh are the self_training files (should be < 24h)."""
    sports = ["nba", "nhl", "wnba", "mls", "epl", "mlb", "cws"]
    ages = []
    n_applied = 0
    for s in sports:
        path = os.path.join(DATA_DIR, f"self_training_{s}.json")
        if not os.path.exists(path): continue
        age_h = (dt.datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        ages.append(age_h)
        try:
            d = json.load(open(path))
            if d.get("recommendation", {}).get("applied"): n_applied += 1
        except Exception: pass
    if not ages: return {"score": 0, "n_sports": 0, "avg_age_h": None, "n_applied": 0}
    avg_age = sum(ages) / len(ages)
    # 100 at age=0, 0 at age=48h
    score = max(0, min(100, 100 - avg_age * 2))
    return {"score": round(score, 1), "n_sports": len(ages),
            "avg_age_h": round(avg_age, 1), "n_applied": n_applied}


def _score_hit_rate_trend() -> Dict[str, Any]:
    """60-day rolling hit rate. >70% = healthy, <55% = unhealthy."""
    d = _load("perf_trend.json")
    by_date = d.get("by_date", [])
    if not by_date: return {"score": 50, "note": "no perf data"}
    recent = by_date[-7:]  # last 7 days
    avg_hr = sum(r["hit_rate"] for r in recent if r.get("hit_rate")) / max(1, len(recent))
    # 100 at 80% hit rate, 0 at 45%
    score = max(0, min(100, (avg_hr - 0.45) / (0.80 - 0.45) * 100))
    return {"score": round(score, 1), "avg_hit_rate_7d": round(avg_hr, 4)}


def _score_brier_trend() -> Dict[str, Any]:
    """Brier score (lower=better). 0.15 = excellent, 0.25 = random."""
    d = _load("perf_trend.json")
    by_date = d.get("by_date", [])
    if not by_date: return {"score": 50, "note": "no perf data"}
    recent = by_date[-7:]
    avg_brier = sum(r["brier"] for r in recent if r.get("brier")) / max(1, len(recent))
    # 100 at brier 0.10, 0 at brier 0.25
    score = max(0, min(100, (0.25 - avg_brier) / (0.25 - 0.10) * 100))
    return {"score": round(score, 1), "avg_brier_7d": round(avg_brier, 4)}


def _score_pipeline_audit() -> Dict[str, Any]:
    """Pipeline audit green/yellow/red counts."""
    d = _load("pipeline_audit.json")
    n_g = d.get("n_green", 0)
    n_y = d.get("n_yellow", 0)
    n_r = d.get("n_red", 0)
    total = n_g + n_y + n_r
    if total == 0: return {"score": 0, "note": "no pipeline audit"}
    # green=1.0, yellow=0.5, red=0
    weighted = n_g + n_y * 0.5
    score = (weighted / total) * 100
    return {"score": round(score, 1), "n_green": n_g, "n_yellow": n_y, "n_red": n_r}


def _score_data_health() -> Dict[str, Any]:
    """Live data accuracy check (data_health.json)."""
    d = _load("data_health.json")
    n_g = d.get("n_green", 0)
    n_y = d.get("n_yellow", 0)
    n_r = d.get("n_red", 0)
    total = n_g + n_y + n_r
    if total == 0: return {"score": 0, "note": "no data_health"}
    weighted = n_g + n_y * 0.5
    score = (weighted / total) * 100
    return {"score": round(score, 1), "n_green": n_g, "n_yellow": n_y, "n_red": n_r}


def _score_edge_count() -> Dict[str, Any]:
    """How many real edges did the model find today?"""
    bb = _load("best_bets.json")
    n_bets = bb.get("n_bets", 0)
    # 100 at >=40 bets, 0 at <=5
    score = max(0, min(100, (n_bets - 5) / (40 - 5) * 100))
    return {"score": round(score, 1), "n_bets": n_bets}


def run() -> Dict[str, Any]:
    components = {
        "calibration_freshness": _score_calibration_freshness(),
        "hit_rate_trend": _score_hit_rate_trend(),
        "brier_trend": _score_brier_trend(),
        "pipeline_audit": _score_pipeline_audit(),
        "data_health": _score_data_health(),
        "edge_count": _score_edge_count(),
    }
    weights = {
        "calibration_freshness": 0.15,
        "hit_rate_trend": 0.20,
        "brier_trend": 0.20,
        "pipeline_audit": 0.15,
        "data_health": 0.20,
        "edge_count": 0.10,
    }
    total_score = sum(components[k]["score"] * weights[k] for k in weights)
    if total_score >= 85: tier = "ELITE"
    elif total_score >= 70: tier = "HEALTHY"
    elif total_score >= 55: tier = "OK"
    elif total_score >= 40: tier = "DEGRADED"
    else: tier = "BROKEN"

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_score": round(total_score, 1),
        "tier": tier,
        "components": components,
        "weights": weights,
        "interpretation": {
            "ELITE": "All systems firing - model fully calibrated, fresh data, finding lots of edges",
            "HEALTHY": "Solid health - some minor issues to monitor",
            "OK": "Operational but room to improve - check yellow components",
            "DEGRADED": "Several components weak - review red items",
            "BROKEN": "Critical issues - manual intervention needed",
        }.get(tier),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Model Health: {p['total_score']:.1f}/100 [{p['tier']}]")
    print(f"  {p['interpretation']}")
    print("  Components:")
    for name, c in p["components"].items():
        weight = p["weights"][name]
        print(f"    {name:25s} {c['score']:5.1f} (weight {weight*100:.0f}%)")
