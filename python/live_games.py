"""
EdgeStat -- live in-game state poller.

For each MLB game currently In Progress, pulls the gumbo live feed and emits
a compact state record:
  - score, inning, outs, base state
  - current pitcher + batter + recent pitch
  - live win expectancy (from RE24 base-out matrix + remaining-innings expected runs)

This module is designed to run on a SHORT cron (every 5-10 min) during the
~7 hour window when games are typically in progress (3 PM - 1 AM ET).

Writes data/live_state.json (overwrites every poll).

Win expectancy approximation:
  Given (inning, outs, base_state, score_diff, batting team), look up the
  base-out run expectancy matrix (RE24) for runs_remaining and combine with
  the score margin to get P(home wins).

For full accuracy a forward Monte Carlo would be better; this is the
'good enough' analytical approximation that updates within 200ms per game.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "live_state.json")
GUMBO = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

# Base-Out Run Expectancy matrix (RE24, 2010-2023 MLB average).
# Key: (outs, on_first, on_second, on_third) -> expected runs in rest of half-inning.
RE24 = {
    (0, False, False, False): 0.48,
    (0, True,  False, False): 0.86,
    (0, False, True,  False): 1.11,
    (0, False, False, True ): 1.35,
    (0, True,  True,  False): 1.46,
    (0, True,  False, True ): 1.78,
    (0, False, True,  True ): 1.96,
    (0, True,  True,  True ): 2.27,
    (1, False, False, False): 0.25,
    (1, True,  False, False): 0.50,
    (1, False, True,  False): 0.68,
    (1, False, False, True ): 0.95,
    (1, True,  True,  False): 0.91,
    (1, True,  False, True ): 1.14,
    (1, False, True,  True ): 1.39,
    (1, True,  True,  True ): 1.60,
    (2, False, False, False): 0.10,
    (2, True,  False, False): 0.22,
    (2, False, True,  False): 0.32,
    (2, False, False, True ): 0.36,
    (2, True,  True,  False): 0.41,
    (2, True,  False, True ): 0.49,
    (2, False, True,  True ): 0.58,
    (2, True,  True,  True ): 0.72,
}


def _base_state(linescore: Dict[str, Any]) -> Dict[str, Any]:
    """Extract (outs, on_first/second/third, current inning, half) from linescore."""
    inning_state = linescore.get("inningState", "Top")  # Top / Bottom / Middle / End
    inning = linescore.get("currentInning", 1)
    outs = (linescore.get("outs") or 0)
    offense = (linescore.get("offense") or {})
    on_first = bool(offense.get("first"))
    on_second = bool(offense.get("second"))
    on_third = bool(offense.get("third"))
    return {
        "inning": inning,
        "inning_state": inning_state,
        "outs": outs,
        "on_first": on_first,
        "on_second": on_second,
        "on_third": on_third,
    }


def _win_expectancy(home_runs: int, away_runs: int, state: Dict[str, Any]) -> float:
    """Approximate P(home wins) given current state."""
    inning = state.get("inning", 1)
    is_bottom = state.get("inning_state", "Top").lower() in ("bottom", "middle", "end")
    margin = home_runs - away_runs
    # Expected runs left this half-inning from RE24
    re = RE24.get((state.get("outs", 0),
                   state.get("on_first", False),
                   state.get("on_second", False),
                   state.get("on_third", False)), 0.5)
    # Average half-inning = 0.48 runs. Innings remaining = 9 - inning (rough).
    full_innings_left = max(0, 9 - inning)
    # If we're in the bottom of the inning, top is done; if top, both halves remain.
    half_innings_left = full_innings_left * 2 + (0 if is_bottom else 1)
    expected_remaining_runs_per_team = 0.5 * half_innings_left + re / 2
    # Approximate P(home outscores away in remaining play) via normal distribution
    # over future-runs difference. Std dev grows with innings left.
    sd = math.sqrt(max(1.0, expected_remaining_runs_per_team * 1.5))
    # Mean of future margin: home offense gets bottom-of-inning RE plus innings, away gets top
    if is_bottom:
        future_mean = re   # home batting now adds margin
    else:
        future_mean = -re  # away batting now subtracts margin
    # Plus future innings approximately neutral
    total_margin_mean = margin + future_mean
    # P(margin > 0)
    z = total_margin_mean / sd
    p = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    # Late-game adjustment: if 8th+ inning, scale toward whoever is currently winning
    if inning >= 8:
        if margin > 0:
            p = max(p, 0.75 + 0.05 * margin)
        elif margin < 0:
            p = min(p, 0.25 + 0.05 * margin)
    return max(0.001, min(0.999, p))


def get_live_state(game_pk: int) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    try:
        r = requests.get(GUMBO.format(game_pk=game_pk), timeout=8)
        if not r.ok:
            return None
        payload = r.json()
    except Exception:
        return None
    live = (payload.get("liveData") or {})
    linescore = live.get("linescore") or {}
    state = _base_state(linescore)
    teams = linescore.get("teams") or {}
    home_runs = (teams.get("home") or {}).get("runs", 0) or 0
    away_runs = (teams.get("away") or {}).get("runs", 0) or 0
    boxscore = live.get("boxscore") or {}
    home_name = ((boxscore.get("teams") or {}).get("home") or {}).get("team", {}).get("name")
    away_name = ((boxscore.get("teams") or {}).get("away") or {}).get("team", {}).get("name")
    # Last play description
    plays = (live.get("plays") or {})
    last_play = (plays.get("currentPlay") or {}).get("result", {}).get("description", "")
    p_home_win = _win_expectancy(home_runs, away_runs, state)
    return {
        "game_pk": game_pk,
        "home": home_name, "away": away_name,
        "home_runs": home_runs, "away_runs": away_runs,
        "state": state,
        "p_home_win": round(p_home_win, 4),
        "last_play": last_play[:200],
    }


def list_in_progress_games() -> List[int]:
    """Return gamePks for games currently In Progress."""
    if requests is None:
        return []
    try:
        sched = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1},
            timeout=10,
        ).json()
    except Exception:
        return []
    pks = []
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            state = g.get("status", {}).get("detailedState", "")
            if state in ("In Progress", "Manager Challenge", "Warmup"):
                pks.append(g["gamePk"])
    return pks


def build_all() -> Dict[str, Any]:
    pks = list_in_progress_games()
    games = []
    for pk in pks:
        st = get_live_state(pk)
        if st:
            games.append(st)
    return {
        "polled_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games_in_progress": len(games),
        "games": games,
    }


def write_live(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote live_state -> {path}")
    print(f"  Games in progress: {payload.get('games_in_progress', 0)}")
    for g in payload.get("games", [])[:8]:
        s = g["state"]
        print(f"  {g['away']} {g['away_runs']} @ {g['home']} {g['home_runs']} "
              f"({s['inning_state']} {s['inning']}, {s['outs']}o) "
              f"P(home win) {g['p_home_win']}")


if __name__ == "__main__":
    write_live(build_all())
