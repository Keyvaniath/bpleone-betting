"""
EdgeStat -- WNBA team alt-totals + 1H/1Q + alt-spread props.

Mirror of nba_team_alts_props.py for the WNBA. Lower sigma since WNBA games
are 40 minutes vs 48 NBA (about 83% game length) -- variance scales.

Output: data/wnba_team_alts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from wnba_scoring_env import game_env_factor


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_team_alts_props.json")

WNBA_TEAM_STDDEV = 9.0
WNBA_H1_STDDEV = 6.5
WNBA_Q1_STDDEV = 3.5

LEAGUE_PACE_WNBA = 78.0
LEAGUE_ORTG_WNBA = 100.5

TEAM_PACE = {
    "ATL": 82.5, "CHI": 79.8, "CONN": 78.2, "DAL": 80.5, "IND": 84.1, "LA": 79.6,
    "LV":  82.8, "MIN": 78.5, "NY":  77.8, "PHX": 80.1, "SEA": 79.0, "WAS": 79.5,
}
TEAM_DRTG = {
    "ATL": 102.0, "CHI": 104.5, "CONN": 95.5, "DAL": 103.2, "IND": 105.0, "LA": 103.8,
    "LV":  96.8,  "MIN": 95.2,  "NY": 96.0,   "PHX": 100.5, "SEA": 99.0,  "WAS": 105.8,
}
TEAM_ORTG = {
    "ATL": 100.5, "CHI": 96.8, "CONN": 102.0, "DAL": 99.5, "IND": 100.0, "LA": 96.0,
    "LV": 106.0,  "MIN": 105.0, "NY": 104.5,  "PHX": 102.5, "SEA": 101.0, "WAS": 95.5,
}

TEAM_FULL = {
    "atlanta dream": "ATL", "chicago sky": "CHI", "connecticut sun": "CONN",
    "dallas wings": "DAL", "indiana fever": "IND", "los angeles sparks": "LA",
    "las vegas aces": "LV", "minnesota lynx": "MIN", "new york liberty": "NY",
    "phoenix mercury": "PHX", "seattle storm": "SEA", "washington mystics": "WAS",
}


def _abbr(name: str) -> str:
    if not name: return ""
    return TEAM_FULL.get(name.lower().strip(), name[:3].upper())


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE_WNBA)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE_WNBA)
        home_ortg = TEAM_ORTG.get(home, LEAGUE_ORTG_WNBA)
        away_ortg = TEAM_ORTG.get(away, LEAGUE_ORTG_WNBA)
        home_drtg = TEAM_DRTG.get(home, LEAGUE_ORTG_WNBA)
        away_drtg = TEAM_DRTG.get(away, LEAGUE_ORTG_WNBA)
        game_pace = (home_pace + away_pace) / 2
        # live scoring-environment trim scales both teams symmetrically
        env, _env = game_env_factor(g.get("home_team") or "", g.get("away_team") or "")
        game_pace *= env

        # Each team's effective points = pace × (their ORtg + opp DRtg) / 2 / 100
        home_pts = game_pace * (home_ortg + away_drtg) / 2 / 100
        away_pts = game_pace * (away_ortg + home_drtg) / 2 / 100
        total = home_pts + away_pts
        spread = home_pts - away_pts

        # Build alt-lines per team
        team_alts = []
        for offset in (-5.5, -3.5, 1.5, 3.5, 5.5):
            for is_home in (True, False):
                base_proj = home_pts if is_home else away_pts
                line = base_proj + offset
                z = (base_proj - line) / WNBA_TEAM_STDDEV
                p_over = _norm_cdf(z)
                team_alts.append({
                    "team": "HOME" if is_home else "AWAY",
                    "line": round(line, 1),
                    "offset_from_proj": offset,
                    "p_over": round(p_over, 3),
                    "p_under": round(1 - p_over, 3),
                })

        h1_total = total * 0.50  # WNBA halves are exactly 50/50 (20 min each)
        q1_total = total * 0.25
        h1_lines = []
        for line in [h1_total - 2.0, h1_total, h1_total + 2.0]:
            z = (h1_total - line) / (WNBA_H1_STDDEV * 1.41)
            h1_lines.append({"line": round(line, 1), "p_over": round(_norm_cdf(z), 3),
                            "p_under": round(1 - _norm_cdf(z), 3)})

        q1_lines = []
        for line in [q1_total - 1.5, q1_total, q1_total + 1.5]:
            z = (q1_total - line) / (WNBA_Q1_STDDEV * 1.41)
            q1_lines.append({"line": round(line, 1), "p_over": round(_norm_cdf(z), 3),
                            "p_under": round(1 - _norm_cdf(z), 3)})

        edge_class = "NONE"
        best_market = None
        for ta in team_alts:
            for direction, p in (("OVER", ta["p_over"]), ("UNDER", ta["p_under"])):
                if 0.62 <= p <= 0.72:
                    if not best_market or p > best_market["p"]:
                        edge_class = f"STRONG_{direction}"
                        best_market = {"market": f"{ta['team']}_TOTAL_{direction}_{ta['line']}",
                                       "p": round(p, 3),
                                       "fair_odds": _american(p)}

        rows.append({
            "matchup": f"{away} @ {home}",
            "home_team": home, "away_team": away,
            "game_pace": round(game_pace, 1),
            "home_pts_proj": round(home_pts, 1),
            "away_pts_proj": round(away_pts, 1),
            "total_proj": round(total, 1),
            "h1_total_proj": round(h1_total, 1),
            "q1_total_proj": round(q1_total, 1),
            "spread_proj": round(spread, 1),
            "team_alts": team_alts,
            "h1_lines": h1_lines,
            "q1_lines": q1_lines,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong": len(strong),
        "method_note": "Normal team-points distribution (sigma=9). H1 = 50%% (40-min game), "
                       "Q1 = 25%%. Alt-lines at +/- 1.5/3.5/5.5 from projection.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-alts] {o['n_games']} games, {o['n_strong']} strong -> {OUT}")
