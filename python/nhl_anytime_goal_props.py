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
# Live current teams over the hard-coded ones (2026-10-23, real_stats_lookup).
PLAYER_DB = __import__("real_stats_lookup").apply_live_teams("nhl", PLAYER_DB)


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


SCORER_MIN_GPG = 0.25    # only established scorers are candidates (a 4th-liner's "no goal" says nothing)


def _opp_goalie_mult(desk_board: Dict[tuple, Dict[str, Any]], gstate, matchup_key, opp_side: str, opp_team: str):
    """Goals-allowed multiplier of the opposing goalie: the desk's confirmed /
    expected / projected starter's shrunk GSAA per shot (nhl_goalies), as
    (1 - (lg + q)) / (1 - lg). League average when unknown."""
    row = desk_board.get(matchup_key) or {}
    gname = ((row.get("goalies") or {}).get(opp_side) or {}).get("projected")
    gid = gstate.resolve(opp_team, gname) if gname else None
    if gid is None:
        return 1.0, gname
    lg = gstate.lg()
    return max(0.80, min(1.20, (1 - (lg + gstate.q(gid))) / (1 - lg))), gname


def run() -> Dict[str, Any]:
    """2026-11-02: real per-player goal rates (nhl_skaters store, EWMA +
    position prior), the opposing goalie from the game-lines desk, and the
    negative binomial fitted on last season. The hand-typed PLAYER_DB /
    GOALIE_SV / TEAM_GOALIE tables above are no longer read: ANYTIME_GOAL_NO
    graded 71% at 87% predicted on them."""
    import nhl_goalies as _ng
    import nhl_skaters as ns
    st, cal = ns.load()
    r_g = ns.dispersion(cal, "goals")
    gstate = _ng.history_features(_ng.ordered_games())[1]
    desk = _load(os.path.join(DATA_DIR, "game_lines_desk.json"))
    desk_board = {}
    for r in ((desk.get("sports") or {}).get("nhl") or {}).get("board") or []:
        a, _, h = str(r.get("matchup") or "").partition(" @ ")
        desk_board[(a.strip(), h.strip())] = r
    from nhl_skater_hits_blocks_props import _fullname_index
    names = _fullname_index()
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []
    cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    by_team: Dict[str, List[str]] = {}
    for pid, x in st.p.items():
        if x.get("team") and str(x.get("last_date") or "") >= cutoff and x.get("gp", 0) >= 10:
            by_team.setdefault(x["team"], []).append(pid)

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or g.get("state") in ("in", "post"):
            continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away:
            continue
        key = (_ng._team(away), _ng._team(home))
        for side, team, opp_side, opp in (("home", home, "away", away), ("away", away, "home", home)):
            mult, opp_goalie = _opp_goalie_mult(desk_board, gstate, key, opp_side, _ng._team(opp))
            for pid in by_team.get(_ng._team(team), []):
                base_gpg = st.rate(pid, "goals")
                if base_gpg is None or base_gpg < SCORER_MIN_GPG:
                    continue
                x = st.p[pid]
                parts = _ng._fold(x.get("name")).replace(".", "").split()
                full = names.get((parts[0][:1], parts[-1])) if len(parts) >= 2 else None
                if not full or len(full) != 1:
                    continue
                expected_goals = base_gpg * mult
                p_scores = ns.p_at_least(1, expected_goals, r_g)
                p_no_goal = 1 - p_scores

                edge_class, best_market = "NONE", None
                if 0.60 <= p_scores <= 0.72:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "ANYTIME_GOAL_YES", "p": round(p_scores, 3), "fair_odds": _american(p_scores)}
                elif p_scores <= 0.20:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "ANYTIME_GOAL_NO", "p": round(p_no_goal, 3), "fair_odds": _american(p_no_goal)}

                rows.append({
                    "matchup": f"{away} @ {home}",
                    "player": full[0],
                    "team": team,
                    "opp_team": opp,
                    "opp_goalie": opp_goalie,
                    "opp_goalie_mult": round(mult, 3),
                    "season_gpg": round(base_gpg, 3),
                    "gpg_source": "nhl_skaters (boxscores, EWMA)",
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
        "dispersion_goals": r_g,
        "method_note": ("P(score) from real per-player goal rates (every NHL boxscore since 2024-25, EWMA + "
                        "position prior) x the opposing goalie's goals-allowed factor (desk's confirmed / "
                        "expected / projected starter, shrunk GSAA), negative binomial fitted on last season. "
                        f"Candidates: scorers >= {SCORER_MIN_GPG} goals/game. STRONG_YES 60-72%, STRONG_NO when "
                        "P(score) <= 20%. Replaced hand-typed tables 2026-11-02."),
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goal] {o['n_players_projected']} players, {o['n_strong']} strong -> {OUT}")
