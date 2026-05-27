"""
EdgeStat -- NHL goalie dominance alerts.

NHL counterpart to mlb_dominant_outing_alerts. Surfaces goalies projecting
for an elite outing -- aligned positive signals:
  - SAVES_OVER (high save projection)
  - 30PLUS_SAVES_YES (workload + skill = >=30 saves)
  - WIN_YES (team favored)
  - SHUTOUT_LIVE (shutout probability >= 12%)
  - LOW_GA (goals allowed < 2.5)
  - FATIGUE_OK (not on back-to-back / not overworked)

DOMINANCE_ELITE = 5+ aligned signals; DOMINANCE_STRONG = 3-4 signals.
Strong basis for multi-leg goalie parlay (saves OVER + win + 30+ saves).

Output: data/nhl_goalie_dominance_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_dominance_alerts.json")


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
    saves = _load(os.path.join(DATA_DIR, "nhl_goalie_saves_props.json"))
    saves_30 = _load(os.path.join(DATA_DIR, "nhl_goalie_30plus_saves.json"))
    win = _load(os.path.join(DATA_DIR, "nhl_goalie_win_props.json"))
    shutout = _load(os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))

    # Index by goalie name
    saves_idx = {_norm(r.get("goalie") or r.get("player")): r
                 for r in (saves.get("rows") or []) if isinstance(r, dict)}
    saves30_idx = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (saves_30.get(k) or []):
            if isinstance(r, dict):
                saves30_idx.setdefault(_norm(r.get("goalie") or r.get("player")), r)
    win_idx = {_norm(r.get("goalie") or r.get("player")): r
               for r in (win.get("rows") or []) if isinstance(r, dict)}
    shutout_idx = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (shutout.get(k) or []):
            if isinstance(r, dict):
                shutout_idx.setdefault(_norm(r.get("goalie") or r.get("player")), r)
    fatigue_idx = {_norm(r.get("goalie") or r.get("player")): r
                   for r in (fatigue.get("rows") or []) if isinstance(r, dict)}

    all_goalies = set(saves_idx.keys()) | set(win_idx.keys())
    alerts: List[Dict[str, Any]] = []

    for name in all_goalies:
        sr = saves_idx.get(name, {})
        sr30 = saves30_idx.get(name, {})
        wr = win_idx.get(name, {})
        shr = shutout_idx.get(name, {})
        fr = fatigue_idx.get(name, {})

        signals: Dict[str, int] = {}
        signals["SAVES_OVER"] = 1 if "OVER" in (sr.get("edge_class") or "").upper() else 0
        p_30 = _safe(sr30.get("p_30plus") or sr30.get("p"))
        signals["30PLUS_SAVES_YES"] = 1 if p_30 >= 0.55 else 0
        p_win = _safe(wr.get("p_win") or wr.get("p"))
        signals["WIN_YES"] = 1 if p_win >= 0.55 else 0
        p_so = _safe(shr.get("p_shutout") or shr.get("p"))
        signals["SHUTOUT_LIVE"] = 1 if p_so >= 0.12 else 0
        # Low GA derived from expected saves and shot vol
        exp_saves = _safe(sr.get("expected_saves") or sr.get("proj_saves"))
        signals["LOW_GA_PROJ"] = 1 if exp_saves >= 28 else 0
        # Fatigue OK = no back-to-back and not flagged FATIGUED
        fatigue_status = (fr.get("status") or fr.get("flag") or "").upper()
        signals["FATIGUE_OK"] = 1 if fatigue_status in ("", "FRESH", "RESTED", "OK") else 0

        positive_count = sum(1 for v in signals.values() if v == 1)
        if positive_count < 3: continue

        goalie_display = (sr.get("goalie") or sr.get("player")
                          or wr.get("goalie") or wr.get("player") or name.title())
        matchup = sr.get("matchup") or wr.get("matchup") or ""

        alerts.append({
            "goalie": goalie_display,
            "matchup": matchup,
            "team": sr.get("team") or wr.get("team"),
            "expected_saves": round(exp_saves, 1) if exp_saves else None,
            "p_30plus_saves": round(p_30, 3),
            "p_win": round(p_win, 3),
            "p_shutout": round(p_so, 3),
            "fatigue_status": fatigue_status or "UNKNOWN",
            "n_positive_signals": positive_count,
            "signals": signals,
            "tier": "DOMINANCE_ELITE" if positive_count >= 5 else "DOMINANCE_STRONG",
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "DOMINANCE_ELITE"),
        "method_note": "NHL counterpart to mlb_dominant_outing_alerts. Surfaces "
                       "goalies with 3+ aligned positive signals (SAVES_OVER, "
                       "30PLUS_SAVES_YES, WIN_YES, SHUTOUT_LIVE, LOW_GA_PROJ, "
                       "FATIGUE_OK). DOMINANCE_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_dominance": [a for a in alerts if a["tier"] == "DOMINANCE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-dominance] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
