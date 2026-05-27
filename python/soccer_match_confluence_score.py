"""
EdgeStat -- Soccer match confluence score.

Composite per-match score combining match-level synthesizers:
  - soccer_match_alert_synthesizer (n_aligned_overs)
  - soccer_total_goals_props (edge_class)
  - soccer_btts_props (p_btts_yes)
  - soccer_corners_props (edge_class)
  - soccer_first_to_score_props

Score formula:
  score = ceiling_overs * 2 + goals_over_signal*3 + p_btts*15 +
          corners_over*2 + first_score_lean

MATCH_LOCK = score >= 14 with ceiling >= 4
MATCH_STRONG = 8-13
MATCH_FADE = score <= -2

Output: data/soccer_match_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_match_confluence_score.json")


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
    match_alerts = _load(os.path.join(DATA_DIR, "soccer_match_alert_synthesizer.json"))
    goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))
    btts = _load(os.path.join(DATA_DIR, "soccer_btts_props.json"))
    corners = _load(os.path.join(DATA_DIR, "soccer_corners_props.json"))
    first_score = _load(os.path.join(DATA_DIR, "soccer_first_to_score_props.json"))

    alert_idx = {_norm(a.get("match")): a for a in (match_alerts.get("alerts") or [])
                 if isinstance(a, dict)}

    goals_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (goals.get("rows") or []) if isinstance(r, dict)}

    btts_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (btts.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in btts_idx:
                    btts_idx[key] = _safe(r.get("p_btts_yes") or r.get("p"))

    corners_idx = {_norm(r.get("match") or r.get("matchup")): r
                   for r in (corners.get("rows") or []) if isinstance(r, dict)}

    fs_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (first_score.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in fs_idx:
                    fs_idx[key] = _safe(r.get("p_either") or r.get("p"))

    all_matches = (set(alert_idx) | set(goals_idx) | set(btts_idx)
                   | set(corners_idx) | set(fs_idx))

    rows: List[Dict[str, Any]] = []
    for key in all_matches:
        a = alert_idx.get(key, {})
        g = goals_idx.get(key, {})
        p_btts = btts_idx.get(key, 0)
        c = corners_idx.get(key, {})
        p_first = fs_idx.get(key, 0)

        ceiling_overs = int(a.get("n_aligned_overs", 0) or 0)

        goals_ec = (g.get("edge_class") or "").upper()
        goals_signal = 3 if "STRONG_OVER" in goals_ec else (
            2 if "OVER" in goals_ec else (-2 if "UNDER" in goals_ec else 0))

        corners_ec = (c.get("edge_class") or "").upper()
        corners_signal = 2 if "OVER" in corners_ec else (-1 if "UNDER" in corners_ec else 0)

        first_score_lean = 1 if p_first >= 0.65 else 0

        score = (ceiling_overs * 2 + goals_signal + p_btts * 15
                 + corners_signal + first_score_lean)

        has_data = (ceiling_overs > 0 or goals_signal != 0 or p_btts > 0
                    or corners_signal != 0 or p_first > 0)

        # Baseline score is around 8-9 for an average match with BTTS ~0.55.
        # Threshold must require deviation above that.
        if not has_data:
            tier = "NO_DATA"
        elif score >= 16 and ceiling_overs >= 4:
            tier = "MATCH_LOCK"
        elif score >= 12 and (ceiling_overs >= 2 or goals_signal >= 2):
            tier = "MATCH_STRONG"
        elif score <= -2 or goals_signal <= -2:
            tier = "MATCH_FADE"
        else:
            tier = "MATCH_NEUTRAL"

        rows.append({
            "match": a.get("match") or g.get("match") or g.get("matchup") or key,
            "league": a.get("league") or g.get("league"),
            "ceiling_overs": ceiling_overs,
            "goals_edge": goals_ec or None,
            "p_btts_yes": round(p_btts, 3),
            "corners_edge": corners_ec or None,
            "p_first_score": round(p_first, 3),
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "MATCH_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "MATCH_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "MATCH_FADE"),
        "method_note": "Composite soccer match score. ceiling_overs*2 + "
                       "goals_signal(3 strong OVER) + p_btts*15 + corners_signal + "
                       "first_score_lean. LOCK >= 14 with ceiling >= 4; "
                       "STRONG 8-13; FADE = score <= -2 or strong UNDER.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "MATCH_LOCK"],
        "fades": [r for r in rows if r["tier"] == "MATCH_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-confluence] {o['n_matches']} matches "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
