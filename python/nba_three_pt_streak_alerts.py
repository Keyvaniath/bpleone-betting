"""
EdgeStat -- NBA 3-point streak alerts.

Surfaces hot 3-point shooters with multiple OVER signals:
  - Threes OVER edge_class
  - Threes alt YES (multi-line edge)
  - High projected attempts
  - Hot form (heat HOT)
  - 30+ pts probability >= 25% (volume scorer with 3PM upside)

Output: data/nba_three_pt_streak_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_three_pt_streak_alerts.json")


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
    threes = _load(os.path.join(DATA_DIR, "nba_player_threes_props.json"))
    threes_alt = _load(os.path.join(DATA_DIR, "nba_player_threes_alt_props.json"))
    heat = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))

    threes_idx = {_norm(r.get("player")): r
                  for r in (threes.get("rows") or []) if isinstance(r, dict)}

    alt_strong_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (threes_alt.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                ec = (r.get("edge_class") or "").upper()
                if key and ("STRONG_ALT" in ec or "OVER" in ec):
                    alt_strong_idx[key] = r

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "heating_up", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    pts30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts30_idx:
                    pts30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    min_idx = {_norm(r.get("player")): _safe(
                   r.get("projected_minutes") or r.get("expected_minutes"))
               for r in (minutes.get("rows") or []) if isinstance(r, dict)}

    alerts: List[Dict[str, Any]] = []
    for name, r in threes_idx.items():
        ec = (r.get("edge_class") or "").upper()
        signals: Dict[str, int] = {}
        signals["THREES_OVER"] = 1 if "OVER" in ec else 0
        signals["THREES_ALT_STRONG"] = 1 if name in alt_strong_idx else 0
        h_trend = heat_idx.get(name, "")
        signals["HOT_FORM"] = 1 if "HOT" in h_trend or "HEATING" in h_trend else 0
        p_30 = pts30_idx.get(name, 0)
        signals["30PLUS_PTS_LIVE"] = 1 if p_30 >= 0.25 else 0
        proj_min = min_idx.get(name, 0)
        signals["HIGH_MINUTES"] = 1 if proj_min >= 34 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 5:
            tier = "3PM_STREAK_ELITE"
        elif n_positive == 4:
            tier = "3PM_STREAK_STRONG"
        else:
            tier = "3PM_STREAK_LEAN"

        alerts.append({
            "player": r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "threes_edge_class": ec or None,
            "p_30plus_pts": round(p_30, 3),
            "form": h_trend or None,
            "projected_minutes": round(proj_min, 1),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                "3PM OVER",
                "3+ 3PM YES (alt)",
                "4+ 3PM YES (long shot alt)",
                "PTS OVER + 3PM OVER (correlated parlay)",
            ],
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "3PM_STREAK_ELITE"),
        "method_note": "NBA 3PM streak alerts. 3+ signals: THREES_OVER, "
                       "THREES_ALT_STRONG, HOT_FORM, 30PLUS_PTS_LIVE (>=25%), "
                       "HIGH_MINUTES (>=34). ELITE = 5; STRONG = 4; LEAN = 3.",
        "alerts": alerts,
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-3pm] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
