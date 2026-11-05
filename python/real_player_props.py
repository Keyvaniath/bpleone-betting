"""
EdgeStat -- REAL player prop projections from ESPN game logs.

For every player in player_stats_<sport>.json (NBA 358, WNBA 131, NHL 377),
convert per-game averages into fair prop odds for common markets:

  NBA / WNBA:
    - Points OVER/UNDER (lines: PG-3.5, PG-1.5, PG+0.5, PG+2.5)
    - Rebounds OVER/UNDER (lines: PG-1.5, PG+0.5)
    - Assists OVER/UNDER
    - 3-pointers made OVER/UNDER
    - PRA combined (pts+reb+ast)

  NHL:
    - Shots OVER/UNDER (lines: PG-0.5, PG+0.5, PG+1.5)
    - Goals + assists (points) OVER/UNDER
    - Power-play points (less reliable)

(2026-11-03) WHAT THIS ACTUALLY IS -- the old text above/below overstated it:
  * Inputs are NOT a last-20-game average. player_stats_<sport>.json blends this
    season's per-game numbers toward LAST season by games played,
    w = n/(n+K) (K = 5 NBA/WNBA, 30 NHL), regular season only. Early in a season
    most of the number is last season.
  * The lines are the MODEL'S OWN (mean +/- fixed offsets), not sportsbook lines.
  * Spread: basketball uses the fitted NBA dispersion (nba_dispersion: SD =
    a*mean^b, negative binomial) -- a Poisson is roughly half the real spread
    for NBA points. WNBA borrows the NBA fit (not fitted on WNBA). NHL stays
    Poisson. None of this is validated against outcomes: an unvalidated model
    projection, not a price and not a pick. The fair_* fields stay in the JSON
    for internal consumers only; the pages do not show them.

Output: data/real_player_props_<sport>.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# (2026-11-03) fitted NBA spread for the basketball markets (Poisson is far too
# narrow for points). Fail-soft: without the module we fall back to Poisson and
# the payload says so.
try:
    import nba_dispersion as _nd
except Exception:   # pragma: no cover
    _nd = None
_BB_STAT = {"PTS": "pts", "REB": "reb", "AST": "ast", "3PM": "fg3m", "PRA": "pra"}
_DIST = {"nba": "fitted NBA negative binomial (nba_dispersion)",
         "wnba": "NBA-fitted negative binomial applied to WNBA (not fitted on WNBA)",
         "nhl": "Poisson"}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam: float, line: float) -> float:
    if lam <= 0: return 0.0
    threshold = int(math.floor(line)) + 1
    s = 0.0
    for k in range(threshold):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _build_prop(lam: float, line: float, market: str) -> Dict[str, Any]:
    stat = _BB_STAT.get(market)
    if stat and _nd is not None:   # (2026-11-03) basketball: fitted spread
        p_over = _nd.p_at_least(stat, int(math.floor(line)) + 1, lam)
    else:
        p_over = _poisson_p_over(lam, line)
    return {
        "market": market,
        "line": line,
        "line_source": "model_generated",   # (2026-11-03) not a sportsbook line
        "model_mean": round(lam, 2),
        "p_over": round(p_over, 4),
        "p_under": round(1 - p_over, 4),
        "fair_over_american": _american(p_over),
        "fair_under_american": _american(1 - p_over),
    }


def project_basketball(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate prop projections for one basketball player."""
    props = []
    pg_pts = (p.get("pts_per_game") or 0)
    pg_reb = (p.get("reb_per_game") or 0)
    pg_ast = (p.get("ast_per_game") or 0)
    pg_3pm = (p.get("threes_per_game") or 0)
    # Common book lines hover around the player's mean ±2
    if pg_pts >= 2:
        # 4 PTS lines: rounded .5 around mean
        base = round(pg_pts)
        for offset in (-3.5, -1.5, 0.5, 2.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(pg_pts, line, "PTS"))
    if pg_reb >= 1:
        base = round(pg_reb)
        for offset in (-1.5, 0.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(pg_reb, line, "REB"))
    if pg_ast >= 1:
        base = round(pg_ast)
        for offset in (-1.5, 0.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(pg_ast, line, "AST"))
    if pg_3pm >= 0.5:
        base = round(pg_3pm)
        for offset in (-0.5, 0.5, 1.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(pg_3pm, line, "3PM"))
    # PRA combined
    pra = pg_pts + pg_reb + pg_ast
    if pra >= 5:
        base = round(pra)
        for offset in (-3.5, 1.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(pra, line, "PRA"))
    return props


def project_hockey(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    props = []
    sog = (p.get("shots_per_game") or 0)
    pts = (p.get("points_per_game") or 0)
    g = (p.get("goals_per_game") or 0)
    if sog >= 1:
        base = round(sog)
        for offset in (-0.5, 0.5, 1.5):
            line = base + offset
            if line >= 0.5:
                props.append(_build_prop(sog, line, "SOG"))
    if pts >= 0.3:
        for line in (0.5, 1.5):
            props.append(_build_prop(pts, line, "POINTS"))
    if g >= 0.2:
        props.append(_build_prop(g, 0.5, "ANYTIME_GOAL"))
    return props


def fetch_sport(sport_key: str) -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, f"player_stats_{sport_key}.json"))
    players = src.get("players") or []
    out = []
    parse_fn = project_basketball if sport_key in ("nba", "wnba") else project_hockey
    for p in players:
        props = parse_fn(p)
        if not props: continue
        out.append({
            "name": p["name"],
            "athlete_id": p.get("athlete_id"),
            "team": p.get("team"),
            "team_abbr": p.get("team_abbr"),
            "position": p.get("position"),
            "n_games": p["n_games"],
            "stats": {k: v for k, v in p.items() if k not in
                      ("name", "athlete_id", "team", "team_abbr", "position", "n_games")},
            "props": props,
        })
    # Sort by primary stat desc
    if sport_key in ("nba", "wnba"):
        out.sort(key=lambda p: -(p["stats"].get("pts_per_game") or 0))
    else:
        out.sort(key=lambda p: -(p["stats"].get("points_per_game") or 0))
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        # (2026-11-03) provenance the pages render instead of "last 20 games".
        "status": "unvalidated_model_projection",
        "lines": "model_generated (mean +/- fixed offsets) -- not sportsbook lines",
        "input_blend": src.get("blend"),
        "season": src.get("season"),
        "prior_season": src.get("prior_season"),
        "distribution": _DIST.get(sport_key, "Poisson") if (_nd is not None or sport_key == "nhl") else "Poisson",
        "n_players": len(out),
        "n_props": sum(len(p["props"]) for p in out),
        "players": out,
    }
    out_path = os.path.join(DATA_DIR, f"real_player_props_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, Any]:
    results = {}
    for sport_key in ("nba", "wnba", "nhl"):
        try:
            p = fetch_sport(sport_key)
            results[sport_key] = (p["n_players"], p["n_props"])
        except Exception as e:
            results[sport_key] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    for sport, info in r.items():
        if isinstance(info, tuple):
            print(f"  {sport}: {info[0]} players, {info[1]} prop projections")
        else:
            print(f"  {sport}: {info}")
