"""
EdgeStat -- MLB pitcher 1st-inning earned run yes/no prop.

Common DK line: "Pitcher to allow ER in 1st inning yes/no"
Typical book: YES +180 to +250 (29-36% breakeven), NO -250 to -150.

Method:
  Each half-inning of a starter ~ 4.5 PA. Expected ER in 1st inning =
    expected_runs_in_first_half_inning
    = LEAGUE_R_PER_PA * PA_in_first * pitcher_ER_per_9_factor * lineup_quality

  P(>= 1 ER) = 1 - exp(-expected_ER)

  STRONG_YES when our P(ER) >= 0.40 (vs +150 book = 40% breakeven)
  STRONG_NO when our P(ER) <= 0.20 (vs -300 book = 75% on NO)

Output: data/mlb_pitcher_1st_inning_er.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_er.json")

LEAGUE_ERA = 4.20
PA_IN_FIRST = 4.5


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_row = p_by_name.get(sp_name.lower(), {})
            stats = sp_row.get("stats") or {}
            era = _safe(stats.get("era"), LEAGUE_ERA)
            # Pitcher ER-per-9 factor: 4.20 league avg
            er_factor = era / LEAGUE_ERA

            # Lineup quality proxy from game-level OPS (opposing side)
            opp_side_key = "away" if side == "HOME" else "home"
            opp_lineup_ops = _safe((g.get(opp_side_key) or {}).get("ops"), 0.72)
            lineup_mult = max(0.80, min(1.20, 1.0 + (opp_lineup_ops - 0.72) * 0.8))

            # Expected runs in 1st half-inning
            # League: ~0.55 R/half-inning. Scale by ER factor & lineup
            base_er_per_inning = LEAGUE_ERA / 9.0  # ~0.467 ER per inning
            expected_er = base_er_per_inning * er_factor * lineup_mult
            p_er = 1 - math.exp(-expected_er)
            p_no_er = 1 - p_er

            edge_class = "NONE"
            best_market = None
            if 0.40 <= p_er <= 0.55:
                edge_class = "STRONG_YES"
                best_market = {"market": "1ST_INN_ER_YES", "p": round(p_er, 3),
                               "fair_odds": _american(p_er)}
            elif p_no_er >= 0.80:
                edge_class = "STRONG_NO"
                best_market = {"market": "1ST_INN_ER_NO", "p": round(p_no_er, 3),
                               "fair_odds": _american(p_no_er)}

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "pitcher_era": era,
                "er_factor": round(er_factor, 3),
                "opp_lineup_ops": opp_lineup_ops,
                "lineup_mult": round(lineup_mult, 3),
                "expected_er_first_inning": round(expected_er, 3),
                "p_er": round(p_er, 3),
                "p_no_er": round(p_no_er, 3),
                "fair_yes_odds": _american(p_er),
                "fair_no_odds": _american(p_no_er),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_er"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(1st-inning ER) = 1 - exp(-pitcher_ERA/9 * lineup_mult). "
                       "STRONG_YES at p in [0.40, 0.55] (vs +150 book = 40%), "
                       "STRONG_NO at p_no >= 0.80 (vs -400 book = 80%).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-inn-er] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
