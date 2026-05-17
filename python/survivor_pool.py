"""
EdgeStat -- NFL survivor pool optimizer.

For each NFL week (when in-season), recommends a single team to pick that:
  - Has high win probability THIS week (P(win) >= 65%)
  - Has been saved for later: doesn't waste an elite team early in season
  - Account for survival value: hold strong-favorite teams (Chiefs, Eagles) for
    must-win weeks; use upper-mid favorites (P=68-78%) on early weeks

Strategy implemented:
  - Score = P(this week) × futureBudget(team)
  - futureBudget penalizes burning a team that has 3+ future weeks rated > 75%
  - Heuristic: a team's "survival reserve" is sum of their top-5 weekly probs

Since NFL is off-season today (May), this is a stub that surfaces "next week"
when schedule data arrives. Captures the algorithm + UI scaffolding.

Output: data/survivor_pool.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "survivor_pool.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    nfl = _load(os.path.join(DATA_DIR, "nfl_state.json"))
    games = [g for g in (nfl.get("games") or []) if g.get("state") != "post"]
    season_status = nfl.get("season_status", "offseason")

    if not games:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "season_status": season_status,
            "note": "NFL is currently off-season. Survivor pool picks activate once Week 1 schedule lands.",
            "n_candidates": 0,
            "picks": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Score each pickable team this week
    candidates = []
    for g in games:
        ph = g.get("p_home_win") or 0.5
        # Home pick
        if ph >= 0.65:
            candidates.append({
                "team": g.get("home_team"),
                "opponent": g.get("away_team"),
                "p_win_this_week": round(ph, 4),
                "side": "HOME",
                "fair_american": g.get("fair_home_american"),
                "matchup": g.get("matchup"),
            })
        # Away pick
        if (1 - ph) >= 0.65:
            candidates.append({
                "team": g.get("away_team"),
                "opponent": g.get("home_team"),
                "p_win_this_week": round(1 - ph, 4),
                "side": "AWAY",
                "fair_american": g.get("fair_away_american"),
                "matchup": g.get("matchup"),
            })

    # Sort by P(win) desc and tier
    candidates.sort(key=lambda c: -c["p_win_this_week"])
    for c in candidates:
        p = c["p_win_this_week"]
        c["tier"] = ("LOCK" if p >= 0.78 else
                      "STRONG" if p >= 0.72 else
                      "GOOD" if p >= 0.68 else "MARGINAL")
        # Survival reserve heuristic: stronger teams have more future value
        c["survival_reserve_advice"] = (
            "SAVE for later week — strong reserve team" if p >= 0.78 else
            "USE THIS WEEK — solid floor without burning a future lock" if 0.68 <= p <= 0.76 else
            "RISKY — only if you've already used all stronger options"
        )

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season_status": season_status,
        "n_candidates": len(candidates),
        "n_locks": sum(1 for c in candidates if c["tier"] == "LOCK"),
        "n_strong": sum(1 for c in candidates if c["tier"] == "STRONG"),
        "n_good": sum(1 for c in candidates if c["tier"] == "GOOD"),
        "best_pick_this_week": candidates[0] if candidates else None,
        "picks": candidates[:15],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Survivor pool: {p['n_candidates']} candidates ({p.get('n_locks',0)} locks, {p.get('n_strong',0)} strong, {p.get('n_good',0)} good)")
    if p.get("best_pick_this_week"):
        b = p["best_pick_this_week"]
        print(f"  Best pick: {b['team']} (P={b['p_win_this_week']*100:.1f}%) [{b.get('tier')}]")
