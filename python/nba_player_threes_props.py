"""
EdgeStat -- NBA player 3-pointers made (3PM) prop projections.

Per-player projected 3PM = season_3pm × pace_factor × opp_3p_defense.
Poisson distribution at typical 0.5 lines.
Common book lines: 1.5, 2.5, 3.5, 4.5 (depending on player).
STRONG when 10%+ edge vs -120 book breakeven (54.5%).

Output: data/nba_player_threes_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_threes_props.json")

LEAGUE_PACE = 99.5
LEAGUE_3P_ALLOWED = 12.7  # NBA league avg 3-pointers allowed per game

# 2024-25 NBA top 3-point shooters (3PM per game)
PLAYER_DB = {
    "stephen curry":            {"team": "GSW", "tpm": 4.5},
    "anthony edwards":          {"team": "MIN", "tpm": 3.5},
    "luka doncic":              {"team": "LAL", "tpm": 3.4},
    "jayson tatum":             {"team": "BOS", "tpm": 3.5},
    "shai gilgeous-alexander":  {"team": "OKC", "tpm": 1.8},
    "tyrese maxey":             {"team": "PHI", "tpm": 3.0},
    "donovan mitchell":         {"team": "CLE", "tpm": 2.9},
    "darius garland":           {"team": "CLE", "tpm": 2.4},
    "kyrie irving":             {"team": "DAL", "tpm": 2.7},
    "jaylen brown":             {"team": "BOS", "tpm": 2.8},
    "derrick white":            {"team": "BOS", "tpm": 3.0},
    "jrue holiday":             {"team": "BOS", "tpm": 1.7},
    "klay thompson":            {"team": "DAL", "tpm": 2.6},
    "buddy hield":              {"team": "GSW", "tpm": 2.8},
    "trae young":               {"team": "ATL", "tpm": 2.6},
    "lamelo ball":              {"team": "CHA", "tpm": 3.5},
    "brandon miller":           {"team": "CHA", "tpm": 2.5},
    "norman powell":            {"team": "LAC", "tpm": 2.6},
    "james harden":             {"team": "LAC", "tpm": 2.8},
    "devin booker":             {"team": "PHX", "tpm": 2.6},
    "kevin durant":             {"team": "PHX", "tpm": 2.5},
    "damian lillard":           {"team": "MIL", "tpm": 3.4},
    "anfernee simons":          {"team": "POR", "tpm": 3.1},
    "coby white":               {"team": "CHI", "tpm": 3.2},
    "donte divincenzo":         {"team": "MIN", "tpm": 3.5},
    "jalen brunson":            {"team": "NYK", "tpm": 2.4},
    "karl-anthony towns":       {"team": "NYK", "tpm": 2.2},
    "mikal bridges":            {"team": "NYK", "tpm": 1.9},
    "jordan poole":             {"team": "WAS", "tpm": 2.7},
    "tyrese haliburton":        {"team": "IND", "tpm": 2.7},
    "pascal siakam":            {"team": "IND", "tpm": 1.7},
    "lauri markkanen":          {"team": "UTA", "tpm": 2.7},
    "isaiah hartenstein":       {"team": "OKC", "tpm": 0.5},
    "chet holmgren":            {"team": "OKC", "tpm": 1.5},
    "jalen williams":           {"team": "OKC", "tpm": 1.7},
    "victor wembanyama":        {"team": "SAS", "tpm": 2.2},
    "chris paul":               {"team": "SAS", "tpm": 1.5},
    "devin vassell":            {"team": "SAS", "tpm": 1.9},
    "cade cunningham":          {"team": "DET", "tpm": 2.4},
    "jalen suggs":              {"team": "ORL", "tpm": 1.5},
    "paolo banchero":           {"team": "ORL", "tpm": 1.5},
    "scottie barnes":           {"team": "TOR", "tpm": 1.5},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

# Per-team 3PA allowed per game (proxy for 3P defense). League avg ~13.5
TEAM_3P_DEFENSE = {
    "MEM": 13.0, "WAS": 14.5, "IND": 13.5, "OKC": 12.0, "SAC": 13.8, "BOS": 12.8,
    "DEN": 13.2, "MIN": 12.3, "NYK": 12.5, "LAL": 13.5, "MIA": 12.5, "GSW": 13.2,
    "PHX": 13.4, "CLE": 12.5, "PHI": 13.0, "DAL": 13.0, "MIL": 13.5, "ATL": 13.8,
    "ORL": 11.5, "BKN": 13.5, "DET": 14.0, "CHA": 14.2, "TOR": 13.2, "POR": 14.0,
    "UTA": 14.0, "HOU": 12.5, "SAS": 13.2, "NOP": 13.5, "CHI": 13.5, "LAC": 12.8,
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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


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
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE)
        home_def = TEAM_3P_DEFENSE.get(home, 13.5)
        away_def = TEAM_3P_DEFENSE.get(away, 13.5)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_def = away_def if is_home else home_def
            # Opp_3p_defense: 13.5 = league avg, higher = worse defense (more 3s allowed)
            opp_def_factor = opp_def / 13.5

            # Prefer REAL ESPN 3PM with hardcoded fallback (2026-05-21 data integrity)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nba", player_name, "threes_per_game",
                                       fallback=info["tpm"], min_games=5)
                base_tpm = stat["value"]
                tpm_source = stat["source"]
            except Exception:
                base_tpm = info["tpm"]
                tpm_source = "fallback"
            projected_tpm = base_tpm * pace_factor * opp_def_factor

            # Nearest 0.5 line (book sets right at expected)
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_tpm * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_tpm - line) > 0.75: continue
                # P(>= floor(line)+1)
                p_over = _poisson_at_least(int(line) + 1, projected_tpm)
                p_under = 1 - p_over
                # Lock STRONG to ±10% edge over -120 (54.5% breakeven), capped at 72%
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"3PM_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"3PM_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_tpm": round(base_tpm, 2),
                "tpm_source": tpm_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_3p_defense": opp_def,
                "opp_def_factor": round(opp_def_factor, 3),
                "projected_tpm": round(projected_tpm, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_tpm"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player 3PM × pace × opp_3p_defense. Poisson at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-3pm] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
