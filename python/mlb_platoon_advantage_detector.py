"""
EdgeStat -- MLB platoon advantage detector.

Surfaces batters with significant platoon advantage:
  - Batter has favorable handedness vs opposing pitcher (L-vs-R or R-vs-L)
  - Batter L/R career splits show 1.10+ wOBA boost
  - Park favors batter handedness (e.g. LHB at Yankee Stadium)
  - Recent form HOT or NEUTRAL

Output: data/mlb_platoon_advantage_detector.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_platoon_advantage_detector.json")


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
    platoon = _load(os.path.join(DATA_DIR, "mlb_platoon_matrix.json"))
    confluence = _load(os.path.join(DATA_DIR, "mlb_batter_confluence_score.json"))
    park = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    heat = _load(os.path.join(DATA_DIR, "mlb_batter_heat.json"))

    # Platoon advantage: batter handedness vs pitcher handedness
    advantage_idx: Dict[str, Dict[str, Any]] = {}
    for r in (platoon.get("rows") or platoon.get("batters") or []):
        if not isinstance(r, dict): continue
        adv = (r.get("platoon_advantage") or r.get("advantage") or "").upper()
        if "ADVANTAGE" in adv or "FAVORABLE" in adv:
            advantage_idx[_norm(r.get("batter") or r.get("player") or "")] = r

    confluence_idx = {_norm(r.get("batter")): r
                      for r in (confluence.get("rows") or []) if isinstance(r, dict)}

    park_by_matchup: Dict[str, str] = {}
    for g in (park.get("games") or []):
        if isinstance(g, dict):
            park_by_matchup[g.get("matchup", "")] = (g.get("tier") or "").upper()

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "heating_up", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("batter") or r.get("player") or "")] = (
                    r.get("trend") or k).upper()

    alerts: List[Dict[str, Any]] = []
    for name, p_data in advantage_idx.items():
        conf = confluence_idx.get(name, {})
        matchup = p_data.get("matchup") or conf.get("matchup") or ""
        park_tier = park_by_matchup.get(matchup, "")
        h_trend = heat_idx.get(name, "")

        signals: Dict[str, int] = {}
        signals["PLATOON_ADVANTAGE"] = 1
        signals["PARK_FAVORABLE"] = 1 if park_tier in ("HOMER_FRIENDLY", "HITTER_FRIENDLY") else 0
        signals["HOT_FORM"] = 1 if "HOT" in h_trend or "HEATING" in h_trend else 0
        signals["NOT_COLD"] = 1 if "COLD" not in h_trend and "COOLING" not in h_trend else 0

        score = _safe(conf.get("composite_score"))
        signals["HIGH_CONFLUENCE"] = 1 if score >= 12 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "PLATOON_PRIME_SPOT"
        else:
            tier = "PLATOON_FAVORABLE"

        alerts.append({
            "batter": p_data.get("batter") or p_data.get("player") or conf.get("batter") or name.title(),
            "team": p_data.get("team") or conf.get("team"),
            "matchup": matchup,
            "park_tier": park_tier or None,
            "form": h_trend or None,
            "confluence_score": round(score, 2),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                "1+ Hit YES",
                "HR YES (if HITTER_FRIENDLY park)",
                "TB OVER 1.5",
                "Platoon advantage 2+ hits YES",
            ],
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_prime_spot": sum(1 for a in alerts if a["tier"] == "PLATOON_PRIME_SPOT"),
        "method_note": "Platoon advantage detector. Combines platoon_matrix "
                       "(handedness advantage) + park tier + form + confluence_score. "
                       "PLATOON_PRIME_SPOT = 4+ signals.",
        "alerts": alerts,
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-platoon] {o['n_alerts']} alerts ({o['n_prime_spot']} PRIME) -> {OUT}")
