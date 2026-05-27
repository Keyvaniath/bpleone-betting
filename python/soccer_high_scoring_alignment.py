"""
EdgeStat -- Soccer high-scoring alignment alerts.

Soccer analog to MLB two-way / NBA two-way. Surfaces matches where
multiple high-scoring signals align:
  - p_btts_yes >= 0.62 (both teams score very likely)
  - total goals OVER lean (STRONG_OVER preferred)
  - p_first_score_either >= 0.65 (someone scores early)
  - corners OVER lean
  - high-conviction goalscorer pick (p_score >= 0.55)

When 4+ of these align, the match is a high-leverage multi-leg parlay:
  - Both Teams To Score YES
  - Total Goals OVER (2.5 or 3.5)
  - First Team To Score YES + Anytime Goalscorer YES
  - Corners OVER

HIGH_SCORING_ALIGNMENT = 4+ signals; CONFLUENCE_GOALS = 3 signals.

Output: data/soccer_high_scoring_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_high_scoring_alignment.json")


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
    btts = _load(os.path.join(DATA_DIR, "soccer_btts_props.json"))
    goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))
    first_score = _load(os.path.join(DATA_DIR, "soccer_first_to_score_props.json"))
    corners = _load(os.path.join(DATA_DIR, "soccer_corners_props.json"))
    goalscorer = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))

    btts_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (btts.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in btts_idx:
                    btts_idx[key] = _safe(r.get("p_btts_yes") or r.get("p"))

    goals_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (goals.get("rows") or []) if isinstance(r, dict)}

    fs_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (first_score.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in fs_idx:
                    fs_idx[key] = _safe(r.get("p_either") or r.get("p"))

    corners_idx = {_norm(r.get("match") or r.get("matchup")): r
                   for r in (corners.get("rows") or []) if isinstance(r, dict)}

    # Top goalscorer per match
    top_scorer: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (goalscorer.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                p_score = _safe(r.get("p_score") or r.get("p"))
                if key:
                    existing = top_scorer.get(key)
                    if not existing or p_score > existing.get("p_score", 0):
                        top_scorer[key] = {"player": r.get("player"), "p_score": p_score}

    all_matches = (set(btts_idx) | set(goals_idx) | set(fs_idx)
                   | set(corners_idx) | set(top_scorer))

    alignments: List[Dict[str, Any]] = []
    for key in all_matches:
        signals: Dict[str, int] = {}
        p_btts = btts_idx.get(key, 0)
        signals["BTTS_HIGH"] = 1 if p_btts >= 0.62 else 0

        goals_ec = (goals_idx.get(key, {}).get("edge_class") or "").upper()
        signals["GOALS_STRONG_OVER"] = 1 if "STRONG_OVER" in goals_ec else 0
        signals["GOALS_OVER_LEAN"] = 1 if "OVER" in goals_ec and "STRONG" not in goals_ec else 0

        p_first = fs_idx.get(key, 0)
        signals["FIRST_SCORE_EARLY"] = 1 if p_first >= 0.65 else 0

        corners_ec = (corners_idx.get(key, {}).get("edge_class") or "").upper()
        signals["CORNERS_OVER"] = 1 if "OVER" in corners_ec else 0

        ts = top_scorer.get(key, {})
        p_score = ts.get("p_score", 0)
        signals["GOALSCORER_LIVE"] = 1 if p_score >= 0.55 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "HIGH_SCORING_ALIGNMENT"
        else:
            tier = "CONFLUENCE_GOALS"

        alignments.append({
            "match": (goals_idx.get(key, {}).get("match")
                      or goals_idx.get(key, {}).get("matchup") or key),
            "league": goals_idx.get(key, {}).get("league"),
            "p_btts_yes": round(p_btts, 3),
            "goals_edge": goals_ec or None,
            "p_first_score": round(p_first, 3),
            "corners_edge": corners_ec or None,
            "top_goalscorer": ts.get("player"),
            "p_goalscorer": round(p_score, 3),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_parlay": [
                "BTTS YES",
                "Total Goals OVER",
                "First Team to Score YES" if signals.get("FIRST_SCORE_EARLY") else "",
                "Corners OVER" if signals.get("CORNERS_OVER") else "",
                (f"{ts.get('player')} Anytime Goal YES"
                 if signals.get("GOALSCORER_LIVE") else ""),
            ],
        })

    alignments.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "n_high_scoring": sum(1 for a in alignments
                              if a["tier"] == "HIGH_SCORING_ALIGNMENT"),
        "n_confluence_goals": sum(1 for a in alignments
                                  if a["tier"] == "CONFLUENCE_GOALS"),
        "method_note": "Soccer high-scoring alignment. 4+ signals across BTTS_HIGH "
                       "(>=62%), GOALS_STRONG_OVER, FIRST_SCORE_EARLY (>=65%), "
                       "CORNERS_OVER, GOALSCORER_LIVE (>=55%). HIGH_SCORING_ALIGNMENT "
                       "= 4+; CONFLUENCE_GOALS = 3.",
        "alignments": alignments,
        "high_scoring": [a for a in alignments
                         if a["tier"] == "HIGH_SCORING_ALIGNMENT"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-high-scoring] {o['n_alignments']} alignments "
          f"({o['n_high_scoring']} HIGH, {o['n_confluence_goals']} CONFLUENCE) -> {OUT}")
