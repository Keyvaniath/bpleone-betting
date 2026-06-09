"""
EdgeStat -- WNBA live scoring environment (shared helper).

The WNBA prop generators carry a STATIC pace table set at season start. This
helper derives a LIVE game-level scoring-environment factor from the real
results ledger (team_form_wnba.json: avg points for/against over the recent
window) so projections respond to how teams are actually playing, not frozen
preseason numbers.

Honesty notes:
  - Final scores can't separate true pace (possessions) from efficiency, so this
    is a SCORING ENVIRONMENT factor, not a pace estimate. For projecting player
    counting stats the distinction doesn't matter -- both scale opportunity.
  - Early-season samples are thin, so each team's factor is Bayesian-shrunk
    toward neutral by games played (k=8): a 5-game sample moves ~38% of the way.
  - The game factor (avg of both teams) is clamped to [0.92, 1.08] -- this is a
    trim on a static baseline, never a wholesale override.

Usage:   from wnba_scoring_env import game_env_factor
         env, meta = game_env_factor(home_full_name, away_full_name)
         pace_factor *= env
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
FORM = os.path.join(DATA_DIR, "team_form_wnba.json")

SHRINK_K = 8.0
CLAMP = (0.92, 1.08)

_CACHE: Optional[Dict[str, Any]] = None


def _teams() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        try:
            with open(FORM, encoding="utf-8") as f:
                _CACHE = json.load(f).get("teams") or {}
        except Exception:
            _CACHE = {}
    return _CACHE


def reset_cache() -> None:
    global _CACHE
    _CACHE = None


def _window(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("L10", "L5"):
        w = rec.get(key)
        if w and w.get("n") and w.get("avg_pf") is not None and w.get("avg_pa") is not None:
            return w
    return None


def _league_avg_score() -> Optional[float]:
    vals = []
    for rec in _teams().values():
        w = _window(rec)
        if w:
            vals.append((w["avg_pf"] + w["avg_pa"]) / 2)
    return (sum(vals) / len(vals)) if len(vals) >= 6 else None


def _team_factor(full_name: str, league: float) -> Tuple[float, int]:
    """Shrunk env factor for one team (1.0 = league-average scoring games)."""
    rec = None
    if full_name:
        low = full_name.lower().strip()
        rec = next((v for k, v in _teams().items() if k.lower() == low), None)
    w = _window(rec) if rec else None
    if not w or not league:
        return 1.0, 0
    raw = ((w["avg_pf"] + w["avg_pa"]) / 2) / league
    n = float(w.get("n") or 0)
    shrunk = 1.0 + (raw - 1.0) * (n / (n + SHRINK_K))
    return shrunk, int(n)


def game_env_factor(home_full: str, away_full: str) -> Tuple[float, Dict[str, Any]]:
    """Game-level live scoring-environment multiplier (both teams averaged),
    shrunk by sample and clamped. Returns (factor, meta). Neutral 1.0 when the
    form feed is missing or too thin -- safe to multiply in unconditionally."""
    league = _league_avg_score()
    if not league:
        return 1.0, {"env": 1.0, "basis": "no form data (neutral)"}
    hf, hn = _team_factor(home_full, league)
    af, an = _team_factor(away_full, league)
    env = max(CLAMP[0], min(CLAMP[1], (hf + af) / 2))
    return env, {
        "env": round(env, 4),
        "home_env": round(hf, 4), "home_n": hn,
        "away_env": round(af, 4), "away_n": an,
        "league_avg_score": round(league, 1),
        "basis": "live results (team_form_wnba), shrunk k=8, clamped 0.92-1.08",
    }


if __name__ == "__main__":
    teams = _teams()
    league = _league_avg_score()
    print(f"[wnba-env] {len(teams)} teams, league avg score {league and round(league,1)}")
    for name in sorted(teams):
        f, n = _team_factor(name, league or 0)
        print(f"    {name:26s} env x{f:.3f}  (n={n})")
