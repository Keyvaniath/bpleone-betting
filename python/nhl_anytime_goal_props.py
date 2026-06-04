"""
EdgeStat -- NHL anytime goalscorer prop projections.

Common DK line: Player to score a goal yes/no (-150 to +600 depending on
team/role/matchup). One of the most-bet hockey props.

Method:
  P(scores >= 1) = 1 - exp(-expected_goals_for_player)
  expected_goals = season_gpg * opp_goalie_factor
  opp_goalie_factor = (1 - opp_starter_SV%) / (1 - league_SV%)   [clamped 0.70..1.30]

The opposing starter's save percentage is the dominant driver of whether a goal
gets scored, so we resolve it per game from TEAM_GOALIE -> GOALIE_SV (league-avg
fallback when unmapped). Per-player goals-per-game baseline (top NHL scorers).

Output: data/nhl_anytime_goal_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from nhl_teams import abbr as _abbr   # shared full-name -> abbrev resolver


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
    "logan thompson": 0.918, "adin hill": 0.911, "pyotr kochetkov": 0.911,
}
LEAGUE_SV = 0.910

# Each team's #1 starter -> resolves the OPPOSING goalie's SV% from GOALIE_SV.
# Unmapped teams fall back to LEAGUE_SV (neutral). Refreshed as starters change.
TEAM_GOALIE = {
    "FLA": "sergei bobrovsky", "TBL": "andrei vasilevskiy", "WPG": "connor hellebuyck",
    "NYR": "igor shesterkin", "BOS": "jeremy swayman", "EDM": "stuart skinner",
    "OTT": "linus ullmark", "TOR": "anthony stolarz", "VAN": "thatcher demko",
    "CAR": "frederik andersen", "DAL": "jake oettinger", "NSH": "juuse saros",
    "WSH": "logan thompson", "VGK": "adin hill",
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
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_team = away if is_home else home

            # Real ESPN goals/game with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nhl", player_name, "goals_per_game", fallback=info["gpg"], min_games=5)
                base_gpg = stat["value"]
                gpg_source = stat["source"]
            except Exception:
                base_gpg = info["gpg"]
                gpg_source = "fallback"
            # Opposing starter's REAL SV% drives the goal environment: an elite
            # goalie (.928) suppresses ~20%, a weak one (.895) boosts ~17%. Falls
            # back to league-average SV% when the opponent's starter is unmapped.
            opp_goalie = TEAM_GOALIE.get(opp_team)
            opp_sv = GOALIE_SV.get(opp_goalie, LEAGUE_SV) if opp_goalie else LEAGUE_SV
            opp_goalie_mult = max(0.70, min(1.30, (1 - opp_sv) / (1 - LEAGUE_SV)))
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
                "opp_team": opp_team,
                "opp_goalie": opp_goalie,
                "opp_sv": opp_sv,
                "opp_goalie_mult": round(opp_goalie_mult, 3),
                "season_gpg": round(base_gpg, 3),
                "gpg_source": gpg_source,
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
        "method_note": "P(score) = 1 - exp(-GPG × opp_goalie_factor), where "
                       "opp_goalie_factor = (1-opp_SV%)/(1-.910) from the opposing "
                       "starter's real save pct (TEAM_GOALIE->GOALIE_SV). "
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
