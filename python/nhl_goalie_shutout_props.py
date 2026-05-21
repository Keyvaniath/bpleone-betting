"""
EdgeStat -- NHL goalie shutout (yes/no) prop projections.

Common DK line: Goalie shutout yes +800 to +1500 (long shots). NO is heavy fav.
Method:
  P(shutout) = P(opp scores 0 goals) under Poisson distribution
  expected_goals_against = opp_goals_per_game * goalie_quality_factor * pace_factor
  P(shutout) = exp(-expected_GA)

  STRONG_YES (rare): when P(shutout) >= 14% (vs typical book +600 = 14.3%)
  STRONG_NO: when P(no shutout) >= 92% AND book is generous (~ -2000)

Output: data/nhl_goalie_shutout_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json")

# 2024-25 NHL starting goalies and their SV% / GAA
GOALIE_DB = {
    "sergei bobrovsky":    {"team": "FLA", "sv_pct": 0.916, "gaa": 2.45},
    "andrei vasilevskiy":  {"team": "TBL", "sv_pct": 0.917, "gaa": 2.50},
    "connor hellebuyck":   {"team": "WPG", "sv_pct": 0.921, "gaa": 2.20},
    "igor shesterkin":     {"team": "NYR", "sv_pct": 0.917, "gaa": 2.55},
    "jeremy swayman":      {"team": "BOS", "sv_pct": 0.910, "gaa": 2.80},
    "stuart skinner":      {"team": "EDM", "sv_pct": 0.907, "gaa": 3.05},
    "linus ullmark":       {"team": "OTT", "sv_pct": 0.910, "gaa": 2.85},
    "anthony stolarz":     {"team": "TOR", "sv_pct": 0.926, "gaa": 2.20},
    "thatcher demko":      {"team": "VAN", "sv_pct": 0.914, "gaa": 2.65},
    "frederik andersen":   {"team": "CAR", "sv_pct": 0.928, "gaa": 2.10},
    "jake oettinger":      {"team": "DAL", "sv_pct": 0.911, "gaa": 2.70},
    "juuse saros":         {"team": "NSH", "sv_pct": 0.908, "gaa": 2.95},
    "logan thompson":      {"team": "WSH", "sv_pct": 0.918, "gaa": 2.45},
    "adin hill":           {"team": "VGK", "sv_pct": 0.911, "gaa": 2.65},
    "ilya sorokin":        {"team": "NYI", "sv_pct": 0.910, "gaa": 2.85},
    "lukas dostal":        {"team": "ANA", "sv_pct": 0.902, "gaa": 3.25},
    "samuel ersson":       {"team": "PHI", "sv_pct": 0.890, "gaa": 3.10},
    "jacob markstrom":     {"team": "NJD", "sv_pct": 0.911, "gaa": 2.65},
    "joonas korpisalo":    {"team": "BOS", "sv_pct": 0.892, "gaa": 3.10},
    "mackenzie blackwood": {"team": "COL", "sv_pct": 0.910, "gaa": 2.65},
    "alex nedeljkovic":    {"team": "PIT", "sv_pct": 0.901, "gaa": 3.20},
    "tristan jarry":       {"team": "PIT", "sv_pct": 0.901, "gaa": 3.20},
    "jordan binnington":   {"team": "STL", "sv_pct": 0.898, "gaa": 3.05},
    "ukko-pekka luukkonen": {"team": "BUF", "sv_pct": 0.890, "gaa": 3.30},
    "joey daccord":        {"team": "SEA", "sv_pct": 0.907, "gaa": 2.95},
    "joel hofer":          {"team": "STL", "sv_pct": 0.905, "gaa": 2.95},
    "spencer knight":      {"team": "CHI", "sv_pct": 0.890, "gaa": 3.35},
    "darcy kuemper":       {"team": "LAK", "sv_pct": 0.910, "gaa": 2.70},
    "kevin lankinen":      {"team": "VAN", "sv_pct": 0.907, "gaa": 2.85},
    "filip gustavsson":    {"team": "MIN", "sv_pct": 0.913, "gaa": 2.55},
    "alex lyon":           {"team": "DET", "sv_pct": 0.900, "gaa": 3.10},
}

TEAM_GOALS_PER_GAME = {
    "BOS": 3.1, "FLA": 3.4, "DAL": 3.3, "CAR": 3.4, "EDM": 3.6, "COL": 3.4, "WPG": 3.2,
    "TBL": 3.4, "NYR": 3.2, "TOR": 3.5, "VGK": 3.3, "NJD": 3.3, "WSH": 3.1, "VAN": 3.2,
    "LAK": 3.0, "STL": 3.0, "MIN": 3.0, "NSH": 3.0, "OTT": 3.1, "PHI": 3.0, "MTL": 3.1,
    "BUF": 3.1, "PIT": 2.9, "DET": 2.8, "ARI": 2.6, "CGY": 2.8, "ANA": 2.7, "SEA": 2.8,
    "SJS": 2.6, "CHI": 2.5, "CBJ": 2.8, "NYI": 2.9,
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

        # Find goalies for each team
        for goalie_name, info in GOALIE_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_team = away if is_home else home

            opp_goals = TEAM_GOALS_PER_GAME.get(opp_team, 3.1)
            # Goalie SV% adjusts expected GA: a 0.928 SV% goalie reduces opp goals
            # by ratio of (1-0.928) / (1-0.910) = 0.72 / 0.90 = 0.80 (allows 80% of avg)
            sv_factor = (1 - info["sv_pct"]) / (1 - 0.910)
            expected_ga = opp_goals * sv_factor

            p_shutout = math.exp(-expected_ga)
            p_no_shutout = 1 - p_shutout

            edge_class = "NONE"
            best_market = None
            # Typical book: shutout YES around +800 (11.1%) to +1200 (7.7%)
            # STRONG_YES when our P(shutout) >= 14% (5%+ edge over +600)
            if p_shutout >= 0.14:
                edge_class = "STRONG_YES"
                best_market = {"market": "GOALIE_SHUTOUT_YES", "p": round(p_shutout, 3),
                               "fair_odds": _american(p_shutout)}
            # STRONG_NO would be too thin given book pricing -- skip

            rows.append({
                "matchup": f"{away} @ {home}",
                "goalie": goalie_name,
                "team": info["team"],
                "opp": opp_team,
                "sv_pct": info["sv_pct"],
                "gaa": info["gaa"],
                "opp_goals_per_game": opp_goals,
                "sv_factor": round(sv_factor, 3),
                "expected_GA": round(expected_ga, 2),
                "p_shutout": round(p_shutout, 3),
                "p_no_shutout": round(p_no_shutout, 3),
                "fair_yes_odds": _american(p_shutout),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_shutout"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_goalies": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(shutout) = exp(-expected_GA). expected_GA = opp_GPG x sv_factor. "
                       "STRONG_YES when P(shutout) >= 14% (vs +600 book breakeven). "
                       "NO not surfaced due to thin payouts at -1800+.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-shutout] {o['n_goalies']} goalies, {o['n_strong_edges']} strong edges -> {OUT}")
