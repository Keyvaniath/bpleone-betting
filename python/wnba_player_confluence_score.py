"""
EdgeStat -- WNBA player confluence score.

Counterpart to nba_player_confluence_score. Composite per-WNBA-player
score combining:
  - wnba_player_ceiling_stack (n_aligned_overs)
  - wnba_player_heat (HOT/COLD)
  - wnba_player_pts_props (edge_class)
  - wnba_player_double_double (p_dd)
  - wnba_player_20plus_pts_alt (p_20plus)

Score formula:
  score = ceiling_overs * 2 + form_score + pts_edge_pp + p_dd*10 + p_20*15

PLAYER_LOCK = score >= 10 with ceiling >= 4;
PLAYER_STRONG = 6-9;
PLAYER_FADE = score <= -2 or strongly negative form.

Output: data/wnba_player_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_confluence_score.json")


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
    ceiling = _load(os.path.join(DATA_DIR, "wnba_player_ceiling_stack.json"))
    heat = _load(os.path.join(DATA_DIR, "wnba_player_heat.json"))
    pts = _load(os.path.join(DATA_DIR, "wnba_player_pts_props.json"))
    dd = _load(os.path.join(DATA_DIR, "wnba_player_double_double.json"))
    pts_20 = _load(os.path.join(DATA_DIR, "wnba_player_20plus_pts_alt.json"))

    ceiling_idx = {_norm(a.get("player")): a for a in (ceiling.get("alerts") or []) if isinstance(a, dict)}

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "cold", "heating_up", "cooling_down", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    pts_idx = {_norm(r.get("player")): r for r in (pts.get("rows") or []) if isinstance(r, dict)}
    dd_idx = {_norm(r.get("player")): r for r in (dd.get("rows") or []) if isinstance(r, dict)}

    pts20_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (pts_20.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts20_idx:
                    pts20_idx[key] = _safe(r.get("p_20plus") or r.get("p"))

    all_players = (set(ceiling_idx) | set(heat_idx) | set(pts_idx)
                   | set(dd_idx) | set(pts20_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_players:
        c = ceiling_idx.get(name, {})
        h_trend = heat_idx.get(name, "")
        p = pts_idx.get(name, {})
        d = dd_idx.get(name, {})
        p_20 = pts20_idx.get(name, 0)

        ceiling_overs = int(c.get("n_aligned_overs", 0) or 0)
        pts_edge_pp = _safe(p.get("edge_pp") or p.get("edge")) * 100
        p_dd = _safe(d.get("p_dd") or d.get("p"))

        form_score = 0
        if "HOT" in h_trend or "HEATING" in h_trend:
            form_score = 2
        elif "COLD" in h_trend or "COOLING" in h_trend:
            form_score = -2

        positive = ceiling_overs * 2 + max(form_score, 0) + max(pts_edge_pp, 0) + p_dd * 10 + p_20 * 15
        negative = max(-form_score, 0) + max(-pts_edge_pp, 0)
        score = positive - negative

        has_data = (ceiling_overs > 0 or h_trend or pts_edge_pp != 0
                    or p_dd > 0 or p_20 > 0)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 10 and ceiling_overs >= 4:
            tier = "PLAYER_LOCK"
        elif score >= 6:
            tier = "PLAYER_STRONG"
        elif score <= -2 or form_score < 0:
            tier = "PLAYER_FADE"
        else:
            tier = "PLAYER_NEUTRAL"

        rows.append({
            "player": (c.get("player") or p.get("player") or d.get("player")
                       or name.title()),
            "team": c.get("team") or p.get("team") or d.get("team"),
            "matchup": (c.get("matchup") or p.get("matchup") or d.get("matchup")
                        or ""),
            "ceiling_overs": ceiling_overs,
            "pts_edge_pp": round(pts_edge_pp, 2),
            "p_dd": round(p_dd, 3),
            "p_20plus": round(p_20, 3),
            "form": h_trend or None,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "PLAYER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "PLAYER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "PLAYER_FADE"),
        "method_note": "Composite WNBA player score. ceiling_overs*2 + form_score "
                       "+ pts_edge_pp + p_dd*10 + p_20plus*15. LOCK >= 10 with "
                       "ceiling >= 4; STRONG 6-9; FADE = score <= -2 or cold form.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "PLAYER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "PLAYER_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-confluence] {o['n_players']} players "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
