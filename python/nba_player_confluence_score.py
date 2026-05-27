"""
EdgeStat -- NBA player confluence score.

Counterpart to mlb_pitcher_confluence_score but for NBA players. Combines:
  - nba_player_ceiling_stack (n_aligned_overs)
  - nba_player_under_fade (n_aligned_unders, subtracts)
  - nba_player_matchup_adjusted (pts/reb/ast deltas)
  - nba_player_heat (HOT/COLD form classification)
  - nba_player_points_props (edge_class strength)

Score formula:
  positive = ceiling_overs * 2 + max(form_score,0) + max(matchup_delta_pts,0)*1.5
  negative = under_fades * 2 + max(-form_score,0) + max(-matchup_delta_pts,0)*1.5
  score = pts_edge + positive - negative

PLAYER_LOCK = score >= 8 with secondary; STRONG = 5-7; FADE = score <= -3
or 4+ under_fades.

Output: data/nba_player_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_confluence_score.json")


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
    ceiling = _load(os.path.join(DATA_DIR, "nba_player_ceiling_stack.json"))
    fade = _load(os.path.join(DATA_DIR, "nba_player_under_fade.json"))
    matchup_adj = _load(os.path.join(DATA_DIR, "nba_player_matchup_adjusted.json"))
    heat = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))

    ceiling_idx = {_norm(a.get("player")): a for a in (ceiling.get("alerts") or []) if isinstance(a, dict)}
    fade_idx = {_norm(a.get("player")): a for a in (fade.get("alerts") or []) if isinstance(a, dict)}
    matchup_idx = {_norm(r.get("player")): r for r in (matchup_adj.get("rows") or []) if isinstance(r, dict)}

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "cold", "heating_up", "cooling_down", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("player") or "")] = (r.get("trend") or k).upper()

    pts_idx = {_norm(r.get("player")): r for r in (pts.get("rows") or []) if isinstance(r, dict)}

    all_players = (set(ceiling_idx) | set(fade_idx) | set(matchup_idx)
                   | set(heat_idx) | set(pts_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_players:
        c = ceiling_idx.get(name, {})
        f = fade_idx.get(name, {})
        m = matchup_idx.get(name, {})
        h_trend = heat_idx.get(name, "")
        p = pts_idx.get(name, {})

        ceiling_overs = int(c.get("n_aligned_overs", 0) or 0)
        under_fades = int(f.get("n_aligned_unders", 0) or 0)
        delta_pts = _safe((m.get("delta") or {}).get("pts"))
        pts_edge_pp = _safe(p.get("edge_pp") or p.get("edge")) * 100

        # Heat trend score
        form_score = 0
        if "HOT" in h_trend or "HEATING" in h_trend:
            form_score = 1
        elif "COLD" in h_trend or "COOLING" in h_trend:
            form_score = -1

        positive = ceiling_overs * 2 + max(form_score, 0) + max(delta_pts, 0) * 1.5
        negative = under_fades * 2 + max(-form_score, 0) + max(-delta_pts, 0) * 1.5
        score = pts_edge_pp + positive - negative

        if score >= 8 and (ceiling_overs >= 3 or form_score > 0 or delta_pts >= 1.0):
            tier = "PLAYER_LOCK"
        elif score >= 5:
            tier = "PLAYER_STRONG"
        elif score <= -3 or under_fades >= 4:
            tier = "PLAYER_FADE"
        else:
            tier = "PLAYER_NEUTRAL"

        rows.append({
            "player": (c.get("player") or f.get("player") or m.get("player")
                       or p.get("player") or name.title()),
            "team": c.get("team") or f.get("team") or m.get("team") or p.get("team"),
            "matchup": (c.get("matchup") or f.get("matchup") or m.get("matchup")
                        or p.get("matchup") or ""),
            "ceiling_overs": ceiling_overs,
            "under_fades": under_fades,
            "delta_pts_matchup": round(delta_pts, 2),
            "form": h_trend or None,
            "pts_edge_pp": round(pts_edge_pp, 2),
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
        "method_note": "Composite NBA player score: pts_edge_pp + ceiling_overs*2 - "
                       "under_fades*2 + form_score + delta_pts_matchup*1.5. "
                       "LOCK >= 8 with secondary signal; STRONG 5-7; FADE <= -3 or "
                       "4+ under_fades.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "PLAYER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "PLAYER_FADE"],
        "top_25": rows[:25],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-player-confluence] {o['n_players']} players "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
