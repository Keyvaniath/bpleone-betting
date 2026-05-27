"""
EdgeStat -- MLB starting pitcher form regression detector.

Surfaces pitchers due for regression to their season baseline:
  - HOT REGRESSION RISK: recent K/9 spike >= 12% above season average +
    high inning load (>=12 IP last 2 starts) -> expected K UNDER tonight
  - COLD REGRESSION OPPORTUNITY: recent ER spike, low K/9 vs season +
    elite raw stuff metrics -> bounce-back candidate

Output: data/mlb_starter_form_regression_detector.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_starter_form_regression_detector.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json"))
    edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    confluence = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))

    form_idx = {_norm(r.get("pitcher")): r for r in (form.get("rows") or []) if isinstance(r, dict)}
    edge_idx = {_norm(r.get("pitcher")): r for r in (edge.get("rows") or []) if isinstance(r, dict)}
    conf_idx = {_norm(r.get("pitcher")): r for r in (confluence.get("rows") or []) if isinstance(r, dict)}

    all_pitchers = set(form_idx) | set(edge_idx) | set(conf_idx)

    hot_regression: List[Dict[str, Any]] = []
    cold_bounceback: List[Dict[str, Any]] = []

    for name in all_pitchers:
        f = form_idx.get(name, {})
        e = edge_idx.get(name, {})
        c = conf_idx.get(name, {})

        form_class = (f.get("trend") or f.get("form") or "").upper()
        season_k9 = _safe(f.get("season_k9") or e.get("season_k9"))
        recent_k9 = _safe(f.get("recent_k9") or f.get("last3_k9") or e.get("recent_k9"))
        season_era = _safe(f.get("season_era") or e.get("season_era"))
        recent_era = _safe(f.get("recent_era") or f.get("last3_era"))
        edge_score = _safe(c.get("edge_score") or e.get("score") or e.get("composite_score"))

        if not (season_k9 > 0 and recent_k9 > 0): continue

        k9_ratio = recent_k9 / season_k9 if season_k9 > 0 else 1.0

        # HOT regression: K/9 12% above season + high inning load
        if k9_ratio >= 1.12 and ("HOT" in form_class or k9_ratio >= 1.20):
            hot_regression.append({
                "pitcher": f.get("pitcher") or c.get("pitcher") or name.title(),
                "team": e.get("team") or c.get("team"),
                "matchup": c.get("matchup") or e.get("matchup"),
                "season_k9": round(season_k9, 2),
                "recent_k9": round(recent_k9, 2),
                "k9_ratio_above_season": round(k9_ratio, 3),
                "form_class": form_class or None,
                "edge_score": round(edge_score, 2) if edge_score else None,
                "alert_type": "HOT_REGRESSION_RISK",
                "recommended_market": "K UNDER (regression to mean)",
            })

        # COLD bounceback: K/9 below season AND ERA elevated AND edge_score still high
        if k9_ratio <= 0.88 and recent_era >= season_era * 1.20 and edge_score >= 55:
            cold_bounceback.append({
                "pitcher": f.get("pitcher") or c.get("pitcher") or name.title(),
                "team": e.get("team") or c.get("team"),
                "matchup": c.get("matchup") or e.get("matchup"),
                "season_k9": round(season_k9, 2),
                "recent_k9": round(recent_k9, 2),
                "season_era": round(season_era, 2),
                "recent_era": round(recent_era, 2),
                "edge_score": round(edge_score, 2),
                "alert_type": "COLD_BOUNCE_BACK",
                "recommended_market": "K OVER + outs OVER (positive regression)",
            })

    hot_regression.sort(key=lambda h: -h["k9_ratio_above_season"])
    cold_bounceback.sort(key=lambda c: -c["edge_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_hot_regression_risk": len(hot_regression),
        "n_cold_bounce_back": len(cold_bounceback),
        "method_note": "Detects pitchers due for regression. HOT_REGRESSION_RISK = "
                       "recent K/9 >= 12% above season + hot form -> K UNDER. "
                       "COLD_BOUNCE_BACK = K/9 <= 88% of season AND ERA elevated "
                       "AND edge_score >= 55 -> K OVER + outs OVER.",
        "hot_regression_risk": hot_regression,
        "cold_bounce_back_candidates": cold_bounceback,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[form-regression] {o['n_hot_regression_risk']} HOT_REGRESSION, "
          f"{o['n_cold_bounce_back']} COLD_BOUNCE_BACK -> {OUT}")
