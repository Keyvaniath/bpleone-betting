"""
EdgeStat -- MLB batter streak alerts.

Surfaces batters on active hitting or HR streaks:
  - On-base streak (heat HOT + recent hits)
  - HR streak (recent HR + park-adjusted HR predictor STRONG)
  - Hot lineup spot (top of order + lineup_quality ELITE)

Output: data/mlb_batter_streak_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_streak_alerts.json")


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
    heat = _load(os.path.join(DATA_DIR, "mlb_batter_heat.json"))
    confluence = _load(os.path.join(DATA_DIR, "mlb_batter_confluence_score.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_adjusted_hr_predictor.json"))
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))

    # Heat trend
    heat_idx: Dict[str, str] = {}
    for k in ("hot", "heating_up", "cold", "cooling_down", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("batter") or r.get("player") or "")] = (
                    r.get("trend") or k).upper()

    confluence_idx = {_norm(r.get("batter")): r
                      for r in (confluence.get("rows") or []) if isinstance(r, dict)}

    park_strong_set: set = set()
    for c in (park_hr.get("strong_park_hr") or []):
        if isinstance(c, dict):
            park_strong_set.add(_norm(c.get("batter") or ""))

    hr_high: Dict[str, float] = {}
    for k in ("rows", "top_25_by_p_hr"):
        for r in (hr.get(k) or []):
            if isinstance(r, dict):
                p_hr = _safe(r.get("p_hr") or r.get("p"))
                if p_hr >= 0.20:
                    hr_high[_norm(r.get("batter") or r.get("player") or "")] = p_hr

    streaks: List[Dict[str, Any]] = []
    all_batters = set(heat_idx) | set(confluence_idx) | park_strong_set | set(hr_high)

    for name in all_batters:
        heat_trend = heat_idx.get(name, "")
        conf_data = confluence_idx.get(name, {})
        is_park_strong = name in park_strong_set
        p_hr = hr_high.get(name, 0)

        flags: List[str] = []
        if "HOT" in heat_trend or "HEATING" in heat_trend:
            flags.append("HEAT_HOT")
        if conf_data.get("ceiling_overs", 0) >= 4:
            flags.append("CEILING_ELITE")
        if is_park_strong:
            flags.append("PARK_HR_STRONG")
        if p_hr >= 0.22:
            flags.append("HR_LIKELY")

        if len(flags) < 2: continue

        streaks.append({
            "batter": conf_data.get("batter") or name.title(),
            "team": conf_data.get("team"),
            "matchup": conf_data.get("matchup"),
            "heat_trend": heat_trend or None,
            "ceiling_overs": conf_data.get("ceiling_overs", 0),
            "park_hr_strong": is_park_strong,
            "p_hr": round(p_hr, 3),
            "n_streak_flags": len(flags),
            "flags": flags,
            "recommended_markets": [
                "1+ Hit YES (streak)" if "HEAT_HOT" in flags else "",
                "TB OVER + 3+ TB YES" if "CEILING_ELITE" in flags else "",
                "HR YES" if "HR_LIKELY" in flags or "PARK_HR_STRONG" in flags else "",
            ],
        })

    streaks.sort(key=lambda s: -s["n_streak_flags"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(streaks),
        "method_note": "Batter streak alerts. 2+ flags from HEAT_HOT, "
                       "CEILING_ELITE (>=4 OVERs), PARK_HR_STRONG (park-adjusted "
                       "HR), HR_LIKELY (p_hr >= 22%). Recommends streak-specific "
                       "markets.",
        "alerts": streaks,
        "top_15": streaks[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-streak] {o['n_alerts']} streak alerts -> {OUT}")
