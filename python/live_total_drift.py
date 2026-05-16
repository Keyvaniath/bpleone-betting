"""
EdgeStat -- score-aware live-total fair-price recomputation.

For each in-progress game, given the current inning + score + outs +
remaining innings, computes a recursive expected-runs distribution and
compares to the OPENING fair total. Tells you if the game total OVER /
UNDER has flipped value mid-game.

Output: data/live_total_drift.json
  {
    "generated_at": "...",
    "by_game": [
      { matchup, inning, score, opening_fair_total, current_fair_total,
        drift_runs, market_total (pre-game), live_implied_total }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
OUT_PATH = os.path.join(DATA_DIR, "live_total_drift.json")

MLB_BASE = "https://statsapi.mlb.com/api/v1"

# League average runs per half-inning (~0.55 per side per inning on average)
LEAGUE_RPI = 0.55


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _expected_runs_remaining(cur_inning: int, half: str, outs: int,
                              opening_fair_per_inn: float) -> float:
    """Naive: assume remaining innings each produce ~opening_fair_per_inn runs.
    Reduce current half by fraction-of-inning-played-out via outs/3."""
    half = (half or "").lower()
    # Innings still to play
    if cur_inning >= 9 and half == "bottom":
        full_innings_left = 0
    else:
        # Remaining: (9 - cur_inning) full innings + the current half + maybe other half
        full_innings_left = max(0, 9 - cur_inning)
        # Plus remainder of current inning
    half_frac_left = max(0, (3 - outs) / 3)
    other_half = 1 if half == "top" else 0    # if top, bottom still to come
    halves_remaining = half_frac_left + other_half + 2 * full_innings_left
    return halves_remaining * (opening_fair_per_inn / 2)   # per-half estimate


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    out: List[Dict[str, Any]] = []
    today_iso = dt.date.today().isoformat()
    sched = _http(f"{MLB_BASE}/schedule?sportId=1&date={today_iso}") or {}
    game_states: Dict[str, Dict[str, Any]] = {}
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            pk = g.get("gamePk")
            state = (g.get("status") or {}).get("detailedState", "")
            if state in ("Scheduled", "Pre-Game", "Warmup", "Final", "Game Over"):
                continue
            if not pk:
                continue
            ls = _http(f"{MLB_BASE}/game/{pk}/linescore") or {}
            home_team = (g.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation") or "?")
            away_team = (g.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation") or "?")
            matchup = f"{away_team} @ {home_team}"
            game_states[matchup] = {
                "linescore": ls,
                "state": state,
                "gamePk": pk,
            }

    for game in (today.get("games") or []):
        matchup = game.get("matchup")
        gs = game_states.get(matchup)
        if not gs:
            continue
        ls = gs["linescore"]
        cur_inning = ls.get("currentInning") or 1
        half = ls.get("inningHalf") or "Top"
        outs = ls.get("outs") or 0
        away_r = (ls.get("teams") or {}).get("away", {}).get("runs", 0)
        home_r = (ls.get("teams") or {}).get("home", {}).get("runs", 0)
        score_so_far = away_r + home_r

        # Per-game expected total per inning from pre-game model
        opening_total = (game.get("model") or {}).get("fair_total") or 8.5
        opening_per_inn = opening_total / 9.0

        # Remaining runs estimate
        remaining = _expected_runs_remaining(cur_inning, half, outs, opening_per_inn)
        current_fair_total = score_so_far + remaining
        drift = current_fair_total - opening_total

        market_total = (game.get("market") or {}).get("total")
        # Live total ~ market_total - score_so_far (this is the simple book formula)
        live_implied = (market_total - score_so_far) if market_total is not None else None

        out.append({
            "matchup": matchup,
            "game_pk": gs["gamePk"],
            "state": gs["state"],
            "inning": cur_inning,
            "half": half,
            "outs": outs,
            "score": f"{away_r}-{home_r}",
            "runs_so_far": score_so_far,
            "opening_fair_total": round(opening_total, 2),
            "current_fair_total": round(current_fair_total, 2),
            "drift_runs": round(drift, 2),
            "pre_game_market_total": market_total,
            "live_implied_total_remaining": round(live_implied, 2) if live_implied is not None else None,
            "lean": "OVER" if drift > 0.5 else "UNDER" if drift < -0.5 else "neutral",
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games_live": len(out),
        "by_game": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games_live']} live games")
    for g in p["by_game"][:5]:
        print(f"  {g['matchup']:15} inn {g['inning']} ({g['half']}) {g['score']} | opening {g['opening_fair_total']}, current {g['current_fair_total']}, drift {g['drift_runs']:+.2f} -> {g['lean']}")
