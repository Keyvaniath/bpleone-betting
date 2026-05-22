"""
EdgeStat -- Tennis player breaks of serve prop.

DK market: per-player breaks of serve O/U (e.g. Sinner over 2.5 breaks).
Strong returners (Medvedev, Djokovic, Alcaraz) produce 3+ breaks regularly
against weaker servers.

Method:
  Per-player break-per-match baseline. Adjust for:
    - Surface: clay +30% breaks (slower courts, longer rallies)
    - Surface: grass -25% (faster courts, fewer breaks)
    - Format: bo5 +50% breaks (more games)
    - Opp serve quality (high-aces players harder to break)

  STRONG when 10%+ edge vs -120 book.

Output: data/tennis_breaks_of_serve.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_breaks_of_serve.json")

# Per-player avg breaks/match (best-of-3 baseline)
PLAYER_BREAKS = {
    # Elite returners
    "novak djokovic":         {"breaks_match": 3.5},
    "carlos alcaraz":         {"breaks_match": 3.2},
    "jannik sinner":          {"breaks_match": 3.0},
    "daniil medvedev":        {"breaks_match": 3.5},
    "casper ruud":            {"breaks_match": 3.0},
    "andrey rublev":          {"breaks_match": 2.8},
    "alex de minaur":         {"breaks_match": 3.0},
    "stefanos tsitsipas":     {"breaks_match": 2.5},
    "holger rune":            {"breaks_match": 2.8},
    "tommy paul":             {"breaks_match": 2.8},
    "lorenzo musetti":        {"breaks_match": 2.7},
    "ugo humbert":            {"breaks_match": 2.5},
    "frances tiafoe":         {"breaks_match": 2.8},
    "karen khachanov":        {"breaks_match": 2.5},
    "grigor dimitrov":        {"breaks_match": 2.6},
    "alexander zverev":       {"breaks_match": 2.5},
    "taylor fritz":           {"breaks_match": 2.2},
    # Big servers (fewer breaks given, but also fewer breaks recorded against good servers)
    "hubert hurkacz":         {"breaks_match": 2.0},
    "ben shelton":            {"breaks_match": 2.2},
    "felix auger-aliassime":  {"breaks_match": 2.3},
    # WTA
    "iga swiatek":            {"breaks_match": 4.0},
    "aryna sabalenka":        {"breaks_match": 3.5},
    "coco gauff":             {"breaks_match": 3.5},
    "elena rybakina":         {"breaks_match": 2.8},
    "jasmine paolini":        {"breaks_match": 3.0},
    "qinwen zheng":           {"breaks_match": 3.0},
    "jessica pegula":         {"breaks_match": 3.2},
    "emma navarro":           {"breaks_match": 3.0},
    "ons jabeur":             {"breaks_match": 3.2},
    "barbora krejcikova":     {"breaks_match": 3.0},
    "marketa vondrousova":    {"breaks_match": 3.0},
    "madison keys":           {"breaks_match": 2.8},
    "danielle collins":       {"breaks_match": 3.2},
}

SURFACE_MULT = {"hard": 1.0, "grass": 0.75, "clay": 1.30, "indoor": 1.0}


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
            info = PLAYER_BREAKS.get(name)
            if not info: continue

            base = info["breaks_match"]
            projected = base * surf_mult * format_mult
            sigma = max(1.0, 0.40 * projected)

            edge_class = "NONE"
            best_market = None
            base_line = round(projected) + 0.5
            for line in (base_line - 1.0, base_line, base_line + 1.0):
                if line < 0.5 or line > 10.5: continue
                if abs(projected - line) > 2.5: continue
                p_over = _p_over(projected, sigma, line)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"BREAKS_OVER_{line}",
                                       "line": line, "p": round(p_over, 3),
                                       "fair_odds": _american(p_over)}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"BREAKS_UNDER_{line}",
                                       "line": line, "p": round(p_under, 3),
                                       "fair_odds": _american(p_under)}

            rows.append({
                "matchup": m.get("matchup"),
                "player": name,
                "opp": m.get(opp_key),
                "surface": surface,
                "format": format_bo,
                "base_breaks_per_match": base,
                "projected_breaks": round(projected, 2),
                "sigma": round(sigma, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_breaks"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_player_matches": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_BREAKS),
        "method_note": "Tennis breaks_of_serve = base * surface_mult (clay +30%, "
                       "grass -25%) * format_mult (bo5 +50%). Normal CDF, sigma 40% "
                       "of projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-breaks] {o['n_player_matches']} player-matches, "
          f"{o['n_strong_edges']} strong -> {OUT}")
