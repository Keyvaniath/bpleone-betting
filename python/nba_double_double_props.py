"""
EdgeStat -- NBA player double-double yes/no prop projections.

A double-double = 10+ in two of (PTS, REB, AST, STL, BLK).
Common book line: -200 for big men, +200 to +500 for guards.

Method:
  Joint probability that a player hits 10+ in 2+ categories.
  P(DD) = sum over pairs (cat1, cat2) of P(cat1>=10 AND cat2>=10)
        ≈ sum of marginal P(cat>=10) products (Bonferroni approximation)

Using Normal CDF on PTS, REB, AST with sigmas; player-specific BPG, SPG.

Output: data/nba_double_double_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_double_double_props.json")

LEAGUE_PACE = 99.5

# Top NBA double-double producers + their PPG/RPG/APG
PLAYER_DB = {
    "nikola jokic":         {"team": "DEN", "ppg": 28.5, "rpg": 13.7, "apg": 10.0},
    "domantas sabonis":     {"team": "SAC", "ppg": 20.5, "rpg": 12.5, "apg": 8.0},
    "anthony davis":        {"team": "LAL", "ppg": 24.5, "rpg": 12.8, "apg": 3.8},
    "giannis antetokounmpo":{"team": "MIL", "ppg": 30.4, "rpg": 11.7, "apg": 6.0},
    "karl-anthony towns":   {"team": "NYK", "ppg": 21.8, "rpg": 12.5, "apg": 3.2},
    "victor wembanyama":    {"team": "SAS", "ppg": 24.3, "rpg": 11.5, "apg": 3.7},
    "alperen sengun":       {"team": "HOU", "ppg": 19.0, "rpg": 9.5,  "apg": 4.9},
    "rudy gobert":          {"team": "MIN", "ppg": 12.0, "rpg": 12.0, "apg": 2.0},
    "ivica zubac":          {"team": "LAC", "ppg": 12.5, "rpg": 12.3, "apg": 2.0},
    "evan mobley":          {"team": "CLE", "ppg": 17.0, "rpg": 9.5,  "apg": 3.0},
    "jaren jackson jr":     {"team": "MEM", "ppg": 22.0, "rpg": 5.5,  "apg": 2.0},
    "jarrett allen":        {"team": "CLE", "ppg": 13.5, "rpg": 9.7,  "apg": 2.5},
    "deandre ayton":        {"team": "POR", "ppg": 16.5, "rpg": 10.5, "apg": 1.5},
    "isaiah hartenstein":   {"team": "OKC", "ppg": 11.0, "rpg": 11.0, "apg": 3.5},
    "luka doncic":          {"team": "LAL", "ppg": 28.5, "rpg": 8.5,  "apg": 8.0},
    "lebron james":         {"team": "LAL", "ppg": 25.0, "rpg": 7.3,  "apg": 8.2},
    "trae young":           {"team": "ATL", "ppg": 22.0, "rpg": 3.0,  "apg": 11.2},
    "tyrese haliburton":    {"team": "IND", "ppg": 18.6, "rpg": 3.5,  "apg": 9.3},
    "shai gilgeous-alexander":{"team": "OKC", "ppg": 32.7, "rpg": 5.0, "apg": 6.2},
    "ja morant":            {"team": "MEM", "ppg": 23.0, "rpg": 4.0,  "apg": 7.6},
    "lamelo ball":          {"team": "CHA", "ppg": 25.0, "rpg": 5.3,  "apg": 7.1},
    "cade cunningham":      {"team": "DET", "ppg": 24.5, "rpg": 6.0,  "apg": 9.1},
    "scottie barnes":       {"team": "TOR", "ppg": 19.5, "rpg": 7.4,  "apg": 5.0},
    "paolo banchero":       {"team": "ORL", "ppg": 25.0, "rpg": 7.0,  "apg": 5.0},
    "franz wagner":         {"team": "ORL", "ppg": 24.0, "rpg": 5.5,  "apg": 4.5},
    "jalen brunson":        {"team": "NYK", "ppg": 26.0, "rpg": 4.0,  "apg": 7.3},
    "donovan mitchell":     {"team": "CLE", "ppg": 24.2, "rpg": 4.5,  "apg": 5.0},
    "jayson tatum":         {"team": "BOS", "ppg": 26.8, "rpg": 8.7,  "apg": 5.8},
    "tyrese maxey":         {"team": "PHI", "ppg": 26.0, "rpg": 3.5,  "apg": 6.0},
    "kyrie irving":         {"team": "DAL", "ppg": 25.0, "rpg": 4.5,  "apg": 4.7},
    "anthony edwards":      {"team": "MIN", "ppg": 27.6, "rpg": 5.5,  "apg": 4.5},
    "james harden":         {"team": "LAC", "ppg": 19.0, "rpg": 5.0,  "apg": 8.5},
    "chris paul":           {"team": "SAS", "ppg": 9.0,  "rpg": 3.5,  "apg": 7.3},
    "stephen curry":        {"team": "GSW", "ppg": 24.5, "rpg": 4.5,  "apg": 6.2},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
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


def _p_at_least_10(mean: float, sigma: float) -> float:
    z = (mean - 10) / sigma
    return _norm_cdf(z)


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
        pace_factor = (TEAM_PACE.get(home, LEAGUE_PACE) + TEAM_PACE.get(away, LEAGUE_PACE)) / 2 / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            # Real ESPN stats with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                _p = get_player_stat("nba", player_name, "pts_per_game", fallback=info["ppg"], min_games=5)
                _r = get_player_stat("nba", player_name, "reb_per_game", fallback=info["rpg"], min_games=5)
                _a = get_player_stat("nba", player_name, "ast_per_game", fallback=info["apg"], min_games=5)
                dd_source = _p["source"]
                ppg = _p["value"] * pace_factor
                rpg = _r["value"] * pace_factor
                apg = _a["value"] * pace_factor
            except Exception:
                dd_source = "fallback"
                ppg = info["ppg"] * pace_factor
                rpg = info["rpg"] * pace_factor
                apg = info["apg"] * pace_factor
            # Sigmas
            sig_p = max(4.0, 0.25 * ppg)
            sig_r = max(1.8, 0.22 * rpg)
            sig_a = max(1.5, 0.30 * apg)

            p_p10 = _p_at_least_10(ppg, sig_p)
            p_r10 = _p_at_least_10(rpg, sig_r)
            p_a10 = _p_at_least_10(apg, sig_a)

            # P(double-double) ~ P(P10 AND R10) + P(P10 AND A10) + P(R10 AND A10) - 2 × triple
            # Using approximation: P(DD) = 1 - P(0 or 1 of three categories hit 10)
            p_at_most_one = (
                (1-p_p10)*(1-p_r10)*(1-p_a10) +  # zero
                p_p10*(1-p_r10)*(1-p_a10) +
                (1-p_p10)*p_r10*(1-p_a10) +
                (1-p_p10)*(1-p_r10)*p_a10
            )
            p_dd = 1 - p_at_most_one
            p_no_dd = 1 - p_dd

            edge_class = "NONE"
            best_market = None
            # Book lines: big men -200 (67%%) to -150 (60%%). Guards +200 to +400.
            # STRONG_YES if model says 70-85%% (vs -200 book = 67%%)
            # STRONG_NO if model says >= 70%% (player won't get DD when book gives +200)
            if 0.70 <= p_dd <= 0.85:
                edge_class = "STRONG_YES"
                best_market = {"market": "DOUBLE_DOUBLE_YES", "p": round(p_dd, 3),
                               "fair_odds": _american(p_dd)}
            elif 0.20 <= p_dd <= 0.35:
                edge_class = "STRONG_NO"
                best_market = {"market": "DOUBLE_DOUBLE_NO", "p": round(p_no_dd, 3),
                               "fair_odds": _american(p_no_dd)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "ppg_proj": round(ppg, 1),
                "rpg_proj": round(rpg, 1),
                "apg_proj": round(apg, 1),
                "p_p10": round(p_p10, 3),
                "p_r10": round(p_r10, 3),
                "p_a10": round(p_a10, 3),
                "p_double_double": round(p_dd, 3),
                "p_no_dd": round(p_no_dd, 3),
                "fair_yes": _american(p_dd),
                "fair_no": _american(p_no_dd),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_double_double"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_strong": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "P(DD) computed from three marginal P(category >= 10) via Bonferroni-style "
                       "P(at least 2 of 3 hit 10). Sigmas scaled to projection.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-dd] {o['n_players']} players, {o['n_strong']} strong -> {OUT}")
