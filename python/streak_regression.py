"""
EdgeStat -- streak regression to mean tracker.

Teams on extreme winning streaks (5+ wins in a row) historically regress.
Teams on extreme losing streaks tend to bounce back. This module:
  - Identifies every team in today's slate currently on a 5+ streak
  - Computes their team-form record (L10)
  - For each, computes what historical post-streak win rate has been
  - Surfaces FADE STREAK / BACK_REVERSAL plays

Reads: team_form_<sport>.json + historical_<sport>.json + <sport>_state.json
Output: data/streak_regression.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "streak_regression.json")

SPORTS = [
    ("nba", "nba_state.json",  "team_form_nba.json",  "historical_nba.json"),
    ("nhl", "nhl_state.json",  "team_form_nhl.json",  "historical_nhl.json"),
    ("wnba", "wnba_state.json","team_form_wnba.json", "historical_wnba.json"),
    ("mls", "mls_state.json",  "team_form_mls.json",  "historical_mls.json"),
    ("epl", "epl_state.json",  "team_form_epl.json",  "historical_epl.json"),
    ("mlb", "today.json",      None,                    None),
    ("cws", "cws_state.json",  "team_form_cws.json",  "historical_cws.json"),
]


def _load(name):
    if not name: return {}
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_streak(streak_str):
    """Parse 'W3' or 'L5' into (sign, n)."""
    if not streak_str or not isinstance(streak_str, str) or len(streak_str) < 2:
        return None, 0
    sign = 1 if streak_str[0].upper() == "W" else (-1 if streak_str[0].upper() == "L" else 0)
    try: return sign, int(streak_str[1:])
    except Exception: return sign, 0


def _compute_streak(last_results):
    """From a list of recent games (most-recent FIRST), compute W/L streak."""
    if not last_results: return None
    first = last_results[0].get("result")
    if first not in ("W", "L"): return None
    n = 1
    for g in last_results[1:]:
        if g.get("result") == first: n += 1
        else: break
    return f"{first}{n}"


def _team_streaks(form_data):
    """team_name -> {'streak': 'W3', 'l5_record': '4-1'}"""
    out = {}
    if not form_data: return out
    teams = form_data.get("teams") or form_data.get("by_team") or {}
    if not isinstance(teams, dict): return out
    for tname, info in teams.items():
        if not isinstance(info, dict): continue
        # Try explicit streak first
        streak = info.get("streak") or info.get("current_streak")
        if not streak:
            # Compute from L5 last_results (most-recent first per team_form schema)
            l5 = info.get("L5") or {}
            results = l5.get("last_results") or []
            streak = _compute_streak(results)
        l5_record = (info.get("L5") or {}).get("record")
        out[tname] = {"streak": streak, "l10": l5_record}
    return out


def _post_streak_regression(hist_games, team, streak_len, streak_sign):
    """For 'team' in past games, find streaks of 'streak_len' wins/losses then look
    at next game outcome to compute historical regression rate."""
    by_team = defaultdict(list)
    for g in hist_games:
        ht, at = g.get("home_team"), g.get("away_team")
        hs, as_ = g.get("home_score"), g.get("away_score")
        if not (ht and at and hs is not None and as_ is not None): continue
        ts = g.get("date") or ""
        if ht == team:
            by_team[team].append({"date": ts, "won": hs > as_})
        if at == team:
            by_team[team].append({"date": ts, "won": as_ > hs})
    games = sorted(by_team[team], key=lambda g: g["date"])
    if len(games) < streak_len + 1: return None
    n_streaks = 0
    regressed = 0
    for i in range(streak_len, len(games)):
        # Check if previous 'streak_len' games match
        if streak_sign > 0 and all(games[i - j - 1]["won"] for j in range(streak_len)):
            n_streaks += 1
            if not games[i]["won"]: regressed += 1
        elif streak_sign < 0 and all(not games[i - j - 1]["won"] for j in range(streak_len)):
            n_streaks += 1
            if games[i]["won"]: regressed += 1
    if n_streaks == 0: return None
    return {"n_streaks_seen": n_streaks, "regressed": regressed,
            "regression_rate": round(regressed / n_streaks, 3)}


def run() -> Dict[str, Any]:
    alerts: List[Dict[str, Any]] = []
    for sport, state_f, form_f, hist_f in SPORTS:
        state = _load(state_f)
        form = _load(form_f)
        hist = _load(hist_f)
        streaks = _team_streaks(form)
        hist_games = hist.get("games") or []
        for g in (state.get("games") or []):
            if g.get("state") == "post": continue
            ht = g.get("home_team") or g.get("home")
            at = g.get("away_team") or g.get("away")
            if not (isinstance(ht, str) and isinstance(at, str)): continue
            for team_name, role in ((ht, "HOME"), (at, "AWAY")):
                s = streaks.get(team_name) or {}
                streak_str = s.get("streak")
                sign, n_streak = _parse_streak(streak_str)
                if n_streak < 3: continue   # need at least a 3-game streak
                regr = _post_streak_regression(hist_games, team_name, n_streak, sign)
                alert = {
                    "sport": sport.upper(),
                    "matchup": g.get("matchup") or f"{at} @ {ht}",
                    "team": team_name,
                    "role": role,
                    "streak": streak_str,
                    "l10": s.get("l10"),
                    "regression_history": regr,
                    "recommendation": (
                        f"FADE {team_name} (on W{n_streak}, historically regress {regr['regression_rate']*100:.0f}% of the time)"
                        if (sign > 0 and regr) else
                        f"BACK {team_name} (on L{n_streak}, historically bounce back {regr['regression_rate']*100:.0f}% of the time)"
                        if (sign < 0 and regr) else
                        f"{team_name} on {streak_str} -- no historical sample"
                    ),
                }
                alerts.append(alert)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "by_sport": {s: sum(1 for a in alerts if a["sport"] == s.upper()) for s, _, _, _ in SPORTS},
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Streak regression: {p['n_alerts']} alerts ({p['by_sport']})")
    for a in p["alerts"][:8]:
        print(f"  [{a['sport']}] {a['team']:25s} {a['streak']} L10 {a.get('l10')} -> {a['recommendation']}")
