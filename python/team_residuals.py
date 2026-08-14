"""
EdgeStat -- per-team model residual analysis.

For each historical game in last 14 days, computes:
  - Expected margin (from pre-game ELO diff)
  - Actual margin
  - Residual = actual - expected

Per team, aggregates:
  - Avg residual when home (how much over/under their ELO-derived expectation)
  - Avg residual when away
  - "Overrated" if avg_residual is significantly negative (under-perform)
  - "Underrated" if avg_residual is positive

Surfaces this as a context overlay on today's predictions: "LAL is +4 vs
their record-based expectation -- model may underrate them."

Output: data/team_residuals_<sport>.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "cws", "mlb"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _winpct_to_elo(wp):
    if wp <= 0.01: return 1250
    if wp >= 0.99: return 1750
    return 1500 + 400 * math.log10(wp / (1 - wp))


def compute_residuals(sport: str) -> Dict[str, Any]:
    h = _load(os.path.join(DATA_DIR, f"historical_{sport}.json"))
    games = h.get("games") or []
    if not games:
        # SHAPE-IDENTICAL degraded payload (off-season / no history yet) -- a
        # missing key here printed "ERROR: 'n_teams'" for every dark sport on
        # every pipeline run. Same rule as everywhere: display code must never
        # look broken because a season is over. Written to disk so the page
        # shows an honest empty state instead of a stale season.
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "sport": sport,
            "n_teams": 0,
            "n_historical_games": 0,
            "most_underrated": [],
            "most_overrated": [],
            "teams": {},
            "note": "no historical games (off-season or feed dark)",
        }
        out_path = os.path.join(DATA_DIR, f"team_residuals_{sport}.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    games_sorted = sorted(games, key=lambda g: g["date"])
    records: Dict[str, Dict[str, int]] = {}
    team_resid_home: Dict[str, List[float]] = {}
    team_resid_away: Dict[str, List[float]] = {}

    for g in games_sorted:
        ht, at = g["home_team"], g["away_team"]
        if not (ht and at): continue
        h_rec = records.get(ht, {"w": 0, "l": 0, "t": 0})
        a_rec = records.get(at, {"w": 0, "l": 0, "t": 0})
        h_tot = sum(h_rec.values())
        a_tot = sum(a_rec.values())
        if h_tot == 0 or a_tot == 0:
            # Skip until we have base records
            pass
        h_wp = (h_rec["w"] + 0.5 * h_rec["t"]) / max(1, h_tot) if h_tot else 0.5
        a_wp = (a_rec["w"] + 0.5 * a_rec["t"]) / max(1, a_tot) if a_tot else 0.5
        h_elo = _winpct_to_elo(h_wp)
        a_elo = _winpct_to_elo(a_wp)
        # Expected margin: rough 1pt per 25 ELO difference (sport-dependent but standard scale)
        expected_margin = (h_elo - a_elo) / 25
        actual_margin = g["margin"]
        residual = actual_margin - expected_margin
        team_resid_home.setdefault(ht, []).append(residual)
        team_resid_away.setdefault(at, []).append(-residual)    # from away team's POV

        # Update records
        if g["home_score"] > g["away_score"]:
            records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["w"] += 1
            records.setdefault(at, {"w": 0, "l": 0, "t": 0})["l"] += 1
        elif g["away_score"] > g["home_score"]:
            records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["l"] += 1
            records.setdefault(at, {"w": 0, "l": 0, "t": 0})["w"] += 1
        else:
            records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["t"] += 1
            records.setdefault(at, {"w": 0, "l": 0, "t": 0})["t"] += 1

    teams_out = {}
    for team in set(list(team_resid_home.keys()) + list(team_resid_away.keys())):
        home_resids = team_resid_home.get(team, [])
        away_resids = team_resid_away.get(team, [])
        all_resids = home_resids + away_resids
        if not all_resids: continue
        avg_resid = sum(all_resids) / len(all_resids)
        teams_out[team] = {
            "name": team,
            "n_home": len(home_resids),
            "n_away": len(away_resids),
            "avg_residual": round(avg_resid, 2),
            "avg_home_residual": round(sum(home_resids) / len(home_resids), 2) if home_resids else None,
            "avg_away_residual": round(sum(away_resids) / len(away_resids), 2) if away_resids else None,
            "classification": ("UNDERRATED" if avg_resid > 3 else
                                "OVERRATED" if avg_resid < -3 else "STABLE"),
        }

    # Sort by abs residual (most-mispriced first)
    teams_list = sorted(teams_out.values(), key=lambda t: -abs(t["avg_residual"]))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport,
        "n_teams": len(teams_out),
        "n_historical_games": len(games),
        "most_underrated": [t for t in teams_list if t["classification"] == "UNDERRATED"][:5],
        "most_overrated": [t for t in teams_list if t["classification"] == "OVERRATED"][:5],
        "teams": teams_out,
    }
    out_path = os.path.join(DATA_DIR, f"team_residuals_{sport}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, int]:
    results = {}
    for sport in SPORTS:
        try:
            p = compute_residuals(sport)
            n_teams = p.get("n_teams", 0)
            if not n_teams:
                results[sport] = "no history (off-season)"
                continue
            n_under = len(p.get("most_underrated", []))
            n_over = len(p.get("most_overrated", []))
            results[sport] = f"{n_teams} teams ({n_under} underrated, {n_over} overrated)"
        except Exception as e:
            results[sport] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    print("Team residuals per sport:")
    for sport, info in r.items():
        print(f"  {sport}: {info}")
