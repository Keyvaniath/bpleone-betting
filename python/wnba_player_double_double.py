"""
EdgeStat -- WNBA player double-double yes/no prop.

A double-double = 10+ in two of (PTS, REB, AST, STL, BLK).
Common DK lines: -200 for elite bigs (A'ja Wilson, Brionna Jones), +200 to
+400 for most guards and role players.

Method:
  Mirror of nba_double_double_props but tuned for WNBA pace/spread:
  - 40-min game (vs NBA 48)
  - Lower PPG ceiling (28 vs 32+)
  - Bonferroni-style joint probability over (PTS, REB, AST) marginals

Player pool: 2024-25 WNBA top DD candidates (A'ja Wilson, Napheesa Collier,
Alyssa Thomas, Aliyah Boston etc).

Output: data/wnba_player_double_double.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from wnba_scoring_env import game_env_factor


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_double_double.json")

LEAGUE_PACE_WNBA = 78.0

# 2024-25 WNBA top double-double producers
PLAYER_DB = {
    "a'ja wilson":          {"team": "LVA", "ppg": 26.8, "rpg": 11.9, "apg": 2.5},
    "aja wilson":           {"team": "LVA", "ppg": 26.8, "rpg": 11.9, "apg": 2.5},  # alias
    "napheesa collier":     {"team": "MIN", "ppg": 23.8, "rpg": 9.5,  "apg": 3.7},
    "alyssa thomas":        {"team": "CON", "ppg": 14.0, "rpg": 9.0,  "apg": 8.0},
    "aliyah boston":        {"team": "IND", "ppg": 14.0, "rpg": 8.9,  "apg": 3.0},
    "brionna jones":        {"team": "CON", "ppg": 14.0, "rpg": 9.0,  "apg": 1.5},
    "angel reese":          {"team": "CHI", "ppg": 13.6, "rpg": 13.1, "apg": 1.9},
    "ezi magbegor":         {"team": "SEA", "ppg": 13.0, "rpg": 7.5,  "apg": 1.5},
    "satou sabally":        {"team": "DAL", "ppg": 18.0, "rpg": 6.5,  "apg": 3.0},
    "breanna stewart":      {"team": "NYL", "ppg": 20.4, "rpg": 8.5,  "apg": 3.5},
    "jonquel jones":        {"team": "NYL", "ppg": 14.0, "rpg": 8.6,  "apg": 2.5},
    "nneka ogwumike":       {"team": "SEA", "ppg": 17.0, "rpg": 7.0,  "apg": 2.5},
    "rhyne howard":         {"team": "ATL", "ppg": 18.0, "rpg": 4.5,  "apg": 3.5},
    "kelsey plum":          {"team": "LAS", "ppg": 17.8, "rpg": 2.6,  "apg": 4.2},
    "jewell loyd":          {"team": "LAS", "ppg": 18.0, "rpg": 3.0,  "apg": 3.8},
    "sabrina ionescu":      {"team": "NYL", "ppg": 19.0, "rpg": 4.5,  "apg": 6.2},
    "caitlin clark":        {"team": "IND", "ppg": 19.2, "rpg": 5.7,  "apg": 8.4},
    "paige bueckers":       {"team": "DAL", "ppg": 21.0, "rpg": 4.5,  "apg": 5.0},
    "kahleah copper":       {"team": "PHX", "ppg": 21.0, "rpg": 4.5,  "apg": 2.5},
    "kayla mcbride":        {"team": "MIN", "ppg": 15.0, "rpg": 3.2,  "apg": 3.5},
    "courtney vandersloot": {"team": "CHI", "ppg": 9.0,  "rpg": 3.0,  "apg": 7.5},
    "natasha cloud":        {"team": "PHX", "ppg": 11.0, "rpg": 4.5,  "apg": 6.0},
    "skylar diggins":       {"team": "SEA", "ppg": 18.0, "rpg": 4.0,  "apg": 6.0},
    "arike ogunbowale":     {"team": "DAL", "ppg": 23.0, "rpg": 4.0,  "apg": 4.7},
    "kelsey mitchell":      {"team": "IND", "ppg": 19.0, "rpg": 2.0,  "apg": 2.5},
    "diana taurasi":        {"team": "PHX", "ppg": 14.0, "rpg": 3.5,  "apg": 4.5},
}


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


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _p_at_least(target: float, mean: float, sigma: float) -> float:
    """P(X >= target) via Normal approximation."""
    if sigma <= 0: return 1.0 if mean >= target else 0.0
    z = (target - 0.5 - mean) / sigma  # continuity correction
    return 1 - _norm_cdf(z)


def _norm_team(t: str) -> str:
    """Normalize team to standard abbreviation."""
    if not t: return ""
    full_to_abbr = {
        "las vegas aces": "LVA", "minnesota lynx": "MIN", "connecticut sun": "CON",
        "indiana fever": "IND", "chicago sky": "CHI", "seattle storm": "SEA",
        "dallas wings": "DAL", "new york liberty": "NYL", "atlanta dream": "ATL",
        "los angeles sparks": "LAS", "phoenix mercury": "PHX", "washington mystics": "WAS",
    }
    return full_to_abbr.get(t.lower().strip(), t[:3].upper())


def run() -> Dict[str, Any]:
    # WNBA games live in wnba_state.json, not matchups.json
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _norm_team(g.get("home_team") or g.get("home") or "")
        away = _norm_team(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue
        matchup = f"{away} @ {home}"
        # live scoring-environment factor from real results (was a 1.0 stub)
        pace_factor, _env = game_env_factor(g.get("home_team") or "", g.get("away_team") or "")

        # Find all PLAYER_DB members whose team matches either side
        candidate_players = [(name, info) for name, info in PLAYER_DB.items()
                             if info["team"] in (home, away)]

        for name, db_row in candidate_players:
            if name == "aja wilson": continue  # skip alias dupe
            ppg = db_row["ppg"] * pace_factor
            rpg = db_row["rpg"] * pace_factor
            apg = db_row["apg"] * pace_factor

            # Sigmas calibrated for WNBA (lower than NBA)
            sig_pts = max(3.0, 0.30 * ppg)
            sig_reb = max(2.0, 0.35 * rpg)
            sig_ast = max(1.5, 0.40 * apg)

            p_pts10 = _p_at_least(10, ppg, sig_pts)
            p_reb10 = _p_at_least(10, rpg, sig_reb)
            p_ast10 = _p_at_least(10, apg, sig_ast)

            # P(DD) ≈ P(any pair both >= 10) via inclusion-exclusion
            p_pr = p_pts10 * p_reb10
            p_pa = p_pts10 * p_ast10
            p_ra = p_reb10 * p_ast10
            p_pra = p_pts10 * p_reb10 * p_ast10
            p_dd = p_pr + p_pa + p_ra - 2 * p_pra
            p_dd = max(0.005, min(0.95, p_dd))
            p_no_dd = 1 - p_dd

            edge_class = "NONE"
            best_market = None
            if 0.65 <= p_dd <= 0.85:
                edge_class = "STRONG_YES"
                best_market = {"market": "DD_YES", "p": round(p_dd, 3),
                               "fair_odds": _american(p_dd)}
            elif 0.80 <= p_no_dd <= 0.93:
                edge_class = "STRONG_NO"
                best_market = {"market": "DD_NO", "p": round(p_no_dd, 3),
                               "fair_odds": _american(p_no_dd)}

            rows.append({
                "matchup": matchup,
                "player": name.title(),
                "team": db_row["team"],
                "ppg": ppg,
                "rpg": rpg,
                "apg": apg,
                "p_pts10": round(p_pts10, 3),
                "p_reb10": round(p_reb10, 3),
                "p_ast10": round(p_ast10, 3),
                "p_dd": round(p_dd, 3),
                "p_no_dd": round(p_no_dd, 3),
                "fair_yes_odds": _american(p_dd),
                "fair_no_odds": _american(p_no_dd),
                "edge_class": edge_class,
                "best_market": best_market,
                "dd_source": "fallback",
            })

    rows.sort(key=lambda r: -r["p_dd"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "WNBA double-double = 10+ in 2+ of (PTS, REB, AST). "
                       "Inclusion-exclusion on marginal Normal CDF. "
                       "STRONG_YES p in [0.65, 0.85] (vs -200 book = 66.7%); "
                       "STRONG_NO p_no in [0.80, 0.93] (vs +180 book on NO).",
        "rows": rows,
        "top_15_by_p_dd": rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-dd] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
