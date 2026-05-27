"""
EdgeStat -- NHL first goal scorer value alerts.

Surfaces top first-goal-scorer plays:
  - p_first_goal >= 0.06 (baseline ~0.05 across ~20 skaters per team)
  - Player anytime goal probability >= 0.30 (volume scorer)
  - Player ceiling stack signaled (multi-prop OVERs)

First goal scorer markets pay 8-1 to 15-1 typically, so even small edges
translate to real EV.

Output: data/nhl_first_goalscorer_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_first_goalscorer_alerts.json")


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
    first_goal = _load(os.path.join(DATA_DIR, "nhl_first_goalscorer_props.json"))
    atg = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    ceiling = _load(os.path.join(DATA_DIR, "nhl_skater_ceiling_stack.json"))

    fg_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (first_goal.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in fg_idx:
                    fg_idx[key] = r

    atg_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (atg.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in atg_idx:
                    atg_idx[key] = _safe(r.get("p_atg") or r.get("p"))

    ceiling_idx = {_norm(a.get("player")): a
                   for a in (ceiling.get("alerts") or []) if isinstance(a, dict)}

    alerts: List[Dict[str, Any]] = []
    for name, fg_data in fg_idx.items():
        p_fg = _safe(fg_data.get("p_first_goal") or fg_data.get("p_1st_goal") or fg_data.get("p"))
        if p_fg < 0.06: continue

        p_atg = atg_idx.get(name, 0)
        if p_atg < 0.30: continue

        c = ceiling_idx.get(name, {})
        ceiling_overs = int(c.get("n_aligned_overs", 0) or 0)

        # Estimate fair odds from p_fg
        if 0 < p_fg < 1:
            if p_fg >= 0.5:
                fair_odds = -int(round(100 / ((1 / p_fg) - 1)))
            else:
                fair_odds = int(round(((1 / p_fg) - 1) * 100))
        else:
            fair_odds = None

        alerts.append({
            "player": fg_data.get("player") or fg_data.get("skater") or name.title(),
            "team": fg_data.get("team"),
            "matchup": fg_data.get("matchup"),
            "p_first_goal": round(p_fg, 4),
            "p_anytime_goal": round(p_atg, 3),
            "ceiling_overs": ceiling_overs,
            "fair_odds_american": fair_odds,
            "advisory": "First goal scorer value play. Typical 8-1 to 15-1 odds. "
                        "Recommended: first goal YES + anytime goal YES (parlay) "
                        "for correlated value.",
            "recommended_markets": [
                "First goal scorer YES",
                "Anytime goal YES (correlated)",
                "Goal in 1st period YES",
            ],
        })

    alerts.sort(key=lambda a: -a["p_first_goal"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "method_note": "First goal scorer value alerts. p_first_goal >= 6% AND "
                       "p_anytime_goal >= 30% (volume scorer). Computes fair "
                       "American odds. Typical market pays 8-1 to 15-1 so any "
                       "edge is meaningful EV.",
        "alerts": alerts,
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-fg] {o['n_alerts']} first-goal alerts -> {OUT}")
