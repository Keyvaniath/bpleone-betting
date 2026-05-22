"""
EdgeStat -- MLB pitcher first-inning strikeout yes/no prop.

Companion to mlb_pitcher_1st_inning_er. Popular DK alt: "Pitcher to record K
in first inning yes/no".

Typical pricing:
  - High-K starters (Skubal, Skenes, Wheeler): -150 to -120 YES
  - Average starters: +100 to +130
  - Contact-pitch starters: +200+

Method:
  expected_K_first = (k_per_9 / 9) * 3 (3 outs in first inning).
  P(at least 1 K) = 1 - (1 - K_rate)^batters_faced.
  Or via Poisson(lam = expected_K_first).

  STRONG_YES at p in [0.62, 0.78] (vs -150 book = 60% breakeven)
  STRONG_NO at p_no in [0.40, 0.55] (vs +130 NO breakeven = 43.5%)

Output: data/mlb_pitcher_1st_inning_k.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_k.json")

LEAGUE_K9 = 8.5


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


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        # Lineup OPS proxy for K-rate adjustment (good lineups K less)
        for side, sp_field, lineup_field in (
            ("HOME", "home_pitcher", "away"),
            ("AWAY", "away_pitcher", "home")
        ):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_row = p_by_name.get(sp_name.lower(), {})
            stats = sp_row.get("stats") or {}
            k9 = _safe(stats.get("k_per_9"), LEAGUE_K9)

            # Adjust for opposing lineup K-rate (high-K lineups boost expected K)
            opp_ops = _safe((g.get(lineup_field) or {}).get("ops"), 0.72)
            # Worse-OPS lineups have more strikeouts (more K-prone)
            opp_k_mult = max(0.85, min(1.20, 1.0 + (0.72 - opp_ops) * 0.6))

            # K per inning (1 inning = K9 / 9), adjusted for opposing lineup K-rate.
            # Average pitcher K9=8.5 -> 0.94 K/inning; ace 11+ K9 -> 1.2+ K/inning.
            expected_k_first = (k9 / 9.0) * opp_k_mult
            p_at_least_1k = _poisson_at_least(1, expected_k_first)
            p_at_least_2k = _poisson_at_least(2, expected_k_first)
            p_no_k = 1 - p_at_least_1k

            edge_class = "NONE"
            best_market = None
            if 0.62 <= p_at_least_1k <= 0.78:
                edge_class = "STRONG_YES"
                best_market = {"market": "1ST_INN_K_YES",
                               "p": round(p_at_least_1k, 3),
                               "fair_odds": _american(p_at_least_1k)}
            elif 0.40 <= p_no_k <= 0.55:
                edge_class = "STRONG_NO"
                best_market = {"market": "1ST_INN_K_NO",
                               "p": round(p_no_k, 3),
                               "fair_odds": _american(p_no_k)}

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "k_per_9": round(k9, 2),
                "opp_lineup_ops": opp_ops,
                "opp_k_mult": round(opp_k_mult, 3),
                "expected_k_first_inning": round(expected_k_first, 3),
                "p_1plus_k": round(p_at_least_1k, 3),
                "p_2plus_k": round(p_at_least_2k, 3),
                "p_no_k": round(p_no_k, 3),
                "fair_yes": _american(p_at_least_1k),
                "fair_no": _american(p_no_k),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_1plus_k"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(1+ K in first inn) = 1 - exp(-lam) where lam = "
                       "(K9/9)*3 * opp_K_mult. STRONG_YES p in [0.62, 0.78] vs "
                       "-150 book; STRONG_NO p_no in [0.40, 0.55] vs +130 NO.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-k] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
