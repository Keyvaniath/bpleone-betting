"""
EdgeStat -- F1 driver confluence score.

Composite per-driver score combining:
  - f1_driver_dominance (n_signals)
  - f1_qualifying_predictor (p_pole, p_top3)
  - f1_podium_finish_props (p_podium, p_win)
  - f1_driver_projections (p_top10)
  - f1_track_specific (track favorable flag)

Score formula:
  score = dom_signals * 3 + p_pole * 25 + p_top3_qual * 12 + p_podium * 20
        + p_win * 30 + p_top10 * 5 + track_fav_bonus(3)

DRIVER_LOCK = score >= 22 with dom>=4
DRIVER_STRONG = 14-21
DRIVER_FADE = score <= 3

Output: data/f1_driver_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "f1_driver_confluence_score.json")


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
    dom = _load(os.path.join(DATA_DIR, "f1_driver_dominance.json"))
    qual = _load(os.path.join(DATA_DIR, "f1_qualifying_predictor.json"))
    podium = _load(os.path.join(DATA_DIR, "f1_podium_finish_props.json"))
    proj = _load(os.path.join(DATA_DIR, "f1_driver_projections.json"))
    track = _load(os.path.join(DATA_DIR, "f1_track_specific.json"))

    dom_idx = {_norm(a.get("driver")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}

    qual_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "predictions"):
        for r in (qual.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("driver") or "")
                if key and key not in qual_idx:
                    qual_idx[key] = r

    podium_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (podium.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("driver") or "")
                if key and key not in podium_idx:
                    podium_idx[key] = r

    proj_idx = {_norm(r.get("driver")): r for r in (proj.get("rows") or proj.get("drivers") or []) if isinstance(r, dict)}

    track_fav: set = set()
    for r in (track.get("rows") or track.get("drivers") or []):
        if not isinstance(r, dict): continue
        lean = (r.get("lean") or r.get("track_edge_class") or "").upper()
        if "POSITIVE" in lean or "STRONG" in lean or "FAVORABLE" in lean:
            track_fav.add(_norm(r.get("driver") or ""))

    all_drivers = (set(dom_idx) | set(qual_idx) | set(podium_idx)
                   | set(proj_idx) | track_fav)

    rows: List[Dict[str, Any]] = []
    for name in all_drivers:
        d = dom_idx.get(name, {})
        q = qual_idx.get(name, {})
        pod = podium_idx.get(name, {})
        pr = proj_idx.get(name, {})

        dom_signals = int(d.get("n_signals", 0) or 0)
        p_pole = _safe(q.get("p_pole") or q.get("p_p1"))
        p_top3_qual = _safe(q.get("p_top3") or q.get("p_q_top3"))
        p_podium = _safe(pod.get("p_podium") or pod.get("p"))
        p_win = _safe(pod.get("p_win") or pod.get("p_p1"))
        p_top10 = _safe(pr.get("p_top10") or pr.get("p_points"))
        track_bonus = 3 if name in track_fav else 0

        score = (dom_signals * 3
                 + p_pole * 25
                 + p_top3_qual * 12
                 + p_podium * 20
                 + p_win * 30
                 + p_top10 * 5
                 + track_bonus)

        has_data = (dom_signals > 0 or p_pole > 0 or p_podium > 0
                    or p_win > 0 or p_top10 > 0 or track_bonus > 0)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 22 and dom_signals >= 4:
            tier = "DRIVER_LOCK"
        elif score >= 14:
            tier = "DRIVER_STRONG"
        elif score <= 3:
            tier = "DRIVER_FADE"
        else:
            tier = "DRIVER_NEUTRAL"

        rows.append({
            "driver": (d.get("driver") or q.get("driver") or pod.get("driver")
                       or pr.get("driver") or name.title()),
            "race": d.get("race") or pr.get("race") or pr.get("event"),
            "dom_signals": dom_signals,
            "p_pole": round(p_pole, 3),
            "p_qual_top3": round(p_top3_qual, 3),
            "p_podium": round(p_podium, 3),
            "p_win": round(p_win, 3),
            "p_top10": round(p_top10, 3),
            "track_favorable": name in track_fav,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_drivers": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "DRIVER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "DRIVER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "DRIVER_FADE"),
        "method_note": "Composite F1 driver score. dom_signals*3 + p_pole*25 + "
                       "p_qual_top3*12 + p_podium*20 + p_win*30 + p_top10*5 + "
                       "track_fav_bonus(3). LOCK >= 22 with dom>=4; STRONG 14-21.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "DRIVER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "DRIVER_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f1-confluence] {o['n_drivers']} drivers "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
