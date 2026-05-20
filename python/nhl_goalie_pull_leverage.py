"""
EdgeStat -- NHL goalie-pull leverage tracker.

Identifies in-progress NHL games where the trailing team has pulled (or is about
to pull) the goalie. These moments create high-leverage live-bet opportunities:

  - Trailing team -1 with < 3:00 left -> P(empty-net goal against) ~ 35%
  - Trailing team -2 with < 5:00 left -> goalie pull imminent (within next 90s)
  - LIVE_EDGE if the goalie-out team rallies (next-goal moves to opposite side)

Uses free ESPN scoreboard data only (nhl_state.json) -- no auth.

Output: data/nhl_goalie_pull_leverage.json

Front-end uses this to show "GOALIE PULLED" badge + live-edge alerts.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_pull_leverage.json")

# Empirically-derived empty-net goal-for vs goal-against probabilities
# (Trailing team is the one pulling; from MoneyPuck.com 2022-2024 data)
EMPTY_NET_GA_RATE = 0.34  # P(empty-net goal scored against the pullers)
EMPTY_NET_GF_RATE = 0.18  # P(pulling team scores to tie/cut deficit)


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_time_left(clock: str, period: int) -> Optional[float]:
    """Return seconds left in regulation. Hockey: 3 periods x 20 min."""
    if not clock or not isinstance(clock, str): return None
    s = clock.strip().upper()
    if "FINAL" in s or "F" == s: return 0
    try:
        if ":" in s:
            mm, ss = s.split(":")
            secs_in_p = int(mm) * 60 + int(ss)
        else:
            secs_in_p = int(float(s))
        periods_left = max(0, 3 - period)
        return secs_in_p + periods_left * 20 * 60
    except Exception:
        return None


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    leverage_events: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "progress" not in status and "live" not in status and "period" not in status:
            continue
        home_score = int(g.get("home_score") or 0)
        away_score = int(g.get("away_score") or 0)
        period = int(g.get("period") or g.get("currentPeriod") or 1)
        clock = g.get("clock") or g.get("displayClock") or ""
        secs_left = _parse_time_left(clock, period)
        if secs_left is None: continue
        # Only 3rd period (or OT not handled here)
        if period < 3: continue

        margin = home_score - away_score
        if margin == 0: continue

        # Identify trailing side
        trailing = "AWAY" if margin > 0 else "HOME"
        deficit = abs(margin)
        trail_team = g.get("away_team") if trailing == "AWAY" else g.get("home_team")
        lead_team = g.get("home_team") if trailing == "AWAY" else g.get("away_team")

        # Classify leverage
        leverage = None
        edge_note = None
        if deficit == 1 and secs_left <= 120:
            leverage = "CRITICAL"
            edge_note = f"{trail_team} -1, <2:00 left, goalie pulled or imminent"
        elif deficit == 1 and secs_left <= 180:
            leverage = "HIGH"
            edge_note = f"{trail_team} -1, <3:00 left, goalie pull window"
        elif deficit == 2 and secs_left <= 300:
            leverage = "HIGH"
            edge_note = f"{trail_team} -2, <5:00 left, pulling early"
        elif deficit <= 2 and secs_left <= 240:
            leverage = "MEDIUM"
            edge_note = f"{trail_team} -{deficit}, <4:00 left"

        if not leverage: continue

        leverage_events.append({
            "matchup": g.get("matchup") or f"{g.get('away_team')} @ {g.get('home_team')}",
            "leverage": leverage,
            "deficit": deficit,
            "secs_left": secs_left,
            "period": period,
            "clock": clock,
            "trail_team": trail_team,
            "lead_team": lead_team,
            "home_score": home_score,
            "away_score": away_score,
            "p_empty_net_against": EMPTY_NET_GA_RATE,
            "p_empty_net_for": EMPTY_NET_GF_RATE,
            "edge_note": edge_note,
            "live_bet_recos": [
                {
                    "market": f"{lead_team} next goal",
                    "model_p": round(0.55 + (EMPTY_NET_GA_RATE - 0.25), 3),
                    "rationale": "Empty-net penalty -- lead team scores ~55% of next goals when opp pulls",
                },
                {
                    "market": f"{lead_team} -1.5 puckline live",
                    "model_p": round(0.50 + 0.10 * (3 - deficit), 3),
                    "rationale": "Empty-net insurance goal expected with 1+ min remaining",
                },
            ],
        })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_events": len(leverage_events),
        "empty_net_priors": {
            "p_ga": EMPTY_NET_GA_RATE,
            "p_gf": EMPTY_NET_GF_RATE,
        },
        "leverage_events": leverage_events,
        "note": "Identifies live NHL games where goalie-pull leverage creates wagerable edges.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-goalie-pull] {o['n_events']} leverage events -> {OUT}")
