"""
EdgeStat -- NHL goalie save parlay builder.

For each goalie with confluence_score >= 8 (STRONG+), builds the
recommended multi-leg saves parlay:
  Leg 1: saves OVER
  Leg 2: 30+ saves YES (if p >= 60%)
  Leg 3: win YES (if p >= 55%)
  Leg 4: shutout LIVE (if p >= 12%)

Computes implied probability for parlay = product of leg p's.
Recommended Kelly stake at 25% Kelly fraction.

Output: data/nhl_goalie_save_parlay_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_save_parlay_builder.json")


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


def _american_from_p(p: float):
    if p <= 0 or p >= 1: return None
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    confluence = _load(os.path.join(DATA_DIR, "nhl_goalie_confluence_score.json"))
    saves_30 = _load(os.path.join(DATA_DIR, "nhl_goalie_30plus_saves.json"))
    win = _load(os.path.join(DATA_DIR, "nhl_goalie_win_props.json"))
    shutout = _load(os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json"))

    # Probability indexes by goalie
    saves30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (saves_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("goalie") or r.get("player") or "")
                if key and key not in saves30_idx:
                    saves30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    win_idx = {_norm(r.get("goalie") or r.get("player")): _safe(r.get("p_win") or r.get("p"))
               for r in (win.get("rows") or []) if isinstance(r, dict)}

    shutout_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (shutout.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("goalie") or r.get("player") or "")
                if key and key not in shutout_idx:
                    shutout_idx[key] = _safe(r.get("p_shutout") or r.get("p"))

    parlays: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 8: continue

        name = _norm(r.get("goalie") or "")
        legs: List[Dict[str, Any]] = []

        # Leg 1: saves OVER (assume baseline 52% probability from dom_signals)
        p_saves_over = 0.52 if score >= 8 else 0.50
        legs.append({
            "market": "Saves OVER",
            "p": round(p_saves_over, 3),
            "implied_odds": _american_from_p(p_saves_over),
        })

        # Leg 2: 30+ saves YES
        p_30 = saves30_idx.get(name, 0)
        if p_30 >= 0.60:
            legs.append({
                "market": "30+ Saves YES",
                "p": round(p_30, 3),
                "implied_odds": _american_from_p(p_30),
            })

        # Leg 3: Win YES
        p_win = win_idx.get(name, 0)
        if p_win >= 0.55:
            legs.append({
                "market": "Win YES",
                "p": round(p_win, 3),
                "implied_odds": _american_from_p(p_win),
            })

        # Leg 4: Shutout LIVE
        p_so = shutout_idx.get(name, 0)
        if p_so >= 0.12:
            legs.append({
                "market": "Shutout YES",
                "p": round(p_so, 3),
                "implied_odds": _american_from_p(p_so),
            })

        if len(legs) < 2: continue

        # Parlay implied prob = product (assume independence)
        parlay_p = 1.0
        for leg in legs:
            parlay_p *= leg["p"]

        kelly_size = max(parlay_p - (1 / 3.0), 0) * 0.25  # conservative quarter-Kelly

        parlays.append({
            "goalie": r.get("goalie"),
            "matchup": r.get("matchup"),
            "team": r.get("team"),
            "confluence_score": round(score, 2),
            "confluence_tier": r.get("tier"),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p": round(parlay_p, 4),
            "parlay_implied_odds": _american_from_p(parlay_p),
            "kelly_25pct_stake_pct": round(kelly_size * 100, 2),
        })

    parlays.sort(key=lambda p: -p["parlay_p"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "NHL goalie saves multi-leg parlay builder. Requires goalie "
                       "confluence_score >= 8 + applicable thresholds: 30+ saves "
                       "p >= 60%, win p >= 55%, shutout p >= 12%. Parlay_p = "
                       "product of leg p's (assumes independence). Kelly 25% "
                       "fractional stake recommendation.",
        "parlays": parlays,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-save-parlay] {o['n_parlays']} parlay builds -> {OUT}")
