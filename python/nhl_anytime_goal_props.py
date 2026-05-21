"""
EdgeStat -- NHL anytime goalscorer prop projections.

Common DK line: Player to score a goal yes/no (-150 to +600 depending on
team/role/matchup). One of the most-bet hockey props.

Method:
  P(scores >= 1) = 1 - exp(-expected_goals_for_player)
  expected_goals = season_gpg * opp_goalie_factor * pace_factor

Per-player goals-per-game baseline (top NHL scorers).

Output: data/nhl_anytime_goal_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_anytime_goal_props.json")

# 2024-25 NHL top scorers (goals per game)
PLAYER_DB = {
    "auston matthews":     {"team": "TOR", "gpg": 0.70},
    "leon draisaitl":      {"team": "EDM", "gpg": 0.65},
    "alex ovechkin":       {"team": "WSH", "gpg": 0.62},
    "nikita kucherov":     {"team": "TBL", "gpg": 0.55},
    "david pastrnak":      {"team": "BOS", "gpg": 0.58},
    "sam reinhart":        {"team": "FLA", "gpg": 0.55},
    "matthew tkachuk":     {"team": "FLA", "gpg": 0.42},
    "connor mcdavid":      {"team": "EDM", "gpg": 0.55},
    "william nylander":    {"team": "TOR", "gpg": 0.52},
    "kirill kaprizov":     {"team": "MIN", "gpg": 0.55},
    "elias pettersson":    {"team": "VAN", "gpg": 0.42},
    "jt miller":           {"team": "VAN", "gpg": 0.40},
    "mikko rantanen":      {"team": "COL", "gpg": 0.55},
    "nathan mackinnon":    {"team": "COL", "gpg": 0.55},
    "sidney crosby":       {"team": "PIT", "gpg": 0.40},
    "evgeni malkin":       {"team": "PIT", "gpg": 0.38},
    "brad marchand":       {"team": "BOS", "gpg": 0.42},
    "elias lindholm":      {"team": "BOS", "gpg": 0.30},
    "tim stutzle":         {"team": "OTT", "gpg": 0.40},
    "brady tkachuk":       {"team": "OTT", "gpg": 0.45},
    "filip forsberg":      {"team": "NSH", "gpg": 0.45},
    "patrik laine":        {"team": "MTL", "gpg": 0.42},
    "jack hughes":         {"team": "NJD", "gpg": 0.50},
    "nico hischier":       {"team": "NJD", "gpg": 0.42},
    "artemi panarin":      {"team": "NYR", "gpg": 0.42},
    "chris kreider":       {"team": "NYR", "gpg": 0.45},
    "mika zibanejad":      {"team": "NYR", "gpg": 0.42},
    "anze kopitar":        {"team": "LAK", "gpg": 0.35},
    "kevin fiala":         {"team": "LAK", "gpg": 0.38},
    "jack eichel":         {"team": "VGK", "gpg": 0.42},
    "mark stone":          {"team": "VGK", "gpg": 0.40},
    "alex debrincat":      {"team": "DET", "gpg": 0.50},
    "dylan larkin":        {"team": "DET", "gpg": 0.40},
    "joel eriksson ek":    {"team": "MIN", "gpg": 0.35},
    "matt boldy":          {"team": "MIN", "gpg": 0.42},
    "vincent trocheck":    {"team": "NYR", "gpg": 0.32},
    "andrei svechnikov":   {"team": "CAR", "gpg": 0.40},
    "sebastian aho":       {"team": "CAR", "gpg": 0.42},
    "tage thompson":       {"team": "BUF", "gpg": 0.50},
    "jt compher":          {"team": "DET", "gpg": 0.30},
    "anze kopitar":        {"team": "LAK", "gpg": 0.32},
    "carter verhaeghe":    {"team": "FLA", "gpg": 0.40},
    "aleksander barkov":   {"team": "FLA", "gpg": 0.40},
}

# Goalie SV% factors (lower SV% = more goals against)
# Default 0.910; 0.920+ elite (reduces P score by ~5-8%), 0.895 weak (boosts ~10%)
GOALIE_SV = {
    "sergei bobrovsky": 0.916, "andrei vasilevskiy": 0.917, "connor hellebuyck": 0.921,
    "igor shesterkin": 0.917, "jeremy swayman": 0.910, "stuart skinner": 0.907,
    "linus ullmark": 0.910, "anthony stolarz": 0.926, "thatcher demko": 0.914,
    "frederik andersen": 0.928, "jake oettinger": 0.911, "juuse saros": 0.908,
    "logan thompson": 0.918, "adin hill": 0.911,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue
        teams_in_game = set([home, away, home[:3], away[:3]])

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in teams_in_game: continue
            is_home = info["team"] == home or info["team"] == home[:3]

            base_gpg = info["gpg"]
            # Opp goalie factor: 0.910 SV% baseline; higher SV% reduces expected goals
            # Simplification: scale by 1 - opp_sv_pct / 1 - 0.910 = goals_above_average
            opp_sv = 0.910  # default
            opp_goalie_mult = (1 - opp_sv) / (1 - 0.910)
            expected_goals = base_gpg * opp_goalie_mult
            p_scores = 1 - math.exp(-expected_goals)
            p_no_goal = 1 - p_scores

            edge_class = "NONE"
            best_market = None
            # Top scorers: book ~ -110 (52%%) to -150 (60%%). STRONG_YES at 60-72%%.
            if 0.60 <= p_scores <= 0.72:
                edge_class = "STRONG_YES"
                best_market = {"market": "ANYTIME_GOAL_YES", "p": round(p_scores, 3),
                               "fair_odds": _american(p_scores)}
            elif p_scores <= 0.20:
                edge_class = "STRONG_NO"
                best_market = {"market": "ANYTIME_GOAL_NO", "p": round(p_no_goal, 3),
                               "fair_odds": _american(p_no_goal)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "season_gpg": base_gpg,
                "expected_goals": round(expected_goals, 3),
                "p_scores": round(p_scores, 3),
                "p_no_goal": round(p_no_goal, 3),
                "fair_yes": _american(p_scores),
                "fair_no": _american(p_no_goal),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_scores"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "P(score) = 1 - exp(-GPG × opp_goalie_factor). "
                       "STRONG_YES 60-72%% (vs typical book -150 for top scorers). "
                       "STRONG_NO when expected GPG very low for active player.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goal] {o['n_players_projected']} players, {o['n_strong']} strong -> {OUT}")
