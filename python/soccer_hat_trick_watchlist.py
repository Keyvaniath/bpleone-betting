"""
EdgeStat -- Soccer hat trick watchlist.

Surfaces forwards with elite goal-scoring potential where a hat trick is
statistically more likely than usual:
  - Anytime goal probability >= 0.50
  - 2+ goals probability >= 0.25
  - Match high-scoring alignment (HIGH_SCORING_ALIGNMENT tier)
  - Total goals OVER lean

Hat tricks ~3-5% per match historically. We surface for "to score 3+
goals" bets.

Output: data/soccer_hat_trick_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_hat_trick_watchlist.json")


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
    goalscorer = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))
    goal2 = _load(os.path.join(DATA_DIR, "soccer_goalscorer_2plus.json"))
    high_scoring = _load(os.path.join(DATA_DIR, "soccer_high_scoring_alignment.json"))
    goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))

    # Top goalscorers by p_score
    g_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (goalscorer.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in g_idx:
                    g_idx[key] = r

    g2_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (goal2.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in g2_idx:
                    g2_idx[key] = _safe(r.get("p_2plus_goals") or r.get("p"))

    hs_matches: set = set()
    for a in (high_scoring.get("high_scoring") or high_scoring.get("alignments") or []):
        if isinstance(a, dict):
            m = _norm(a.get("match") or "")
            if m: hs_matches.add(m)

    goals_over_matches: set = set()
    for r in (goals.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                goals_over_matches.add(_norm(r.get("match") or r.get("matchup") or ""))

    watchlist: List[Dict[str, Any]] = []
    for name, g_data in g_idx.items():
        p_score = _safe(g_data.get("p_score") or g_data.get("p"))
        p_2plus = g2_idx.get(name, 0)
        if p_score < 0.50 or p_2plus < 0.25: continue

        match_norm = _norm(g_data.get("match") or g_data.get("matchup") or "")
        is_high_scoring = match_norm in hs_matches
        is_goals_over = match_norm in goals_over_matches

        # Estimate hat trick prob (very rough)
        # p_3plus ~ p_2plus * 0.3 (drop-off for 3rd goal)
        p_3plus = p_2plus * 0.30 * (1.3 if is_high_scoring else 1.0)
        p_3plus = min(p_3plus, 0.20)

        if p_3plus < 0.04: continue  # baseline 3-5% historical

        watchlist.append({
            "player": g_data.get("player"),
            "match": g_data.get("match") or g_data.get("matchup"),
            "team": g_data.get("team"),
            "p_score": round(p_score, 3),
            "p_2plus_goals": round(p_2plus, 3),
            "est_p_3plus_goals_hat_trick": round(p_3plus, 4),
            "match_high_scoring": is_high_scoring,
            "match_goals_over": is_goals_over,
            "advisory": "Top hat-trick candidate. Recommended bets: 3+ goals "
                        "YES (typical 8-1 to 15-1), 2+ goals YES, anytime "
                        "goalscorer + total goals OVER (parlay).",
            "recommended_markets": [
                "3+ Goals YES (hat trick)",
                "2+ Goals YES",
                "Player + Total Goals OVER (parlay)",
            ],
        })

    watchlist.sort(key=lambda w: -w["est_p_3plus_goals_hat_trick"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "Hat trick watchlist. p_score >= 50% + p_2plus >= 25%. "
                       "Estimated p_3plus = p_2plus * 0.30 * (1.3x if "
                       "high-scoring match). Surfaces if est >= 4% "
                       "(historical baseline 3-5%).",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-hat-trick] {o['n_watchlist']} on watchlist -> {OUT}")
