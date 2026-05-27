"""
EdgeStat -- MLB park-adjusted HR predictor.

Combines per-batter HR probability with park HR factor to produce a
park-adjusted HR projection. Surfaces batters in HR-friendly parks
with already-elevated HR probability:

  PARK_ADJ_HR_PROB = baseline_p_hr * park_hr_factor
  STRONG_PARK_HR_LEAN: park_adj >= 25% AND park factor >= 1.05

Output: data/mlb_park_adjusted_hr_predictor.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_park_adjusted_hr_predictor.json")


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
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    park = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))

    # Park HR factors by matchup (or by team home park)
    park_factor_by_matchup: Dict[str, float] = {}
    park_tier_by_matchup: Dict[str, str] = {}
    for g in (park.get("games") or park.get("rows") or []):
        if not isinstance(g, dict): continue
        m = g.get("matchup", "")
        if m:
            park_factor_by_matchup[m] = _safe(g.get("hr_factor") or g.get("park_factor"),
                                              1.0)
            park_tier_by_matchup[m] = (g.get("tier") or "").upper()

    candidates: List[Dict[str, Any]] = []

    for k in ("rows", "top_25_by_p_hr", "strong_edges"):
        for r in (hr.get(k) or []):
            if not isinstance(r, dict): continue
            p_hr = _safe(r.get("p_hr") or r.get("p"))
            if p_hr <= 0: continue
            matchup = r.get("matchup") or ""
            park_factor = park_factor_by_matchup.get(matchup, 1.0)
            park_tier = park_tier_by_matchup.get(matchup, "")

            adj_p = p_hr * park_factor

            flags: List[str] = []
            if adj_p >= 0.25 and park_factor >= 1.05:
                flags.append("STRONG_PARK_HR_LEAN")
            elif adj_p >= 0.18:
                flags.append("PARK_HR_LEAN")
            if park_tier in ("HOMER_FRIENDLY",):
                flags.append("HOMER_FRIENDLY_PARK")

            if not flags: continue

            candidates.append({
                "batter": r.get("batter") or r.get("player"),
                "team": r.get("team"),
                "matchup": matchup,
                "baseline_p_hr": round(p_hr, 3),
                "park_hr_factor": round(park_factor, 2),
                "park_tier": park_tier or None,
                "park_adjusted_p_hr": round(adj_p, 3),
                "flags": flags,
                "recommended_markets": [
                    "HR YES" if "STRONG_PARK_HR_LEAN" in flags else "HR alt boost",
                    "TB OVER 1.5",
                    "3+ TB YES" if "STRONG_PARK_HR_LEAN" in flags else "",
                ],
            })

    # Dedupe by player
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for c in candidates:
        key = (_norm(c["batter"]), c.get("matchup"))
        if key in seen: continue
        seen.add(key)
        unique.append(c)

    unique.sort(key=lambda c: -c["park_adjusted_p_hr"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_candidates": len(unique),
        "n_strong_park_hr": sum(1 for c in unique
                                if "STRONG_PARK_HR_LEAN" in (c.get("flags") or [])),
        "method_note": "Park-adjusted HR predictor. park_adj_p_hr = baseline_p_hr "
                       "* park_hr_factor. STRONG_PARK_HR_LEAN at adj_p >= 25% AND "
                       "park_factor >= 1.05. PARK_HR_LEAN at adj_p >= 18%.",
        "candidates": unique,
        "strong_park_hr": [c for c in unique
                           if "STRONG_PARK_HR_LEAN" in (c.get("flags") or [])],
        "top_15": unique[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[park-hr] {o['n_candidates']} candidates "
          f"({o['n_strong_park_hr']} STRONG) -> {OUT}")
