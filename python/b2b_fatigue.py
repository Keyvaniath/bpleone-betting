"""
EdgeStat -- NBA / NHL back-to-back fatigue tracker.

A team playing the 2nd game of a back-to-back (B2B) underperforms relative
to its baseline. We track:
  - Recent games per team (date-indexed)
  - For each team in today's slate, are they on a B2B?
  - For each B2B team, how have they performed in their last 5 B2B games?

Output: data/b2b_fatigue.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "b2b_fatigue.json")


def _load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_date(s):
    if not s: return None
    try: return dt.date.fromisoformat(s[:10])
    except Exception: return None


def _build_team_calendar(games):
    """team_name -> sorted list of (date, opponent, was_home, won)"""
    cal = defaultdict(list)
    for g in games:
        d = _parse_date(g.get("date"))
        if not d: continue
        ht, at = g.get("home_team"), g.get("away_team")
        hs, as_ = g.get("home_score"), g.get("away_score")
        if hs is None or as_ is None: continue
        home_won = hs > as_
        cal[ht].append({"date": d, "opp": at, "home": True, "won": home_won, "diff": hs - as_})
        cal[at].append({"date": d, "opp": ht, "home": False, "won": not home_won, "diff": as_ - hs})
    for t in cal: cal[t].sort(key=lambda x: x["date"])
    return cal


def _check_b2b(today_date, team_calendar):
    """Is this team playing on a B2B (yesterday + today)?"""
    yesterday = today_date - dt.timedelta(days=1)
    return any(g["date"] == yesterday for g in team_calendar)


def _b2b_history(team_calendar, lookback_days=60):
    """For this team's last N B2B games, compute record + avg margin."""
    cutoff = dt.date.today() - dt.timedelta(days=lookback_days)
    b2b_games = []
    for i in range(1, len(team_calendar)):
        prev = team_calendar[i - 1]
        cur = team_calendar[i]
        if cur["date"] < cutoff: continue
        if (cur["date"] - prev["date"]).days == 1:
            b2b_games.append(cur)
    n = len(b2b_games)
    if n == 0: return None
    wins = sum(1 for g in b2b_games if g["won"])
    avg_margin = sum(g["diff"] for g in b2b_games) / n
    return {"n_b2b": n, "wins": wins, "win_pct": round(wins / n, 3),
            "avg_margin_in_b2b": round(avg_margin, 1)}


def run() -> Dict[str, Any]:
    today = dt.date.today()
    out_by_sport: Dict[str, Any] = {}
    n_fatigued_today = 0

    for sport, state_file, hist_file in (
        ("nba", "nba_state.json", "historical_nba.json"),
        ("nhl", "nhl_state.json", "historical_nhl.json"),
    ):
        state = _load(state_file)
        hist = _load(hist_file)
        cal = _build_team_calendar(hist.get("games") or [])
        sport_alerts = []
        for g in (state.get("games") or []):
            if g.get("state") == "post": continue
            ht = g.get("home_team")
            at = g.get("away_team")
            home_b2b = _check_b2b(today, cal.get(ht, []))
            away_b2b = _check_b2b(today, cal.get(at, []))
            if not (home_b2b or away_b2b): continue
            home_b2b_hist = _b2b_history(cal.get(ht, [])) if home_b2b else None
            away_b2b_hist = _b2b_history(cal.get(at, [])) if away_b2b else None
            alert = {
                "matchup": g.get("matchup"),
                "home_team": ht, "away_team": at,
                "home_on_b2b": home_b2b,
                "away_on_b2b": away_b2b,
                "p_home_pregame": g.get("p_home_win"),
                "home_b2b_history": home_b2b_hist,
                "away_b2b_history": away_b2b_hist,
            }
            # Side that's NOT on B2B has the fatigue advantage
            if home_b2b and not away_b2b:
                alert["fatigue_edge"] = "AWAY"
                alert["recommend"] = f"FADE {ht} (home on B2B)"
                n_fatigued_today += 1
            elif away_b2b and not home_b2b:
                alert["fatigue_edge"] = "HOME"
                alert["recommend"] = f"FADE {at} (away on B2B)"
                n_fatigued_today += 1
            else:
                alert["fatigue_edge"] = "BOTH"
                alert["recommend"] = "Both teams on B2B - no edge"
            sport_alerts.append(alert)
        out_by_sport[sport] = sport_alerts

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_fatigued_games_today": n_fatigued_today,
        "by_sport": out_by_sport,
        "note": "B2B = team played yesterday AND playing today. Historical hit rate < .500 for B2B side.",
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"B2B fatigue: {p['n_fatigued_games_today']} games with fatigue edge today")
    for sport, alerts in p["by_sport"].items():
        if alerts:
            print(f"  [{sport.upper()}]")
            for a in alerts:
                hist = a.get('home_b2b_history') or a.get('away_b2b_history') or {}
                print(f"    {a['matchup']:50s} -> {a['recommend']:35s} (last B2B win%: {hist.get('win_pct','?')})")
