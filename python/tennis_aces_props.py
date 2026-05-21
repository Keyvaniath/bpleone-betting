"""
EdgeStat -- Tennis player aces total O/U prop.

Common DK lines: per-player aces O/U (e.g. Sinner over 7.5 aces).
Big-server props are especially common in men's events.

Method:
  Per-player avg aces/match (tour-specific). Adjust for:
    - Match length (bo3 default, bo5 adds ~50%)
    - Surface (grass +25%, hard 0, clay -20%)
    - Opponent return-game quality (poor returners = more aces)

  Normal CDF at nearest 1.0 line within 3.0 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/tennis_aces_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_aces_props.json")

# Per-player avg aces per match (best-of-3 baseline)
PLAYER_ACES = {
    # ATP big servers
    "jannik sinner":         {"aces_match": 7.5},
    "carlos alcaraz":        {"aces_match": 5.5},
    "alexander zverev":      {"aces_match": 9.2},
    "daniil medvedev":       {"aces_match": 5.8},
    "novak djokovic":        {"aces_match": 5.5},
    "taylor fritz":          {"aces_match": 8.5},
    "casper ruud":           {"aces_match": 5.0},
    "andrey rublev":         {"aces_match": 5.2},
    "stefanos tsitsipas":    {"aces_match": 5.5},
    "alex de minaur":        {"aces_match": 4.5},
    "grigor dimitrov":       {"aces_match": 6.0},
    "hubert hurkacz":        {"aces_match": 12.5},
    "tommy paul":            {"aces_match": 5.5},
    "ben shelton":           {"aces_match": 11.5},
    "frances tiafoe":        {"aces_match": 6.5},
    "jack draper":           {"aces_match": 7.0},
    "ugo humbert":           {"aces_match": 7.0},
    "lorenzo musetti":       {"aces_match": 3.8},
    "holger rune":           {"aces_match": 5.5},
    "karen khachanov":       {"aces_match": 8.5},
    "alejandro davidovich fokina": {"aces_match": 4.2},
    "alexei popyrin":        {"aces_match": 9.5},
    "felix auger-aliassime": {"aces_match": 9.5},
    "sebastian baez":        {"aces_match": 2.5},
    "arthur fils":           {"aces_match": 6.8},
    # WTA big servers
    "aryna sabalenka":       {"aces_match": 4.5},
    "iga swiatek":           {"aces_match": 3.0},
    "coco gauff":            {"aces_match": 4.0},
    "elena rybakina":        {"aces_match": 7.5},
    "jasmine paolini":       {"aces_match": 2.5},
    "qinwen zheng":          {"aces_match": 4.0},
    "jessica pegula":        {"aces_match": 3.0},
    "barbora krejcikova":    {"aces_match": 3.5},
    "emma navarro":          {"aces_match": 2.5},
    "danielle collins":      {"aces_match": 3.5},
    "daria kasatkina":       {"aces_match": 2.0},
    "paula badosa":          {"aces_match": 3.0},
    "mirra andreeva":        {"aces_match": 2.0},
    "marketa vondrousova":   {"aces_match": 3.0},
    "diana shnaider":        {"aces_match": 3.0},
    "madison keys":          {"aces_match": 6.5},
    "elina svitolina":       {"aces_match": 2.5},
    "ons jabeur":            {"aces_match": 3.5},
    "amanda anisimova":      {"aces_match": 3.5},
    "anna kalinskaya":       {"aces_match": 2.0},
    "donna vekic":           {"aces_match": 3.5},
    "victoria azarenka":     {"aces_match": 3.0},
    "karolina muchova":      {"aces_match": 3.5},
    "yulia putintseva":      {"aces_match": 2.5},
    "elise mertens":         {"aces_match": 2.5},
}

SURFACE_MULT = {"hard": 1.0, "grass": 1.25, "clay": 0.80}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


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

        for p_key, p_name_key, opp_key in (("p1", "p1", "p2"), ("p2", "p2", "p1")):
            name = (m.get(p_name_key) or "").lower()
            opp_name = (m.get(opp_key) or "").lower()
            info = PLAYER_ACES.get(name)
            if not info: continue

            base_aces = info["aces_match"]
            # Opp return quality proxy: top servers themselves are usually average returners
            # Default: 1.0. Adjust if opp is known weak returner (big server type)
            opp_info = PLAYER_ACES.get(opp_name)
            opp_serve_quality = opp_info["aces_match"] if opp_info else 5.0
            # High-serving opponents -> less time on return -> roughly neutral
            opp_return_factor = 1.0  # simplification — could add per-player return stats

            projected_aces = base_aces * surf_mult * format_mult * opp_return_factor

            # Sigma: serve variance ~ 2.5-3.5 aces
            sigma = max(2.8, 0.30 * projected_aces)

            edge_class = "NONE"
            best_market = None
            base_line = round(projected_aces) + 0.5
            for line_int in (base_line - 2, base_line - 1, base_line, base_line + 1, base_line + 2):
                line = line_int
                if line < 1.5 or line > 25.5: continue
                if abs(projected_aces - line) > 3.0: continue
                p_over = _p_over(projected_aces, sigma, line)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"ACES_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"ACES_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": m.get("matchup"),
                "player": name,
                "opp": opp_name,
                "surface": surface,
                "format": format_bo,
                "base_aces_per_match": base_aces,
                "surface_mult": surf_mult,
                "format_mult": format_mult,
                "projected_aces": round(projected_aces, 2),
                "sigma": round(sigma, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_aces"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_player_matches": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_ACES),
        "method_note": "Tennis player_aces = base x surface_mult (grass +25%, clay -20%) "
                       "x format_mult (bo5 +50%). Normal CDF, sigma 30% of projection. "
                       "STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-aces] {o['n_player_matches']} player-matches, {o['n_strong_edges']} strong edges -> {OUT}")
