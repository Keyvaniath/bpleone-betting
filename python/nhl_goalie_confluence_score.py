"""
EdgeStat -- NHL goalie confluence score.

Counterpart to mlb_pitcher_confluence_score but for NHL goalies. Combines:
  - nhl_goalie_dominance_alerts (positive signals)
  - nhl_goalie_saves_props (edge_class strength)
  - nhl_goalie_win_props
  - nhl_goalie_shutout_props
  - nhl_goalie_fatigue_index (FATIGUED -> negative)

Score formula:
  positive = dom_signals * 2.5 + max(saves_edge_pp, 0)
  negative = fatigue_penalty + max(-saves_edge_pp, 0)
  score = positive - negative + 5 * p_win + 8 * p_shutout

GOALIE_LOCK = score >= 12 with dom_signals >= 3; STRONG = 8-11;
FADE = fatigued OR score <= 2.

Output: data/nhl_goalie_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_confluence_score.json")


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
    dom = _load(os.path.join(DATA_DIR, "nhl_goalie_dominance_alerts.json"))
    saves = _load(os.path.join(DATA_DIR, "nhl_goalie_saves_props.json"))
    win = _load(os.path.join(DATA_DIR, "nhl_goalie_win_props.json"))
    shutout = _load(os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))

    dom_idx = {_norm(a.get("goalie")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}
    saves_idx = {_norm(r.get("goalie") or r.get("player")): r
                 for r in (saves.get("rows") or []) if isinstance(r, dict)}
    win_idx = {_norm(r.get("goalie") or r.get("player")): r
               for r in (win.get("rows") or []) if isinstance(r, dict)}

    shutout_idx = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (shutout.get(k) or []):
            if isinstance(r, dict):
                shutout_idx.setdefault(_norm(r.get("goalie") or r.get("player")), r)

    fatigue_idx = {_norm(r.get("goalie") or r.get("player")): r
                   for r in (fatigue.get("rows") or []) if isinstance(r, dict)}

    all_goalies = set(dom_idx) | set(saves_idx) | set(win_idx) | set(shutout_idx)

    rows: List[Dict[str, Any]] = []
    for name in all_goalies:
        d = dom_idx.get(name, {})
        s = saves_idx.get(name, {})
        w = win_idx.get(name, {})
        sh = shutout_idx.get(name, {})
        f = fatigue_idx.get(name, {})

        dom_signals = int(d.get("n_positive_signals", 0) or 0)
        saves_edge_pp = _safe(s.get("edge_pp") or s.get("edge")) * 100
        p_win = _safe(w.get("p_win") or w.get("p"))
        p_shutout = _safe(sh.get("p_shutout") or sh.get("p"))
        fatigue_status = (f.get("status") or f.get("flag") or "").upper()
        fatigue_penalty = 4 if fatigue_status in ("FATIGUED", "TIRED", "BACK_TO_BACK") else 0

        positive = dom_signals * 2.5 + max(saves_edge_pp, 0)
        negative = fatigue_penalty + max(-saves_edge_pp, 0)
        score = positive - negative + 5 * p_win + 8 * p_shutout

        if score >= 12 and dom_signals >= 3:
            tier = "GOALIE_LOCK"
        elif score >= 8:
            tier = "GOALIE_STRONG"
        elif fatigue_status in ("FATIGUED", "TIRED", "BACK_TO_BACK") or score <= 2:
            tier = "GOALIE_FADE"
        else:
            tier = "GOALIE_NEUTRAL"

        rows.append({
            "goalie": (d.get("goalie") or s.get("goalie") or s.get("player")
                       or w.get("goalie") or name.title()),
            "matchup": (d.get("matchup") or s.get("matchup") or w.get("matchup") or ""),
            "team": s.get("team") or w.get("team") or d.get("team"),
            "dom_signals": dom_signals,
            "saves_edge_pp": round(saves_edge_pp, 2),
            "p_win": round(p_win, 3),
            "p_shutout": round(p_shutout, 3),
            "fatigue_status": fatigue_status or "UNKNOWN",
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_goalies": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "GOALIE_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "GOALIE_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "GOALIE_FADE"),
        "method_note": "Composite NHL goalie score: dom_signals*2.5 + saves_edge_pp "
                       "+ 5*p_win + 8*p_shutout - fatigue_penalty(4 if tired). "
                       "LOCK >= 12 with dom_signals >= 3; STRONG 8-11; "
                       "FADE = fatigued or score <= 2.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "GOALIE_LOCK"],
        "fades": [r for r in rows if r["tier"] == "GOALIE_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goalie-confluence] {o['n_goalies']} goalies "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
