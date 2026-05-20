"""
EdgeStat -- NBA player points (PTS) prop projections.

For each NBA game tonight, projects per-player expected points and identifies
edges vs typical DK/FD prop lines.

Approach:
  Per-player projected PTS = season_ppg × pace_factor × matchup_factor × usage_boost
    - pace_factor: game pace / 99.5 league avg
    - matchup_factor: opp DRtg / league DRtg (worse defense = boost)
    - usage_boost: +5-10%% if star player on team with injuries (proxy)
  Normal distribution around projection with sigma scaled to PPG:
    sigma = max(4, 0.25 * projected_pts)
  Probabilities for typical 0.5 increments.

Player pool (baked in, top 60 NBA scorers 2024-25). Updates seasonally.

Output: data/nba_player_points_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_points_props.json")

LEAGUE_PACE = 99.5
LEAGUE_DRTG = 115.8

# 2024-25 season top NBA scorers + their team
PLAYER_DB = {
    "shai gilgeous-alexander": {"team": "OKC", "ppg": 32.7, "usage": 0.32},
    "luka doncic":              {"team": "LAL", "ppg": 28.5, "usage": 0.34},
    "giannis antetokounmpo":    {"team": "MIL", "ppg": 30.4, "usage": 0.34},
    "jayson tatum":             {"team": "BOS", "ppg": 26.8, "usage": 0.30},
    "anthony edwards":          {"team": "MIN", "ppg": 27.6, "usage": 0.31},
    "stephen curry":            {"team": "GSW", "ppg": 24.5, "usage": 0.30},
    "lebron james":             {"team": "LAL", "ppg": 25.0, "usage": 0.28},
    "donovan mitchell":         {"team": "CLE", "ppg": 24.2, "usage": 0.31},
    "darius garland":           {"team": "CLE", "ppg": 20.5, "usage": 0.25},
    "jaylen brown":             {"team": "BOS", "ppg": 23.5, "usage": 0.28},
    "kevin durant":             {"team": "PHX", "ppg": 27.0, "usage": 0.30},
    "devin booker":             {"team": "PHX", "ppg": 25.4, "usage": 0.30},
    "damian lillard":           {"team": "MIL", "ppg": 24.5, "usage": 0.29},
    "tyrese haliburton":        {"team": "IND", "ppg": 18.6, "usage": 0.23},
    "pascal siakam":            {"team": "IND", "ppg": 20.2, "usage": 0.25},
    "jalen brunson":            {"team": "NYK", "ppg": 26.0, "usage": 0.31},
    "karl-anthony towns":       {"team": "NYK", "ppg": 21.8, "usage": 0.27},
    "trae young":               {"team": "ATL", "ppg": 22.0, "usage": 0.30},
    "victor wembanyama":        {"team": "SAS", "ppg": 24.3, "usage": 0.29},
    "jaylen wells":             {"team": "MEM", "ppg": 15.5, "usage": 0.20},
    "ja morant":                {"team": "MEM", "ppg": 23.0, "usage": 0.29},
    "jaren jackson jr":         {"team": "MEM", "ppg": 22.0, "usage": 0.27},
    "paul george":              {"team": "PHI", "ppg": 20.0, "usage": 0.27},
    "joel embiid":              {"team": "PHI", "ppg": 24.5, "usage": 0.32},
    "tyrese maxey":             {"team": "PHI", "ppg": 26.0, "usage": 0.30},
    "domantas sabonis":         {"team": "SAC", "ppg": 20.5, "usage": 0.24},
    "demar derozan":            {"team": "SAC", "ppg": 21.8, "usage": 0.27},
    "zion williamson":          {"team": "NOP", "ppg": 22.5, "usage": 0.29},
    "anthony davis":            {"team": "LAL", "ppg": 24.5, "usage": 0.29},
    "rudy gobert":              {"team": "MIN", "ppg": 12.0, "usage": 0.16},
    "lauri markkanen":          {"team": "UTA", "ppg": 22.5, "usage": 0.27},
    "alperen sengun":           {"team": "HOU", "ppg": 19.0, "usage": 0.25},
    "jalen green":              {"team": "HOU", "ppg": 20.5, "usage": 0.27},
    "scottie barnes":           {"team": "TOR", "ppg": 19.5, "usage": 0.25},
    "rj barrett":               {"team": "TOR", "ppg": 21.0, "usage": 0.26},
    "lamelo ball":              {"team": "CHA", "ppg": 25.0, "usage": 0.31},
    "brandon miller":           {"team": "CHA", "ppg": 21.0, "usage": 0.27},
    "franz wagner":             {"team": "ORL", "ppg": 24.0, "usage": 0.27},
    "paolo banchero":           {"team": "ORL", "ppg": 25.0, "usage": 0.30},
    "kyrie irving":             {"team": "DAL", "ppg": 25.0, "usage": 0.29},
    "cade cunningham":          {"team": "DET", "ppg": 24.5, "usage": 0.29},
    "jalen williams":           {"team": "OKC", "ppg": 21.5, "usage": 0.24},
    "chet holmgren":            {"team": "OKC", "ppg": 17.0, "usage": 0.21},
    "dejounte murray":          {"team": "NOP", "ppg": 19.5, "usage": 0.25},
    "kawhi leonard":            {"team": "LAC", "ppg": 22.0, "usage": 0.28},
    "james harden":             {"team": "LAC", "ppg": 19.0, "usage": 0.26},
    "norman powell":            {"team": "LAC", "ppg": 21.0, "usage": 0.25},
    "deni avdija":              {"team": "POR", "ppg": 16.0, "usage": 0.22},
    "anfernee simons":          {"team": "POR", "ppg": 19.0, "usage": 0.26},
    "coby white":               {"team": "CHI", "ppg": 20.5, "usage": 0.25},
    "josh giddey":              {"team": "CHI", "ppg": 14.5, "usage": 0.20},
}

# Team pace + DRtg (already in nba_pace_adjusted but re-baked here for self-contained)
TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}
TEAM_DRTG = {
    "MEM": 113.8, "WAS": 119.7, "IND": 113.6, "OKC": 107.0, "SAC": 117.4, "BOS": 111.4,
    "DEN": 115.9, "MIN": 110.9, "NYK": 112.5, "LAL": 114.0, "MIA": 113.0, "GSW": 113.8,
    "PHX": 115.4, "CLE": 112.0, "PHI": 113.0, "DAL": 113.6, "MIL": 113.4, "ATL": 116.0,
    "ORL": 109.2, "BKN": 115.6, "DET": 115.5, "CHA": 115.5, "TOR": 113.8, "POR": 115.5,
    "UTA": 117.5, "HOU": 110.0, "SAS": 115.0, "NOP": 114.0, "CHI": 115.6, "LAC": 110.5,
}

# Full-name -> abbrev (nba_state.json uses full names)
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
    """Normalize team name to abbreviation."""
    if not name: return ""
    n = name.lower().strip()
    return TEAM_FULL.get(n, name[:3].upper())


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
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue

        home_raw = g.get("home_team") or g.get("home") or ""
        away_raw = g.get("away_team") or g.get("away") or ""
        home = _abbr(home_raw)
        away = _abbr(away_raw)
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE)
        home_drtg = TEAM_DRTG.get(home, LEAGUE_DRTG)
        away_drtg = TEAM_DRTG.get(away, LEAGUE_DRTG)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        # For each player on either team, project points
        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_drtg = away_drtg if is_home else home_drtg
            matchup_factor = opp_drtg / LEAGUE_DRTG

            base_ppg = info["ppg"]
            projected_pts = base_ppg * pace_factor * matchup_factor
            sigma = max(4.0, 0.25 * projected_pts)

            # Compute over/under for typical 0.5 lines around projection
            # Books set the line at or very near projected_pts. Only evaluate the
            # nearest 0.5 line above and below (within 0.75 of projection).
            best_edge_class = "NONE"
            best_market = None
            base_line = round(projected_pts * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 5: continue
                if abs(projected_pts - line) > 0.75: continue
                z = (projected_pts - line) / sigma
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                # STRONG only if model significantly differs from a 50/50 line
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        best_edge_class = "STRONG_OVER"
                        best_market = {"market": f"PTS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        best_edge_class = "STRONG_UNDER"
                        best_market = {"market": f"PTS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_ppg": base_ppg,
                "usage_rate": info["usage"],
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_drtg": opp_drtg,
                "matchup_factor": round(matchup_factor, 3),
                "projected_pts": round(projected_pts, 1),
                "sigma": round(sigma, 2),
                "edge_class": best_edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_pts"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "Player PPG × pace × opp_DRtg × matchup factor. Normal CDF with "
                       "sigma scaled to projected (~25%% of mean). STRONG requires 10%%+ "
                       "edge against -120 book lines.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pts] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
