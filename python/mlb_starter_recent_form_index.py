"""
EdgeStat -- MLB starter recent form index.

Composite recent-form score combining last 3-5 starts:
  - Recent K rate vs season baseline
  - Recent ERA vs season baseline
  - Recent walks per IP
  - Trend direction (improving, declining, stable)

Form_index from 0-100:
  >= 75 = ELITE (top form, no regression risk)
  60-74 = STRONG (positive form)
  40-59 = NEUTRAL
  25-39 = WEAK (declining form)
  < 25 = STRUGGLING (avoid)

Output: data/mlb_starter_recent_form_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_starter_recent_form_index.json")


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
    confluence = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))

    form_idx = {_norm(r.get("pitcher")): r
                for r in (form.get("rows") or []) if isinstance(r, dict)}
    conf_idx = {_norm(r.get("pitcher")): r
                for r in (confluence.get("rows") or []) if isinstance(r, dict)}
    edge_idx = {_norm(r.get("pitcher")): r
                for r in (edge.get("rows") or []) if isinstance(r, dict)}

    all_pitchers = set(form_idx) | set(conf_idx)

    rows: List[Dict[str, Any]] = []
    for name in all_pitchers:
        f = form_idx.get(name, {})
        c = conf_idx.get(name, {})
        e = edge_idx.get(name, {})

        season_k9 = _safe(f.get("season_k9") or e.get("season_k9"), 8.0)
        recent_k9 = _safe(f.get("recent_k9") or f.get("last3_k9"), season_k9)
        season_era = _safe(f.get("season_era") or e.get("season_era"), 4.0)
        recent_era = _safe(f.get("recent_era") or f.get("last3_era"), season_era)

        # Form components
        k_ratio = (recent_k9 / season_k9) if season_k9 > 0 else 1.0
        era_ratio = (season_era / recent_era) if recent_era > 0 else 1.0

        k_score = max(0, min(100, 50 + (k_ratio - 1.0) * 100))
        era_score = max(0, min(100, 50 + (era_ratio - 1.0) * 100))

        # Form trend qualifier
        trend = (f.get("trend") or f.get("form") or "").upper()
        trend_boost = 0
        if "HOT" in trend or "POSITIVE" in trend: trend_boost = 10
        elif "COLD" in trend or "NEGATIVE" in trend: trend_boost = -10

        form_index = round((k_score + era_score) / 2 + trend_boost, 1)
        form_index = max(0, min(100, form_index))

        if form_index >= 75:
            tier = "ELITE_FORM"
        elif form_index >= 60:
            tier = "STRONG_FORM"
        elif form_index >= 40:
            tier = "NEUTRAL_FORM"
        elif form_index >= 25:
            tier = "WEAK_FORM"
        else:
            tier = "STRUGGLING"

        rows.append({
            "pitcher": f.get("pitcher") or c.get("pitcher") or name.title(),
            "team": c.get("team"),
            "matchup": c.get("matchup"),
            "season_k9": round(season_k9, 2),
            "recent_k9": round(recent_k9, 2),
            "season_era": round(season_era, 2),
            "recent_era": round(recent_era, 2),
            "k_ratio_recent_vs_season": round(k_ratio, 3),
            "era_ratio_season_vs_recent": round(era_ratio, 3),
            "trend": trend or None,
            "form_index": form_index,
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["form_index"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_elite_form": sum(1 for r in rows if r["tier"] == "ELITE_FORM"),
        "n_strong_form": sum(1 for r in rows if r["tier"] == "STRONG_FORM"),
        "n_struggling": sum(1 for r in rows if r["tier"] == "STRUGGLING"),
        "method_note": "Starter recent form index. Combines recent_k9 vs season + "
                       "recent_era vs season + trend qualifier. Index 0-100: "
                       "ELITE >=75, STRONG >=60, NEUTRAL >=40, WEAK >=25, "
                       "STRUGGLING <25.",
        "rows": rows,
        "elite_form": [r for r in rows if r["tier"] == "ELITE_FORM"],
        "struggling": [r for r in rows if r["tier"] == "STRUGGLING"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[starter-form] {o['n_pitchers']} pitchers "
          f"({o['n_elite_form']} ELITE, {o['n_strong_form']} STRONG, "
          f"{o['n_struggling']} STRUGGLING) -> {OUT}")
