"""
EdgeStat -- Tennis match dominance alerts.

Counterpart to mlb_dominant_outing_alerts / nhl_goalie_dominance_alerts
but for tennis matches. Surfaces players projected for elite outings:
  - MATCH_WIN_HIGH (p_match_win >= 70%)
  - 1ST_SET_WIN (p_1st_set_win >= 65%)
  - STRAIGHT_SETS_LEAN (3-0 / 2-0 set score lean)
  - ACES_OVER
  - LOW_DOUBLE_FAULTS (UNDER lean)
  - BREAKS_OF_SERVE_OVER (winning vol)

DOMINANCE_ELITE = 5+ signals; STRONG = 3-4.

Output: data/tennis_dominance_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_dominance_alerts.json")


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
    match_win = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    set1 = _load(os.path.join(DATA_DIR, "tennis_1st_set_winner.json"))
    set_score = _load(os.path.join(DATA_DIR, "tennis_set_score_props.json"))
    aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))
    dfs = _load(os.path.join(DATA_DIR, "tennis_double_faults_props.json"))
    breaks = _load(os.path.join(DATA_DIR, "tennis_breaks_of_serve.json"))

    players: Dict[str, Dict[str, Any]] = {}

    def _entry(player_name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(player_name)
        if not key: return {}
        return players.setdefault(key, {
            "player": player_name,
            "match": r.get("match") or r.get("matchup"),
            "signals": {},
            "scores": {},
        })

    # Match win
    for r in (match_win.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or r.get("favorite") or ""
        entry = _entry(name, r)
        if not entry: continue
        p_win = _safe(r.get("p_win") or r.get("p_match_win"))
        entry["signals"]["MATCH_WIN_HIGH"] = 1 if p_win >= 0.70 else 0
        entry["scores"]["MATCH_WIN_HIGH"] = round(p_win, 3)

    # 1st set
    for r in (set1.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or r.get("favorite") or ""
        entry = _entry(name, r)
        if not entry: continue
        p_1st = _safe(r.get("p_1st_set") or r.get("p_set1_win"))
        entry["signals"]["1ST_SET_WIN"] = 1 if p_1st >= 0.65 else 0
        entry["scores"]["1ST_SET_WIN"] = round(p_1st, 3)

    # Set score (straight sets lean)
    for k in ("rows", "strong_edges"):
        for r in (set_score.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or r.get("favorite") or ""
            entry = _entry(name, r)
            if not entry: continue
            # Best straight-sets prob across markets
            p_2_0 = _safe(r.get("p_2_0"))
            p_3_0 = _safe(r.get("p_3_0"))
            best = max(p_2_0, p_3_0)
            entry["signals"]["STRAIGHT_SETS_LEAN"] = 1 if best >= 0.30 else 0
            entry["scores"]["STRAIGHT_SETS_LEAN"] = round(best, 3)

    # Aces over
    for r in (aces.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or ""
        entry = _entry(name, r)
        if not entry: continue
        ec = (r.get("edge_class") or "").upper()
        entry["signals"]["ACES_OVER"] = 1 if "OVER" in ec else 0

    # Double faults UNDER (low DF is positive signal)
    for r in (dfs.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or ""
        entry = _entry(name, r)
        if not entry: continue
        ec = (r.get("edge_class") or "").upper()
        entry["signals"]["LOW_DFS"] = 1 if "UNDER" in ec else 0

    # Breaks of serve OVER (offense generating breaks)
    for r in (breaks.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or ""
        entry = _entry(name, r)
        if not entry: continue
        ec = (r.get("edge_class") or "").upper()
        entry["signals"]["BREAKS_OVER"] = 1 if "OVER" in ec else 0

    alerts: List[Dict[str, Any]] = []
    for key, entry in players.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        tier = "DOMINANCE_ELITE" if n >= 5 else "DOMINANCE_STRONG"
        alerts.append({
            "player": entry["player"],
            "match": entry["match"],
            "n_signals": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "DOMINANCE_ELITE"),
        "method_note": "Tennis counterpart to MLB/NHL dominance synthesizers. "
                       "Surfaces players with 3+ aligned signals (MATCH_WIN_HIGH, "
                       "1ST_SET_WIN, STRAIGHT_SETS_LEAN, ACES_OVER, LOW_DFS, "
                       "BREAKS_OVER). DOMINANCE_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_dominance": [a for a in alerts if a["tier"] == "DOMINANCE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-dominance] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
