"""
EdgeStat -- NHL skater confluence score.

Composite per-skater score combining:
  - nhl_skater_ceiling_stack (n_aligned_overs)
  - nhl_skater_matchup_adjusted (delta SOG / pts)
  - nhl_anytime_goal_props (p_atg)
  - nhl_skater_sog_props (edge_class)
  - nhl_skater_points_props (edge_class)

Score formula:
  positive = ceiling_overs * 2 + max(delta_sog, 0) * 4 + p_atg * 30
            + sog_over_signal + pts_over_signal
  negative = max(-delta_sog, 0) * 4 + sog_under_signal + pts_under_signal
  score = positive - negative

SKATER_LOCK = score >= 12 with ceiling >= 3; STRONG = 8-11.

Output: data/nhl_skater_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_confluence_score.json")


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
    ceiling = _load(os.path.join(DATA_DIR, "nhl_skater_ceiling_stack.json"))
    matchup_adj = _load(os.path.join(DATA_DIR, "nhl_skater_matchup_adjusted.json"))
    atg = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    sog = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    pts = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))

    ceiling_idx = {_norm(a.get("player")): a for a in (ceiling.get("alerts") or []) if isinstance(a, dict)}
    matchup_idx = {_norm(r.get("skater") or r.get("player")): r
                   for r in (matchup_adj.get("rows") or []) if isinstance(r, dict)}

    atg_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (atg.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in atg_idx:
                    atg_idx[key] = _safe(r.get("p_atg") or r.get("p"))

    sog_idx = {_norm(r.get("player") or r.get("skater")): r
               for r in (sog.get("rows") or []) if isinstance(r, dict)}
    pts_idx = {_norm(r.get("player") or r.get("skater")): r
               for r in (pts.get("rows") or []) if isinstance(r, dict)}

    all_skaters = (set(ceiling_idx) | set(matchup_idx) | set(atg_idx)
                   | set(sog_idx) | set(pts_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_skaters:
        c = ceiling_idx.get(name, {})
        m = matchup_idx.get(name, {})
        p_atg = atg_idx.get(name, 0)
        sr = sog_idx.get(name, {})
        pr = pts_idx.get(name, {})

        ceiling_overs = int(c.get("n_aligned_overs", 0) or 0)
        delta_sog = _safe((m.get("delta") or {}).get("sog"))
        sog_edge_class = (sr.get("edge_class") or "").upper()
        pts_edge_class = (pr.get("edge_class") or "").upper()

        sog_over = 1 if "OVER" in sog_edge_class else 0
        sog_under = 1 if "UNDER" in sog_edge_class else 0
        pts_over = 1 if "OVER" in pts_edge_class else 0
        pts_under = 1 if "UNDER" in pts_edge_class else 0

        positive = (ceiling_overs * 2 + max(delta_sog, 0) * 4 + p_atg * 30
                    + sog_over * 1.5 + pts_over * 1.5)
        negative = (max(-delta_sog, 0) * 4 + sog_under * 1.5 + pts_under * 1.5)
        score = positive - negative

        if score >= 12 and ceiling_overs >= 3:
            tier = "SKATER_LOCK"
        elif score >= 8:
            tier = "SKATER_STRONG"
        elif score <= 2:
            tier = "SKATER_FADE"
        else:
            tier = "SKATER_NEUTRAL"

        rows.append({
            "skater": (c.get("player") or m.get("skater") or sr.get("player")
                       or pr.get("player") or name.title()),
            "team": c.get("team") or m.get("team") or sr.get("team"),
            "matchup": (c.get("matchup") or m.get("matchup") or sr.get("matchup")
                        or ""),
            "ceiling_overs": ceiling_overs,
            "delta_sog_matchup": round(delta_sog, 2),
            "p_atg": round(p_atg, 3),
            "sog_edge_class": sog_edge_class or None,
            "pts_edge_class": pts_edge_class or None,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "SKATER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "SKATER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "SKATER_FADE"),
        "method_note": "Composite NHL skater score. ceiling_overs*2 + "
                       "max(delta_sog,0)*4 + p_atg*30 + sog_over*1.5 + "
                       "pts_over*1.5 - max(-delta_sog,0)*4 - "
                       "sog_under*1.5 - pts_under*1.5. LOCK >= 12 with "
                       "ceiling >= 3; STRONG 8-11.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "SKATER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "SKATER_FADE"],
        "top_25": rows[:25],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[skater-confluence] {o['n_skaters']} skaters "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
