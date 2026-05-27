"""
EdgeStat -- NHL skater same-game parlay (SGP) builder.

For each NHL skater with confluence_score >= 8 (STRONG+), builds the
recommended SGP from their OVER signals:
  - SOG OVER (if signaled)
  - 3+ SOG YES (if p >= 45%)
  - Points OVER (if signaled)
  - 2+ Points YES (if p >= 32%)
  - Anytime Goal YES (if p_atg >= 22%)
  - Hits+Blocks OVER (if signaled)

Apply 1.10x correlation boost (less than NBA's 1.15x since hits/SOG/
goals are slightly less correlated than NBA's scoring metrics).

Output: data/nhl_skater_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_sgp_builder.json")


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


def _is_over(ec: str) -> bool:
    return "OVER" in (ec or "").upper()


def run() -> Dict[str, Any]:
    confluence = _load(os.path.join(DATA_DIR, "nhl_skater_confluence_score.json"))
    sog = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    sog_3 = _load(os.path.join(DATA_DIR, "nhl_skater_3plus_sog.json"))
    pts = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))
    pts_2 = _load(os.path.join(DATA_DIR, "nhl_skater_2plus_points.json"))
    atg = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    hits = _load(os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json"))

    def _idx(src):
        return {_norm(r.get("player") or r.get("skater")): r
                for r in (src.get("rows") or []) if isinstance(r, dict)}

    sog_idx = _idx(sog)
    pts_idx = _idx(pts)
    hits_idx = _idx(hits)

    sog3_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (sog_3.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in sog3_idx:
                    sog3_idx[key] = _safe(r.get("p_3plus_sog") or r.get("p"))

    pts2_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (pts_2.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in pts2_idx:
                    pts2_idx[key] = _safe(r.get("p_2plus_points") or r.get("p"))

    atg_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (atg.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in atg_idx:
                    atg_idx[key] = _safe(r.get("p_atg") or r.get("p"))

    parlays: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 8: continue

        name = _norm(r.get("skater") or "")
        legs: List[Dict[str, Any]] = []

        if _is_over(sog_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "SOG OVER", "p": 0.55})

        p_sog3 = sog3_idx.get(name, 0)
        if p_sog3 >= 0.45:
            legs.append({"market": "3+ SOG YES", "p": round(p_sog3, 3)})

        if _is_over(pts_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "Points OVER", "p": 0.54})

        p_pts2 = pts2_idx.get(name, 0)
        if p_pts2 >= 0.32:
            legs.append({"market": "2+ Points YES", "p": round(p_pts2, 3)})

        p_atg = atg_idx.get(name, 0)
        if p_atg >= 0.22:
            legs.append({"market": "Anytime Goal YES", "p": round(p_atg, 3)})

        if _is_over(hits_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "Hits+Blocks OVER", "p": 0.55})

        if len(legs) < 2: continue

        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        parlay_p_corr = min(parlay_p_naive * 1.10, 0.99)

        parlays.append({
            "skater": r.get("skater"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "confluence_score": round(score, 2),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
            "advisory": "Same-player NHL SGP. SOG/Goal/Points are positively "
                        "correlated -> apply 1.10x boost to naive parlay p.",
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "NHL skater SGP builder. Confluence >= 8 + OVER signals "
                       "across SOG/3+SOG/Points/2+Points/ATG/Hits+Blocks. "
                       "1.10x correlation boost applied.",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-skater-sgp] {o['n_parlays']} SGP builds -> {OUT}")
