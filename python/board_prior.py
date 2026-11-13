"""Which win probability a sport's game board may publish (2026-11-03).

The *_state.json boards (espn_generic, nba/nhl/nfl pipelines) published P(home)
and "fair" American odds from a SYNTHETIC Elo built from season win-pct -- after
seven games a 5-2 team vs a 1-6 team came out 94.8% / -1835. That number was
never validated against anything and is not a price. It also fed the prop
generators and every board that reads p_home_win.

Rule now, per game, best validated source first:
  1. "game_lines_desk": the desk's blended P(home) (python/game_lines_desk.py,
     by ESPN event id), published WITH the desk's verdict. Where the verdict is
     NO EDGE the blend is DraftKings' own no-vig number.
  2. "dk_no_vig": DraftKings' two moneylines for this event, de-vigged
     (quotes.no_vig_two_way) from data/espn_odds.json.
  3. None: no validated probability -> the board shows no probability and no
     fair price. The synthetic Elo is kept only as p_home_win_record_elo for
     internal consumers that still need a number; it is never displayed.

Every board row gets: p_source, p_home_display (None unless 1 or 2),
dk_ml_home / dk_ml_away / odds_observed_at (the real price), desk_verdict.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import quotes as _q

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


PLACEHOLDER_ABS_ML = 3000   # beyond this an ESPN 'DK' line is a placeholder, not a market


class BoardPrior:
    def __init__(self, sport: str):
        self.sport = sport.lower()
        odds = _load("espn_odds.json")
        self.observed_at = odds.get("generated_at")
        self.dk: Dict[str, Dict[str, Any]] = {}
        for g in odds.get("games") or []:
            if str(g.get("sport") or "").lower() != self.sport or not g.get("event_id"):
                continue
            m = g.get("market") or {}
            if m.get("ml_home") is None or m.get("ml_away") is None:
                continue
            self.dk[str(g["event_id"])] = m
        desk = ((_load("game_lines_desk.json").get("sports") or {}).get(self.sport) or {})
        self.verdict = desk.get("verdict")
        # (2026-11-13 review) a RESEARCH ONLY desk (college basketball) is not a prior for anything
        if str(self.verdict or "").upper().startswith("RESEARCH"):
            desk = {}
        self.desk = {str(r["event_id"]): r for r in (desk.get("board") or [])
                     if r.get("event_id") and r.get("p_home") is not None}

    def for_event(self, event_id: Any) -> Dict[str, Any]:
        """Display fields for one game. p_home_display is None when nothing validated exists."""
        eid = str(event_id or "")
        m = self.dk.get(eid) or {}
        out: Dict[str, Any] = {
            "dk_ml_home": m.get("ml_home"),
            "dk_ml_away": m.get("ml_away"),
            "odds_observed_at": self.observed_at if m else None,
            "p_source": None,
            "p_home_display": None,
            "desk_verdict": None,
        }
        # (2026-11-05) ESPN files placeholder "DraftKings" lines on lopsided
        # college games (-100000/+5000, -20000/+3500). De-vigged they read as a
        # 98% "market" probability and seeded TRACK buttons at -100000. A side
        # beyond +/-3000 is treated as no posted market.
        if m and any(abs(int(m.get(k) or 0)) > PLACEHOLDER_ABS_ML for k in ("ml_home", "ml_away")):
            out.update(dk_ml_home=None, dk_ml_away=None, odds_observed_at=None, dk_placeholder=True)
            m = {}
        d = self.desk.get(eid)
        if d is not None:
            out.update(p_source="game_lines_desk", p_home_display=round(float(d["p_home"]), 4),
                       desk_verdict=(self.verdict or "").split(":")[0] or None)
            return out
        if m:
            p = _q.no_vig_two_way(m.get("ml_home"), m.get("ml_away"))
            if p is not None:
                out.update(p_source="dk_no_vig", p_home_display=round(p, 4))
        return out


def apply(game: Dict[str, Any], prior: "BoardPrior", synthetic_p: float,
          keep_model_prior: Optional[float] = None) -> float:
    """Stamp display fields on `game` and return the PRE-GAME prior to use.

    keep_model_prior: a pipeline that already has a validated model prior
    (NHL's desk model prob) passes it to keep using it internally.
    """
    f = prior.for_event(game.get("id"))
    game.update(f)
    game["p_home_win_record_elo"] = round(synthetic_p, 4)   # audit only, never displayed
    if keep_model_prior is not None:
        return keep_model_prior
    return f["p_home_display"] if f["p_home_display"] is not None else synthetic_p


def finalize(game: Dict[str, Any], american) -> None:
    """Fair prices only exist where a validated PRE-GAME probability does.
    In play and final: no probability is displayed (the live win-prob curve
    is an unvalidated heuristic) and no fair price."""
    p = game.get("p_home_display") if game.get("state") == "pre" else None
    if game.get("state") != "pre":
        game["p_home_display"] = None
        # (2026-11-04) the board is pre-game only: once a game starts, the latest
        # espn_odds snapshot can be DK's IN-PLAY line (TOR@DEN -191/+160 showed
        # mid-game). Keep the pre-game number for reference, never display it.
        for k in ("dk_ml_home", "dk_ml_away"):
            if game.get(k) is not None:
                game[k + "_last_seen"] = game[k]
            game[k] = None
    game["fair_home_american"] = american(p) if p is not None else None
    game["fair_away_american"] = american(1 - p) if p is not None else None
