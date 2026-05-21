"""
EdgeStat -- NBA team total points (O/U) prop projections.

Common DK lines: 105.5-128.5 team points per game. Per-team O/U.

Method:
  expected_team_pts = team_ortg * opp_drtg / 100  -> scaled to expected possessions
  expected_pts = expected_team_pts * pace_factor
  Normal CDF at nearest 1.0 line within 4.0 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_team_total_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_total_props.json")

LEAGUE_PACE = 99.5
LEAGUE_ORTG = 115.8  # offensive rating: points per 100 possessions
LEAGUE_DRTG = 115.8

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

TEAM_ORTG = {
    "OKC": 118.5, "BOS": 121.5, "DEN": 119.0, "MIN": 113.5, "CLE": 121.0, "NYK": 119.0,
    "DAL": 117.5, "LAL": 118.0, "PHX": 116.5, "MIA": 114.5, "MIL": 117.0, "PHI": 115.5,
    "ATL": 116.5, "MEM": 113.5, "GSW": 117.0, "NOP": 117.5, "IND": 122.0, "SAC": 117.5,
    "ORL": 110.0, "CHI": 115.5, "HOU": 113.5, "DET": 114.5, "TOR": 113.5, "BKN": 113.0,
    "LAC": 116.0, "SAS": 113.5, "UTA": 112.5, "POR": 113.0, "CHA": 112.5, "WAS": 110.0,
}

TEAM_DRTG = {
    "OKC": 106.5, "BOS": 110.5, "MIN": 110.0, "ORL": 111.0, "CLE": 112.5, "MEM": 113.0,
    "NYK": 113.0, "DEN": 113.5, "MIA": 113.0, "PHI": 114.5, "DAL": 113.5, "LAL": 114.5,
    "PHX": 116.0, "GSW": 116.5, "MIL": 115.5, "IND": 117.0, "HOU": 113.5, "ATL": 117.5,
    "SAC": 117.0, "CHI": 117.0, "TOR": 117.5, "BKN": 118.0, "LAC": 113.0, "DET": 118.5,
    "POR": 119.0, "SAS": 118.0, "UTA": 120.0, "CHA": 119.5, "WAS": 122.5, "NOP": 117.0,
}

TEAM_FULL = {
    "memphis grizzlies": "MEM", "washington wizards": "WAS", "indiana pacers": "IND",
    "oklahoma city thunder": "OKC", "sacramento kings": "SAC", "boston celtics": "BOS",
    "denver nuggets": "DEN", "minnesota timberwolves": "MIN", "new york knicks": "NYK",
    "los angeles lakers": "LAL", "miami heat": "MIA", "golden state warriors": "GSW",
    "phoenix suns": "PHX", "cleveland cavaliers": "CLE", "philadelphia 76ers": "PHI",
    "dallas mavericks": "DAL", "milwaukee bucks": "MIL", "atlanta hawks": "ATL",
    "orlando magic": "ORL", "brooklyn nets": "BKN", "detroit pistons": "DET",
    "charlotte hornets": "CHA", "toronto raptors": "TOR", "portland trail blazers": "POR",
    "utah jazz": "UTA", "houston rockets": "HOU", "san antonio spurs": "SAS",
    "new orleans pelicans": "NOP", "chicago bulls": "CHI", "los angeles clippers": "LAC",
}


def _abbr(name: str) -> str:
    if not name: return ""
    return TEAM_FULL.get(name.lower().strip(), name[:3].upper())


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_team(team: str, opp: str, game_pace: float) -> float:
    ortg = TEAM_ORTG.get(team, LEAGUE_ORTG)
    opp_drtg = TEAM_DRTG.get(opp, LEAGUE_DRTG)
    # Combined offensive output: weighted avg of OFF rating vs DEF rating
    eff_rating = (ortg * 0.55 + opp_drtg * 0.45)
    # Points = rating * possessions / 100
    return eff_rating * game_pace / 100


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE)
        game_pace = (home_pace + away_pace) / 2

        # Each side projection
        for team, opp, side in ((home, away, "home"), (away, home, "away")):
            projected = _project_team(team, opp, game_pace)
            # Sigma: team scoring SD ~9-11 points
            sigma = max(8.5, 0.085 * projected)

            edge_class = "NONE"
            best_market = None
            base_line = round(projected) + 0.5
            for line_int in (base_line - 3, base_line - 2, base_line - 1, base_line, base_line + 1, base_line + 2, base_line + 3):
                line = line_int
                if line < 90.5 or line > 145.5: continue
                if abs(projected - line) > 4.0: continue
                p_over = _p_over(projected, sigma, line)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"TEAM_PTS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"TEAM_PTS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "team": team,
                "opp": opp,
                "side": side,
                "game_pace": round(game_pace, 1),
                "team_ortg": TEAM_ORTG.get(team, LEAGUE_ORTG),
                "opp_drtg": TEAM_DRTG.get(opp, LEAGUE_DRTG),
                "projected_pts": round(projected, 1),
                "sigma": round(sigma, 1),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_pts"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_projections": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "NBA team total = (ortg*0.55 + opp_drtg*0.45) * game_pace/100. "
                       "Normal CDF, sigma scaled to 8.5% of projection. STRONG = 10%+ edge.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-tt] {o['n_team_projections']} team projections, {o['n_strong_edges']} strong edges -> {OUT}")
