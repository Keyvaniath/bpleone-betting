"""
EdgeStat -- Against-the-Spread (ATS) tracker per team.

Uses our model's pre-game P(home win) → implied "model spread" via point
margin proxy (ELO diff / 25 = pts), then compares to actual margin to
compute ATS record.

A team that consistently exceeds our model's expected margin = our model
is UNDERRATING them at the spread. The flag is used to overlay context on
future predictions ("this team has covered our implied spread in 7 of last
10 -- our model may still be underrating them").

Output: data/ats_tracker_<sport>.json
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


def compute_ats(sport: str) -> Dict[str, Any]:
    h = _load(os.path.join(DATA_DIR, f"historical_{sport}.json"))
    games = h.get("games") or []
    if not games:
        return {"sport": sport, "n_teams": 0, "teams": {}}

    games_sorted = sorted(games, key=lambda g: g["date"])
    records: Dict[str, Dict[str, int]] = {}
    team_ats: Dict[str, Dict[str, int]] = {}    # team -> {covers, fails, pushes}

    for g in games_sorted:
        ht, at = g["home_team"], g["away_team"]
        if not (ht and at): continue
        h_rec = records.get(ht, {"w": 0, "l": 0, "t": 0})
        a_rec = records.get(at, {"w": 0, "l": 0, "t": 0})
        h_tot = sum(h_rec.values())
        a_tot = sum(a_rec.values())
        h_wp = (h_rec["w"] + 0.5 * h_rec["t"]) / max(1, h_tot) if h_tot else 0.5
        a_wp = (a_rec["w"] + 0.5 * a_rec["t"]) / max(1, a_tot) if a_tot else 0.5
        h_elo = _winpct_to_elo(h_wp)
        a_elo = _winpct_to_elo(a_wp)
        expected_margin = (h_elo - a_elo) / 25
        actual_margin = g["margin"]
        # Home covers if actual_margin > expected_margin
        diff = actual_margin - expected_margin
        team_ats.setdefault(ht, {"covers": 0, "fails": 0, "pushes": 0})
        team_ats.setdefault(at, {"covers": 0, "fails": 0, "pushes": 0})
        if abs(diff) < 0.5:
            team_ats[ht]["pushes"] += 1
            team_ats[at]["pushes"] += 1
        elif diff > 0:
            team_ats[ht]["covers"] += 1
            team_ats[at]["fails"] += 1
        else:
            team_ats[ht]["fails"] += 1
            team_ats[at]["covers"] += 1

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
    for team, ats in team_ats.items():
        total = ats["covers"] + ats["fails"] + ats["pushes"]
        if total == 0: continue
        cover_pct = ats["covers"] / max(1, ats["covers"] + ats["fails"])
        teams_out[team] = {
            "name": team,
            "ats_record": f"{ats['covers']}-{ats['fails']}-{ats['pushes']}",
            "cover_pct": round(cover_pct, 3),
            "n_games": total,
            "signal": ("MODEL_UNDERRATES" if cover_pct >= 0.65 else
                        "MODEL_OVERRATES" if cover_pct <= 0.35 else "ALIGNED"),
        }

    teams_list = sorted(teams_out.values(), key=lambda t: -t["cover_pct"])
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport,
        "n_teams": len(teams_out),
        "n_games": len(games),
        "model_underrates_top5": [t for t in teams_list if t["signal"] == "MODEL_UNDERRATES"][:5],
        "model_overrates_top5": [t for t in teams_list if t["signal"] == "MODEL_OVERRATES"][:5],
        "teams": teams_out,
    }
    out_path = os.path.join(DATA_DIR, f"ats_tracker_{sport}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, int]:
    r = {}
    for sport in SPORTS:
        try:
            p = compute_ats(sport)
            r[sport] = p["n_teams"]
        except Exception as e:
            r[sport] = f"ERROR: {e}"
    return r


if __name__ == "__main__":
    r = run()
    print("ATS tracker per sport:")
    for sport, n in r.items():
        print(f"  {sport:6}: {n} teams")
