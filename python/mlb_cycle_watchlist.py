"""
EdgeStat -- MLB hit for the cycle watchlist.

Surfaces top candidates for hitting for the cycle (single + double +
triple + HR same game). Extremely rare (~once per 300 MLB games).
Requirements:
  - Confluence_score >= 14 (BATTER_LOCK tier)
  - p_3plus_tb >= 0.30 (deep extra-base potential)
  - p_hr >= 0.22
  - Speed signal (steal proj OR triple-friendly park)
  - HOMER_FRIENDLY or HITTER_FRIENDLY park

Output: data/mlb_cycle_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_cycle_watchlist.json")


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
    confluence = _load(os.path.join(DATA_DIR, "mlb_batter_confluence_score.json"))
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    tb_3 = _load(os.path.join(DATA_DIR, "mlb_batter_3plus_tb_props.json"))
    steals = _load(os.path.join(DATA_DIR, "mlb_steal_props.json"))
    park = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))

    def _prob_idx(src, p_field):
        idx: Dict[str, float] = {}
        for k in ("rows", "top_25_by_p_hr", "top_25_by_p_tb3", "strong_edges"):
            for r in (src.get(k) or []):
                if isinstance(r, dict):
                    key = _norm(r.get("batter") or r.get("player") or "")
                    if key and key not in idx:
                        idx[key] = _safe(r.get(p_field) or r.get("p"))
        return idx

    hr_idx = _prob_idx(hr, "p_hr")
    tb3_idx = _prob_idx(tb_3, "p_tb3")

    speed_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (steals.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("batter") or r.get("player") or "")
                if key and key not in speed_idx:
                    speed_idx[key] = _safe(r.get("p_steal") or r.get("p"))

    park_by_matchup: Dict[str, str] = {}
    for g in (park.get("games") or []):
        if isinstance(g, dict):
            park_by_matchup[g.get("matchup", "")] = (g.get("tier") or "").upper()

    watchlist: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 14: continue

        name = _norm(r.get("batter") or "")
        p_hr = hr_idx.get(name, 0)
        p_tb3 = tb3_idx.get(name, 0)
        p_speed = speed_idx.get(name, 0)
        park_tier = park_by_matchup.get(r.get("matchup") or "", "")

        if p_hr < 0.22: continue
        if p_tb3 < 0.30: continue

        has_speed = p_speed >= 0.20
        favorable_park = park_tier in ("HOMER_FRIENDLY", "HITTER_FRIENDLY")
        if not (has_speed or favorable_park): continue

        # Estimate cycle probability (very rough)
        # baseline cycle rate ~ 0.005 per game
        cycle_p_est = 0.003 * (score / 14.0) * (p_hr / 0.20) * (p_tb3 / 0.25)
        if has_speed: cycle_p_est *= 1.5
        cycle_p_est = min(cycle_p_est, 0.025)

        watchlist.append({
            "batter": r.get("batter"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "composite_score": round(score, 2),
            "p_hr": round(p_hr, 3),
            "p_3plus_tb": round(p_tb3, 3),
            "p_steal": round(p_speed, 3),
            "park_tier": park_tier or None,
            "has_speed": has_speed,
            "est_p_cycle": round(cycle_p_est, 5),
            "advisory": "Long-shot cycle candidate. Recommended bets: "
                        "hit for the cycle YES (200-1 to 500-1 typical, "
                        "skip if not available), HR + 3+ TB + 2+ hits "
                        "correlated parlay (more reasonable payout).",
            "recommended_markets": [
                "Hit for cycle YES (long shot)",
                "HR YES + 3+ TB YES + 2+ Hits YES (parlay)",
                "Player TB OVER 3.5",
            ],
        })

    watchlist.sort(key=lambda w: -w["est_p_cycle"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "MLB hit for cycle watchlist. Confluence >= 14 + p_hr "
                       ">= 22% + p_3plus_tb >= 30% + (speed OR favorable park). "
                       "Cycles ~0.3% baseline historical so filter is strict.",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-cycle] {o['n_watchlist']} on watchlist -> {OUT}")
