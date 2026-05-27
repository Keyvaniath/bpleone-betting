"""
EdgeStat -- Soccer clean sheet alignment alerts.

Inverse of high_scoring_alignment. Surfaces matches where multiple
LOW-scoring signals align:
  - p_btts_yes <= 0.45 (BTTS NO likely)
  - total goals UNDER lean (STRONG_UNDER preferred)
  - p_first_score_either <= 0.50 (no early goal)
  - low p_clean_sheet_team (favorite for clean sheet)
  - elite defense team in matchup

When 3+ align, recommend:
  - BTTS NO
  - Total Goals UNDER (1.5 or 2.5)
  - Clean Sheet (favorite team)
  - 0-0 / 1-0 correct score boost

Output: data/soccer_clean_sheet_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_clean_sheet_alignment.json")


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
    clean_sheet = _load(os.path.join(DATA_DIR, "soccer_clean_sheet_props.json"))

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

    cs_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (clean_sheet.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                p_cs = _safe(r.get("p_clean_sheet") or r.get("p"))
                existing = cs_idx.get(key)
                if not existing or p_cs > existing.get("p_clean_sheet", 0):
                    cs_idx[key] = {"team": r.get("team"), "p_clean_sheet": p_cs}

    all_matches = set(btts_idx) | set(goals_idx) | set(fs_idx) | set(cs_idx)

    alignments: List[Dict[str, Any]] = []
    for key in all_matches:
        signals: Dict[str, int] = {}
        p_btts = btts_idx.get(key, 1)
        signals["BTTS_NO_LIKELY"] = 1 if 0 < p_btts <= 0.45 else 0

        goals_ec = (goals_idx.get(key, {}).get("edge_class") or "").upper()
        signals["GOALS_STRONG_UNDER"] = 1 if "STRONG_UNDER" in goals_ec else 0
        signals["GOALS_UNDER_LEAN"] = 1 if "UNDER" in goals_ec and "STRONG" not in goals_ec else 0

        p_first = fs_idx.get(key, 1)
        signals["LOW_EARLY_SCORE"] = 1 if 0 < p_first <= 0.50 else 0

        cs_info = cs_idx.get(key, {})
        p_cs = cs_info.get("p_clean_sheet", 0)
        signals["CLEAN_SHEET_LIVE"] = 1 if p_cs >= 0.35 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "CLEAN_SHEET_LOCK"
        else:
            tier = "LOW_SCORING_LEAN"

        alignments.append({
            "match": (goals_idx.get(key, {}).get("match")
                      or goals_idx.get(key, {}).get("matchup") or key),
            "league": goals_idx.get(key, {}).get("league"),
            "p_btts_yes": round(p_btts, 3),
            "goals_edge": goals_ec or None,
            "p_first_score": round(p_first, 3),
            "clean_sheet_team": cs_info.get("team"),
            "p_clean_sheet": round(p_cs, 3),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_parlay": [
                "BTTS NO",
                "Total Goals UNDER",
                (f"{cs_info.get('team')} Clean Sheet YES"
                 if cs_info.get("team") else ""),
                "Under 1.5 First Half Goals" if signals.get("LOW_EARLY_SCORE") else "",
            ],
        })

    alignments.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "n_clean_sheet_lock": sum(1 for a in alignments
                                  if a["tier"] == "CLEAN_SHEET_LOCK"),
        "method_note": "Inverse of high_scoring_alignment. 3+ signals: "
                       "BTTS_NO_LIKELY (<=45%), GOALS_STRONG_UNDER, "
                       "LOW_EARLY_SCORE (p_either <=50%), CLEAN_SHEET_LIVE "
                       "(>=35%). CLEAN_SHEET_LOCK = 4+ signals.",
        "alignments": alignments,
        "clean_sheet_locks": [a for a in alignments
                              if a["tier"] == "CLEAN_SHEET_LOCK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-clean-sheet] {o['n_alignments']} alignments "
          f"({o['n_clean_sheet_lock']} LOCK) -> {OUT}")
