"""
EdgeStat -- MLB pitcher recent-form tracker.

For each starter scheduled tonight, compares recent (last 3 starts) form to
season baseline. Flags pitchers who are:

  - HEATING_UP:   recent K9 +1.5 vs season AND recent ERA -1.0 vs season
                  (lean K_OVER, OUTS_OVER, QS_YES, opp_TT_UNDER)
  - COOLING_DOWN: recent K9 -1.5 vs season OR recent ERA +1.5 vs season
                  (lean K_UNDER, OUTS_UNDER, QS_NO, opp_TT_OVER)
  - HOT_K:        only K9 elevated, ERA mixed (lean K_OVER only)
  - COLD_K:       only K9 depressed, ERA mixed (lean K_UNDER only)
  - STEADY:       no significant deviation

Output: data/mlb_pitcher_form_tracker.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json")


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


def _classify(season_k9: float, recent_k9: float,
              season_era: float, recent_era: float) -> str:
    k9_delta = recent_k9 - season_k9
    era_delta = recent_era - season_era

    if k9_delta >= 1.5 and era_delta <= -1.0:
        return "HEATING_UP"
    if k9_delta <= -1.5 or era_delta >= 1.5:
        return "COOLING_DOWN"
    if k9_delta >= 1.5:
        return "HOT_K"
    if k9_delta <= -1.5:
        return "COLD_K"
    return "STEADY"


def _leans_for(status: str) -> List[str]:
    return {
        "HEATING_UP": ["K_OVER", "OUTS_OVER", "QS_YES", "OPP_TT_UNDER", "1ST_INN_ER_NO"],
        "COOLING_DOWN": ["K_UNDER", "OUTS_UNDER", "QS_NO", "OPP_TT_OVER", "1ST_INN_ER_YES"],
        "HOT_K": ["K_OVER"],
        "COLD_K": ["K_UNDER"],
        "STEADY": [],
    }.get(status, [])


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_l = sp_name.lower()
            sp_row = p_by_name.get(sp_l, {})
            stats = sp_row.get("stats") or {}
            recent = sp_row.get("recent") or {}

            season_k9 = _safe(stats.get("k_per_9"), 8.5)
            season_era = _safe(stats.get("era"), 4.20)
            # Recent 3-start composite
            recent_k9 = _safe(recent.get("k_per_9_l3") or recent.get("k_per_9_recent"),
                              season_k9)
            recent_era = _safe(recent.get("era_l3") or recent.get("era_recent"),
                               season_era)

            status = _classify(season_k9, recent_k9, season_era, recent_era)
            leans = _leans_for(status)

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "season_k_per_9": round(season_k9, 2),
                "season_era": round(season_era, 2),
                "recent_k_per_9_l3": round(recent_k9, 2),
                "recent_era_l3": round(recent_era, 2),
                "k9_delta": round(recent_k9 - season_k9, 2),
                "era_delta": round(recent_era - season_era, 2),
                "status": status,
                "leans": leans,
            })

    rows.sort(key=lambda r: {
        "HEATING_UP": 0, "HOT_K": 1, "COOLING_DOWN": 2, "COLD_K": 3, "STEADY": 4
    }.get(r["status"], 5))

    n_heating = sum(1 for r in rows if r["status"] == "HEATING_UP")
    n_cooling = sum(1 for r in rows if r["status"] == "COOLING_DOWN")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_heating_up": n_heating,
        "n_cooling_down": n_cooling,
        "method_note": "Compares recent 3-start K9/ERA vs season baseline. HEATING_UP = "
                       "K9+1.5 AND ERA-1.0; COOLING_DOWN = K9-1.5 OR ERA+1.5. Drives K/"
                       "outs/QS/opp_TT directional leans.",
        "rows": rows,
        "heating_up_alerts": [r for r in rows if r["status"] == "HEATING_UP"],
        "cooling_down_alerts": [r for r in rows if r["status"] == "COOLING_DOWN"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitch-form] {o['n_starters']} starters, {o['n_heating_up']} heating, "
          f"{o['n_cooling_down']} cooling -> {OUT}")
