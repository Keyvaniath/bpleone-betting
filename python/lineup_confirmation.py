"""
EdgeStat -- MLB lineup confirmation status.

Tracks per-game lineup posting status:
   home_posted (bool): home lineup announced
   away_posted (bool): away lineup announced

Alerts when a top-board lock involves a starting pitcher who's NOT in
the posted lineup (potential scratch).

Output: data/lineup_confirmation.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "lineup_confirmation.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    locks = _load(os.path.join(DATA_DIR, "locks_history.json"))

    games_status: List[Dict[str, Any]] = []
    n_both_posted = 0
    n_pending = 0

    for g in (matchups.get("games") or []):
        lineups = g.get("lineups") or {}
        home_posted = lineups.get("home_posted", False)
        away_posted = lineups.get("away_posted", False)
        if home_posted and away_posted: n_both_posted += 1
        else: n_pending += 1
        games_status.append({
            "matchup": g.get("matchup"),
            "home_pitcher": (g.get("home_pitcher") or {}).get("name"),
            "away_pitcher": (g.get("away_pitcher") or {}).get("name"),
            "home_lineup_posted": home_posted,
            "away_lineup_posted": away_posted,
            "home_lineup_size": len(lineups.get("home") or []),
            "away_lineup_size": len(lineups.get("away") or []),
            "first_pitch": g.get("time"),
        })

    # Check today's locks for pitcher / matchup references against pending lineups
    today_str = dt.date.today().isoformat()
    todays_locks = [L for L in (locks.get("history") or [])
                     if L.get("date") == today_str and not L.get("settled")]

    lock_warnings = []
    for L in todays_locks:
        market = (L.get("market") or "").lower()
        if "k_over" in market or "er_under" in market or "ml_" in market:
            mu = (L.get("player_or_matchup") or "").lower()
            for g in games_status:
                gm = (g.get("matchup") or "").lower()
                if mu in gm or gm in mu:
                    if not g["home_lineup_posted"] or not g["away_lineup_posted"]:
                        lock_warnings.append({
                            "pick_id": L.get("pick_id"),
                            "lock": f"{L.get('sport')} {L.get('player_or_matchup')} {L.get('market')}",
                            "warning": "Lineup not fully posted -- scratched-starter risk",
                            "matchup": g["matchup"],
                            "home_posted": g["home_lineup_posted"],
                            "away_posted": g["away_lineup_posted"],
                        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_status),
        "n_both_posted": n_both_posted,
        "n_pending": n_pending,
        "lock_warnings": lock_warnings,
        "games": games_status,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Lineup confirmation: {p['n_both_posted']}/{p['n_games']} both posted, {p['n_pending']} pending")
    print(f"  {len(p['lock_warnings'])} lock warnings (lineup not yet posted for game with active lock)")
    for w in p['lock_warnings'][:5]:
        print(f"    [{w['matchup']}] {w['warning']}: {w['lock']}")
