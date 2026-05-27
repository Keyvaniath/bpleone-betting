"""
EdgeStat -- Soccer first-half goal alignment.

Surfaces matches with multi-signal first-half scoring alignment:
  - p_first_score_either >= 0.65 (someone scores early)
  - team_score_1h lean OVER for one or both teams
  - 1st half goals OVER lean (from total goals decomposition)
  - HT result not 0-0 implied by other signals

When 3+ signals align: bet 1H goals OVER, HT not 0-0, first-team-to-score.

Output: data/soccer_first_half_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_first_half_alignment.json")


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
    first_score = _load(os.path.join(DATA_DIR, "soccer_first_to_score_props.json"))
    team_1h = _load(os.path.join(DATA_DIR, "soccer_team_score_1h.json"))
    goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))

    fs_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (first_score.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in fs_idx:
                    fs_idx[key] = _safe(r.get("p_either") or r.get("p"))

    team_1h_by_match: Dict[str, List[Dict[str, Any]]] = {}
    for k in ("rows", "strong_edges"):
        for r in (team_1h.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key:
                    team_1h_by_match.setdefault(key, []).append(r)

    goals_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (goals.get("rows") or []) if isinstance(r, dict)}

    all_matches = set(fs_idx) | set(team_1h_by_match) | set(goals_idx)

    alignments: List[Dict[str, Any]] = []
    for key in all_matches:
        signals: Dict[str, int] = {}
        p_first = fs_idx.get(key, 0)
        signals["EARLY_GOAL_LIKELY"] = 1 if p_first >= 0.65 else 0

        team_1h_rows = team_1h_by_match.get(key, [])
        team_1h_over_count = 0
        for tr in team_1h_rows:
            ec = (tr.get("edge_class") or "").upper()
            if "OVER" in ec:
                team_1h_over_count += 1
        signals["TEAM_1H_OVER"] = 1 if team_1h_over_count >= 1 else 0
        signals["BOTH_TEAMS_1H_OVER"] = 1 if team_1h_over_count >= 2 else 0

        # Total goals OVER as a proxy for 1H goals
        goals_ec = (goals_idx.get(key, {}).get("edge_class") or "").upper()
        signals["TOTAL_GOALS_OVER"] = 1 if "OVER" in goals_ec else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 2: continue

        if n_positive >= 3:
            tier = "FIRST_HALF_ALIGNMENT"
        else:
            tier = "FIRST_HALF_LEAN"

        alignments.append({
            "match": (goals_idx.get(key, {}).get("match")
                      or goals_idx.get(key, {}).get("matchup") or key),
            "league": goals_idx.get(key, {}).get("league"),
            "p_first_score": round(p_first, 3),
            "team_1h_over_count": team_1h_over_count,
            "total_goals_edge": goals_ec or None,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_parlay": [
                "1st Half Goals OVER",
                "HT Not 0-0",
                "First Team to Score (favorite)" if signals.get("EARLY_GOAL_LIKELY") else "",
                "Both Teams to Score 1H YES" if signals.get("BOTH_TEAMS_1H_OVER") else "",
            ],
        })

    alignments.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "n_first_half_alignment": sum(1 for a in alignments
                                      if a["tier"] == "FIRST_HALF_ALIGNMENT"),
        "method_note": "First-half scoring alignment. Signals: EARLY_GOAL_LIKELY "
                       "(p_either >= 65%), TEAM_1H_OVER, BOTH_TEAMS_1H_OVER, "
                       "TOTAL_GOALS_OVER. ALIGNMENT = 3+; LEAN = 2.",
        "alignments": alignments,
        "first_half_locks": [a for a in alignments
                             if a["tier"] == "FIRST_HALF_ALIGNMENT"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-1h] {o['n_alignments']} alignments "
          f"({o['n_first_half_alignment']} LOCK) -> {OUT}")
