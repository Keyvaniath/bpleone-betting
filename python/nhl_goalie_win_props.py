"""
EdgeStat -- NHL goalie wins yes/no prop projection.

Common DK line: "Goalie to win - Yes/No" (priced same as team ML usually).
Subtle difference: goalie ONLY gets the win if they're the goalie of record
when their team wins. If pulled early or replaced, no win even if team wins.

Method:
  P(goalie wins) = P(team_wins) * P(goalie_completes_game_as_starter)
  P(team_wins) approximated from team strength rating (ELO-like)
  P(complete_game) = base 0.92 (rate at which starters get the decision),
    adjusted down if SV% is poor (more likely pulled)

  STRONG_YES when our P(goalie wins) shows 5%+ edge vs typical book ML.
  Book ML for a -150 favorite goalie = 60% breakeven.
  STRONG when 65-75% (5%+ edge on top end, capped at heavy fav range).

Output: data/nhl_goalie_win_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_win_props.json")

# Team strength rating (higher = better team). League avg 1500.
TEAM_RATING = {
    "BOS": 1610, "FLA": 1605, "DAL": 1600, "CAR": 1605, "EDM": 1590, "COL": 1595,
    "WPG": 1585, "TBL": 1580, "NYR": 1575, "TOR": 1580, "VGK": 1575, "NJD": 1565,
    "WSH": 1530, "VAN": 1555, "LAK": 1540, "STL": 1490, "MIN": 1495, "NSH": 1480,
    "OTT": 1470, "PHI": 1465, "MTL": 1455, "BUF": 1450, "PIT": 1480, "DET": 1455,
    "ARI": 1395, "CGY": 1465, "ANA": 1380, "SEA": 1465, "SJS": 1370, "CHI": 1390,
    "CBJ": 1425, "NYI": 1485,
}

# Starting goalies and quality
GOALIE_DB = {
    "sergei bobrovsky":    {"team": "FLA", "sv_pct": 0.916},
    "andrei vasilevskiy":  {"team": "TBL", "sv_pct": 0.917},
    "connor hellebuyck":   {"team": "WPG", "sv_pct": 0.921},
    "igor shesterkin":     {"team": "NYR", "sv_pct": 0.917},
    "jeremy swayman":      {"team": "BOS", "sv_pct": 0.910},
    "stuart skinner":      {"team": "EDM", "sv_pct": 0.907},
    "linus ullmark":       {"team": "OTT", "sv_pct": 0.910},
    "anthony stolarz":     {"team": "TOR", "sv_pct": 0.926},
    "thatcher demko":      {"team": "VAN", "sv_pct": 0.914},
    "frederik andersen":   {"team": "CAR", "sv_pct": 0.928},
    "jake oettinger":      {"team": "DAL", "sv_pct": 0.911},
    "juuse saros":         {"team": "NSH", "sv_pct": 0.908},
    "logan thompson":      {"team": "WSH", "sv_pct": 0.918},
    "adin hill":           {"team": "VGK", "sv_pct": 0.911},
    "ilya sorokin":        {"team": "NYI", "sv_pct": 0.910},
    "jacob markstrom":     {"team": "NJD", "sv_pct": 0.911},
    "mackenzie blackwood": {"team": "COL", "sv_pct": 0.910},
    "darcy kuemper":       {"team": "LAK", "sv_pct": 0.910},
    "filip gustavsson":    {"team": "MIN", "sv_pct": 0.913},
    "joey daccord":        {"team": "SEA", "sv_pct": 0.907},
    "ukko-pekka luukkonen": {"team": "BUF", "sv_pct": 0.890},
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


def _team_win_prob(team_rating: int, opp_rating: int, home: bool) -> float:
    """ELO-style P(team wins) with home-ice boost ~+50 ELO."""
    adj = 50 if home else -50
    diff = (team_rating + adj) - opp_rating
    return 1 / (1 + 10 ** (-diff / 400))


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

        for goalie_name, info in GOALIE_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp = away if is_home else home

            team_rating = TEAM_RATING.get(info["team"], 1500)
            opp_rating = TEAM_RATING.get(opp, 1500)
            p_team_wins = _team_win_prob(team_rating, opp_rating, is_home)

            # P(goalie completes start as starter of record)
            # Below-average SV% goalies get pulled more often
            sv_factor = 0.92 if info["sv_pct"] >= 0.910 else 0.85
            p_goalie_wins = p_team_wins * sv_factor
            p_no_win = 1 - p_goalie_wins

            edge_class = "NONE"
            best_market = None
            # STRONG_YES when p(win) >= 65% and <= 75% (capture good fav range)
            if 0.65 <= p_goalie_wins <= 0.75:
                edge_class = "STRONG_YES"
                best_market = {"market": "GOALIE_WIN_YES", "p": round(p_goalie_wins, 3),
                               "fair_odds": _american(p_goalie_wins)}
            # STRONG_NO when team is heavy dog (35-45% win prob -> NO at ~+150)
            elif 0.55 <= p_no_win <= 0.65:
                edge_class = "STRONG_NO"
                best_market = {"market": "GOALIE_WIN_NO", "p": round(p_no_win, 3),
                               "fair_odds": _american(p_no_win)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "goalie": goalie_name,
                "team": info["team"],
                "opp": opp,
                "team_rating": team_rating,
                "opp_rating": opp_rating,
                "is_home": is_home,
                "sv_pct": info["sv_pct"],
                "p_team_wins": round(p_team_wins, 3),
                "sv_factor": sv_factor,
                "p_goalie_wins": round(p_goalie_wins, 3),
                "p_no_win": round(p_no_win, 3),
                "fair_yes_odds": _american(p_goalie_wins),
                "fair_no_odds": _american(p_no_win),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_goalie_wins"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_goalies": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(goalie wins) = ELO-based P(team wins) x sv_factor (0.92 starter, "
                       "0.85 weak SV%). STRONG_YES 65-75% (vs -180 book), STRONG_NO 55-65% "
                       "for the NO side (vs +150 book).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goalie-win] {o['n_goalies']} goalies, {o['n_strong_edges']} strong edges -> {OUT}")
