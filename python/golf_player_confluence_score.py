"""
EdgeStat -- Golf player confluence score.

Composite per-golfer score combining:
  - golf_player_dominance (n_signals)
  - golf_top_finish_props (p_top5, p_top10)
  - golf_leaderboard_probability (p_leader)
  - golf_makecut (p_make_cut)
  - golf_round_score_props (UNDER lean = lower scores = positive)
  - golf_player_heat (HOT flag)

Score formula:
  score = dom_signals * 2.5 + p_top5 * 40 + p_top10 * 20 + p_leader * 60
        + p_make_cut * 5 + round_under_lean * 3 + hot_bonus(3)

PLAYER_LOCK = score >= 18 with dom>=4
PLAYER_STRONG = 11-17
PLAYER_FADE = score <= 4

Output: data/golf_player_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_player_confluence_score.json")


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
    dom = _load(os.path.join(DATA_DIR, "golf_player_dominance.json"))
    top_finish = _load(os.path.join(DATA_DIR, "golf_top_finish_props.json"))
    leaderboard = _load(os.path.join(DATA_DIR, "golf_leaderboard_probability.json"))
    make_cut = _load(os.path.join(DATA_DIR, "golf_makecut.json"))
    rounds = _load(os.path.join(DATA_DIR, "golf_round_score_props.json"))
    heat = _load(os.path.join(DATA_DIR, "golf_player_heat.json"))

    dom_idx = {_norm(a.get("player")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}

    top_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (top_finish.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in top_idx:
                    top_idx[key] = r

    lead_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (leaderboard.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in lead_idx:
                    lead_idx[key] = _safe(r.get("p_leader") or r.get("p_top1"))

    cut_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (make_cut.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in cut_idx:
                    cut_idx[key] = _safe(r.get("p_make_cut") or r.get("p_cut"))

    round_idx = {_norm(r.get("player")): r for r in (rounds.get("rows") or []) if isinstance(r, dict)}

    hot_players: set = set()
    for k in ("hot", "hot_players"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                hot_players.add(_norm(r.get("player") or ""))
            elif isinstance(r, str):
                hot_players.add(_norm(r))

    all_players = (set(dom_idx) | set(top_idx) | set(lead_idx)
                   | set(cut_idx) | set(round_idx) | hot_players)

    rows: List[Dict[str, Any]] = []
    for name in all_players:
        d = dom_idx.get(name, {})
        tr = top_idx.get(name, {})
        p_lead = lead_idx.get(name, 0)
        p_cut = cut_idx.get(name, 0)
        rr = round_idx.get(name, {})

        dom_signals = int(d.get("n_signals", 0) or 0)
        p_top5 = _safe(tr.get("p_top5"))
        p_top10 = _safe(tr.get("p_top10"))

        round_ec = (rr.get("edge_class") or "").upper()
        round_under_lean = 1 if "UNDER" in round_ec else 0  # lower scores = positive
        hot_bonus = 3 if name in hot_players else 0

        score = (dom_signals * 2.5
                 + p_top5 * 40
                 + p_top10 * 20
                 + p_lead * 60
                 + p_cut * 5
                 + round_under_lean * 3
                 + hot_bonus)

        has_data = (dom_signals > 0 or p_top5 > 0 or p_lead > 0
                    or p_cut > 0 or round_under_lean > 0 or hot_bonus > 0)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 18 and dom_signals >= 4:
            tier = "PLAYER_LOCK"
        elif score >= 11:
            tier = "PLAYER_STRONG"
        elif score <= 4:
            tier = "PLAYER_FADE"
        else:
            tier = "PLAYER_NEUTRAL"

        rows.append({
            "player": (d.get("player") or tr.get("player") or rr.get("player")
                       or name.title()),
            "tournament": d.get("tournament") or tr.get("tournament"),
            "dom_signals": dom_signals,
            "p_top5": round(p_top5, 3),
            "p_top10": round(p_top10, 3),
            "p_leader": round(p_lead, 3),
            "p_make_cut": round(p_cut, 3),
            "round_under_lean": bool(round_under_lean),
            "hot": name in hot_players,
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
        "method_note": "Composite golf player score. dom_signals*2.5 + p_top5*40 + "
                       "p_top10*20 + p_leader*60 + p_make_cut*5 + round_under_lean*3 "
                       "+ hot_bonus(3). LOCK >= 18 with dom>=4; STRONG 11-17.",
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
    print(f"[golf-confluence] {o['n_players']} players "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
