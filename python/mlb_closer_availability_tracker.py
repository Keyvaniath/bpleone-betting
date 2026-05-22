"""
EdgeStat -- MLB closer availability tracker.

The closer's availability shifts late-game leverage dramatically. When the
elite closer is unavailable (used yesterday + day before, or 25+ pitches in
last appearance), the team typically uses a setup man — and blown-save
risk rises ~15-20 percentage points.

For each game tonight, identifies the team's closer + availability status:
  AVAILABLE:    Fresh, can pitch 1 full inning
  LIMITED:      Used yesterday, can pitch but at reduced effectiveness
  UNAVAILABLE:  2+ consecutive days OR 25+ pitches last outing
                                 -> blown-save risk +15 pp

Consumers:
  - mlb_innings_7_9_totals: opp UNDER lean reverses when closer unavailable
  - mlb_pitcher_win_props: starter win prob drops 5-8 pp if closer out
  - mlb_team_first_inning_run: irrelevant (this is late-game only)

Output: data/mlb_closer_availability_tracker.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json")


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


# Team -> primary closer (2025 season approximation)
CLOSER_DB = {
    "BAL": "Felix Bautista", "BOS": "Aroldis Chapman", "NYY": "Luke Weaver",
    "TBR": "Pete Fairbanks", "TOR": "Jordan Romano", "TBD": "Pete Fairbanks",
    "CWS": "Steven Wilson", "CLE": "Emmanuel Clase", "DET": "Will Vest",
    "KCR": "Carlos Estevez", "MIN": "Jhoan Duran", "KC": "Carlos Estevez",
    "HOU": "Josh Hader", "LAA": "Ben Joyce", "OAK": "Mason Miller",
    "SEA": "Andres Munoz", "TEX": "Kirby Yates", "ATH": "Mason Miller",
    "ATL": "Raisel Iglesias", "MIA": "Calvin Faucher", "NYM": "Edwin Diaz",
    "PHI": "Jose Alvarado", "WSN": "Kyle Finnegan", "WAS": "Kyle Finnegan",
    "CHC": "Porter Hodge", "CIN": "Alexis Diaz", "MIL": "Devin Williams",
    "PIT": "David Bednar", "STL": "Ryan Helsley",
    "ARI": "Justin Martinez", "COL": "Justin Lawrence", "LAD": "Tanner Scott",
    "SDP": "Robert Suarez", "SFG": "Ryan Walker", "SF": "Ryan Walker",
    "SD": "Robert Suarez", "AZ": "Justin Martinez",
}


def _status(usage_yesterday: bool, usage_2_days_ago: bool,
            pitches_last: float) -> str:
    if usage_yesterday and usage_2_days_ago:
        return "UNAVAILABLE"
    if pitches_last >= 25 and usage_yesterday:
        return "UNAVAILABLE"
    if usage_yesterday:
        return "LIMITED"
    return "AVAILABLE"


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    # Index closer recent usage
    pitcher_idx = {(p.get("name") or "").lower(): p
                   for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        # Extract teams from "AWAY @ HOME" string or game object
        home_team = (g.get("home_team") or
                     ((g.get("home") or {}).get("team") if isinstance(g.get("home"), dict) else "") or
                     (matchup.split("@")[1].strip() if "@" in matchup else ""))
        away_team = (g.get("away_team") or
                     ((g.get("away") or {}).get("team") if isinstance(g.get("away"), dict) else "") or
                     (matchup.split("@")[0].strip() if "@" in matchup else ""))

        sides_out: Dict[str, Any] = {}
        for side, team in (("home", home_team), ("away", away_team)):
            closer_name = CLOSER_DB.get((team or "").upper())
            if not closer_name:
                sides_out[side] = {
                    "team": team, "closer": None,
                    "status": "UNKNOWN_CLOSER",
                    "blown_save_risk_delta_pp": 0,
                }
                continue

            closer_row = pitcher_idx.get(closer_name.lower(), {})
            recent = closer_row.get("recent") or {}
            usage_yesterday = bool(recent.get("pitched_yesterday", False))
            usage_2_days = bool(recent.get("pitched_2_days_ago", False))
            pitches_last = _safe(recent.get("pitches_last_appearance"), 12.0)

            status = _status(usage_yesterday, usage_2_days, pitches_last)
            risk_delta = {"AVAILABLE": 0, "LIMITED": 7, "UNAVAILABLE": 16,
                          "UNKNOWN_CLOSER": 0}.get(status, 0)

            sides_out[side] = {
                "team": team,
                "closer": closer_name,
                "status": status,
                "usage_yesterday": usage_yesterday,
                "usage_2_days_ago": usage_2_days,
                "pitches_last_appearance": pitches_last,
                "blown_save_risk_delta_pp": risk_delta,
            }

        # Game-level leans
        leans: List[str] = []
        for side, opp_side in (("home", "away"), ("away", "home")):
            s = sides_out[side]
            opp_team = sides_out[opp_side].get("team")
            if s["status"] == "UNAVAILABLE":
                leans.append(f"{opp_team}_LATE_RALLY_OVER (vs {s['team']} closer out)")
            elif s["status"] == "LIMITED":
                leans.append(f"{opp_team}_LATE_OVER_LEAN (vs {s['team']} closer limited)")

        out_games.append({
            "matchup": matchup,
            "home": sides_out["home"],
            "away": sides_out["away"],
            "leans": leans,
        })

    n_unavail = sum(1 for g in out_games for s in ("home", "away")
                    if g[s].get("status") == "UNAVAILABLE")
    n_limited = sum(1 for g in out_games for s in ("home", "away")
                    if g[s].get("status") == "LIMITED")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_closers_unavailable": n_unavail,
        "n_closers_limited": n_limited,
        "method_note": "Closer status from recent-usage logs: AVAILABLE (fresh), "
                       "LIMITED (used yesterday, +7pp blown save risk), UNAVAILABLE "
                       "(2 consecutive days OR 25+ pitches last, +16pp risk). Drives "
                       "opp LATE_OVER leans.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[closer] {o['n_games']} games, {o['n_closers_unavailable']} unavailable, "
          f"{o['n_closers_limited']} limited -> {OUT}")
