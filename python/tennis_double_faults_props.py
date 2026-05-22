"""
EdgeStat -- Tennis player double faults total O/U prop.

DK markets: per-player double faults O/U (e.g. Medvedev over 2.5 DFs).
Inverse signal vs aces — risky 2nd serves and mental break candidates
produce DFs.

Method:
  Per-player avg DFs per match. Adjust for:
    - Match length (bo5 adds ~50%)
    - Surface (clay +20% DFs from harder kicks, grass -10% from quicker points)
    - Pressure context (deciding-set ITV markets see DF rates spike)
  Sigma calibrated tighter than aces (~1.0-1.5 DFs).

  STRONG when 10%+ edge vs -120 book.

Output: data/tennis_double_faults_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_double_faults_props.json")

# DFs per match (best-of-3 baseline). Higher = more error-prone server.
PLAYER_DFS = {
    # ATP
    "jannik sinner":         {"dfs_match": 2.0},
    "carlos alcaraz":        {"dfs_match": 3.0},
    "alexander zverev":      {"dfs_match": 3.8},
    "daniil medvedev":       {"dfs_match": 1.8},
    "novak djokovic":        {"dfs_match": 1.5},
    "taylor fritz":          {"dfs_match": 2.5},
    "casper ruud":           {"dfs_match": 2.0},
    "andrey rublev":         {"dfs_match": 3.2},
    "stefanos tsitsipas":    {"dfs_match": 3.5},
    "holger rune":           {"dfs_match": 3.5},
    "alex de minaur":        {"dfs_match": 1.8},
    "ben shelton":           {"dfs_match": 3.5},
    "tommy paul":            {"dfs_match": 2.2},
    "lorenzo musetti":       {"dfs_match": 2.8},
    "felix auger-aliassime": {"dfs_match": 3.5},
    "ugo humbert":           {"dfs_match": 2.5},
    "frances tiafoe":        {"dfs_match": 3.0},
    "karen khachanov":       {"dfs_match": 2.5},
    "grigor dimitrov":       {"dfs_match": 2.2},
    "hubert hurkacz":        {"dfs_match": 2.0},
    "alejandro davidovich fokina": {"dfs_match": 4.0},
    # WTA
    "iga swiatek":           {"dfs_match": 2.5},
    "aryna sabalenka":       {"dfs_match": 4.5},
    "coco gauff":            {"dfs_match": 5.0},
    "elena rybakina":        {"dfs_match": 2.8},
    "jasmine paolini":       {"dfs_match": 2.0},
    "qinwen zheng":          {"dfs_match": 3.5},
    "jessica pegula":        {"dfs_match": 2.0},
    "emma navarro":          {"dfs_match": 2.5},
    "diana shnaider":        {"dfs_match": 3.0},
    "ons jabeur":            {"dfs_match": 2.5},
    "barbora krejcikova":    {"dfs_match": 2.5},
    "danielle collins":      {"dfs_match": 3.5},
    "madison keys":          {"dfs_match": 4.0},
    "marketa vondrousova":   {"dfs_match": 2.5},
}

SURFACE_MULT = {"hard": 1.0, "grass": 0.9, "clay": 1.2, "indoor": 1.0}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    matches = state.get("rows") or []

    rows: List[Dict[str, Any]] = []
    for m in matches:
        surface = (m.get("surface") or "hard").lower()
        surf_mult = SURFACE_MULT.get(surface, 1.0)
        format_bo = m.get("format") or "bo3"
        format_mult = 1.50 if format_bo == "bo5" else 1.0

        for p_key, opp_key in (("p1", "p2"), ("p2", "p1")):
            name = (m.get(p_key) or "").lower()
            info = PLAYER_DFS.get(name)
            if not info: continue

            base_dfs = info["dfs_match"]
            projected = base_dfs * surf_mult * format_mult
            sigma = max(1.0, 0.35 * projected)

            edge_class = "NONE"
            best_market = None
            base_line = round(projected) + 0.5
            for line in (base_line - 1.0, base_line, base_line + 1.0):
                if line < 0.5 or line > 10.5: continue
                if abs(projected - line) > 2.0: continue
                p_over = _p_over(projected, sigma, line)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"DFS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"DFS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": m.get("matchup"),
                "player": name,
                "opp": m.get(opp_key),
                "surface": surface,
                "format": format_bo,
                "base_dfs_per_match": base_dfs,
                "projected_dfs": round(projected, 2),
                "sigma": round(sigma, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_dfs"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_player_matches": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DFS),
        "method_note": "Tennis double faults = base x surface_mult (clay +20%, "
                       "grass -10%) x format_mult (bo5 +50%). Normal CDF, sigma 35% of "
                       "projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-df] {o['n_player_matches']} player-matches, "
          f"{o['n_strong_edges']} strong -> {OUT}")
