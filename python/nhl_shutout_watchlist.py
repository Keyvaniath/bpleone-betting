"""
EdgeStat -- NHL goalie shutout watchlist.

Surfaces NHL goalies with EXTREME dominance signals where a shutout is
statistically more likely:
  - Confluence score >= 14 (top tier)
  - p_shutout >= 12%
  - p_win >= 55%
  - 30+ saves YES probability >= 60%
  - Not fatigued

Output: data/nhl_shutout_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_shutout_watchlist.json")


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
    confluence = _load(os.path.join(DATA_DIR, "nhl_goalie_confluence_score.json"))
    shutout = _load(os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json"))
    win = _load(os.path.join(DATA_DIR, "nhl_goalie_win_props.json"))
    saves_30 = _load(os.path.join(DATA_DIR, "nhl_goalie_30plus_saves.json"))

    shutout_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (shutout.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("goalie") or r.get("player") or "")
                if key and key not in shutout_idx:
                    shutout_idx[key] = _safe(r.get("p_shutout") or r.get("p"))

    win_idx = {_norm(r.get("goalie") or r.get("player")): _safe(r.get("p_win") or r.get("p"))
               for r in (win.get("rows") or []) if isinstance(r, dict)}

    saves30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (saves_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("goalie") or r.get("player") or "")
                if key and key not in saves30_idx:
                    saves30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    watchlist: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 14: continue

        name = _norm(r.get("goalie") or "")
        p_so = shutout_idx.get(name, 0)
        p_win = win_idx.get(name, 0)
        p_30 = saves30_idx.get(name, 0)
        fatigue_status = (r.get("fatigue_status") or "").upper()

        if p_so < 0.12: continue
        if p_win < 0.55: continue
        if p_30 < 0.60: continue
        if fatigue_status in ("FATIGUED", "TIRED", "BACK_TO_BACK"): continue

        watchlist.append({
            "goalie": r.get("goalie"),
            "matchup": r.get("matchup"),
            "team": r.get("team"),
            "composite_score": round(score, 2),
            "p_shutout": round(p_so, 3),
            "p_win": round(p_win, 3),
            "p_30plus_saves": round(p_30, 3),
            "fatigue_status": fatigue_status or "RESTED",
            "advisory": "Elite shutout spot. Recommended bets: shutout YES "
                        "(typical 6-1 to 12-1), 30+ saves + win + shutout "
                        "parlay.",
            "recommended_markets": [
                "Goalie shutout YES",
                "Saves OVER + win YES + shutout YES (parlay)",
                "Opp 0 goals YES",
            ],
        })

    watchlist.sort(key=lambda w: -w["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "NHL shutout watchlist. Strict criteria: confluence_score "
                       ">= 14 + p_shutout >= 12% + p_win >= 55% + p_30plus_saves "
                       ">= 60% + not fatigued. NHL shutouts ~5-10% historically.",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-shutout] {o['n_watchlist']} on watchlist -> {OUT}")
