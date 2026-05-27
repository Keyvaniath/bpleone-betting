"""
EdgeStat -- Tennis upset alerts.

Surfaces underdogs with positive signals (live ML value):
  - Underdog (p_match_win <= 0.40)
  - Aces OVER lean (strong serve day -> upset path)
  - Low double faults (efficiency)
  - Tiebreak likelihood (close match -> upset live)

When 3+ positive signals on an underdog, recommend their ML +
extra-game spread (covering the +6.5 / +7.5 line).

Output: data/tennis_upset_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_upset_alerts.json")


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
    aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))
    dfs = _load(os.path.join(DATA_DIR, "tennis_double_faults_props.json"))
    breaks = _load(os.path.join(DATA_DIR, "tennis_breaks_of_serve.json"))

    # Match win idx
    win_idx: Dict[str, Dict[str, Any]] = {}
    for r in (match_win.get("rows") or []):
        if isinstance(r, dict):
            win_idx[_norm(r.get("player") or "")] = r

    aces_overs: Dict[str, bool] = {}
    for r in (aces.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                aces_overs[_norm(r.get("player") or "")] = True

    df_unders: Dict[str, bool] = {}
    for r in (dfs.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "UNDER" in ec:
                df_unders[_norm(r.get("player") or "")] = True

    breaks_overs: Dict[str, bool] = {}
    for r in (breaks.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                breaks_overs[_norm(r.get("player") or "")] = True

    upsets: List[Dict[str, Any]] = []
    for name, win_data in win_idx.items():
        p_win = _safe(win_data.get("p_win") or win_data.get("p_match_win"))
        if p_win > 0.40 or p_win <= 0: continue  # only consider underdogs

        signals: List[str] = []
        if aces_overs.get(name):
            signals.append("ACES_OVER")
        if df_unders.get(name):
            signals.append("LOW_DFS_EFFICIENCY")
        if breaks_overs.get(name):
            signals.append("BREAKS_GENERATING")

        if len(signals) < 2: continue

        upsets.append({
            "player": win_data.get("player"),
            "match": win_data.get("match") or win_data.get("matchup"),
            "p_match_win": round(p_win, 3),
            "implied_odds_american": _american_from_p(p_win),
            "signals": signals,
            "n_signals": len(signals),
            "recommended_markets": [
                f"{win_data.get('player')} ML upset (+value)",
                f"{win_data.get('player')} +1.5 sets spread cover",
                "Match goes 3 sets (close)",
            ],
        })

    upsets.sort(key=lambda u: -u["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_upset_candidates": len(upsets),
        "method_note": "Tennis upset alerts. Underdogs (p_win <= 40%) with 2+ "
                       "positive signals: ACES_OVER, LOW_DFS_EFFICIENCY, "
                       "BREAKS_GENERATING. Recommends ML + spread cover plays.",
        "upsets": upsets,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


def _american_from_p(p: float):
    if p <= 0 or p >= 1: return None
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


if __name__ == "__main__":
    o = run()
    print(f"[tennis-upset] {o['n_upset_candidates']} upset candidates -> {OUT}")
