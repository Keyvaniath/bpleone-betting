"""
EdgeStat -- NBA player blocks + steals prop projections.

Niche but very profitable markets. Common book lines:
  - Blocks 0.5, 1.5, 2.5 (Wemby gets 3+ regularly)
  - Steals 0.5, 1.5, 2.5

Per-player BPG + SPG baseline. Pace_factor adjustment.
Poisson distribution since counts are small.

Output: data/nba_player_blocks_steals_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_blocks_steals_props.json")

LEAGUE_PACE = 99.5

# 2024-25 NBA top BPG + SPG players
PLAYER_DB = {
    "victor wembanyama":        {"team": "SAS", "bpg": 3.7, "spg": 1.2},
    "rudy gobert":              {"team": "MIN", "bpg": 2.1, "spg": 0.7},
    "chet holmgren":            {"team": "OKC", "bpg": 2.4, "spg": 0.7},
    "anthony davis":            {"team": "LAL", "bpg": 2.3, "spg": 1.2},
    "myles turner":             {"team": "IND", "bpg": 2.0, "spg": 0.7},
    "jaren jackson jr":         {"team": "MEM", "bpg": 2.1, "spg": 1.2},
    "brook lopez":              {"team": "MIL", "bpg": 2.4, "spg": 0.5},
    "walker kessler":           {"team": "UTA", "bpg": 2.4, "spg": 0.5},
    "evan mobley":              {"team": "CLE", "bpg": 1.4, "spg": 0.7},
    "ivica zubac":              {"team": "LAC", "bpg": 1.3, "spg": 0.7},
    "isaiah hartenstein":       {"team": "OKC", "bpg": 1.1, "spg": 1.1},
    "alex sarr":                {"team": "WAS", "bpg": 1.5, "spg": 0.7},
    # Steals leaders
    "shai gilgeous-alexander":  {"team": "OKC", "bpg": 1.0, "spg": 1.7},
    "jaylin williams":          {"team": "OKC", "bpg": 0.5, "spg": 1.0},
    "dyson daniels":            {"team": "ATL", "bpg": 0.4, "spg": 3.0},
    "matisse thybulle":         {"team": "POR", "bpg": 0.4, "spg": 1.8},
    "de'aaron fox":             {"team": "SAS", "bpg": 0.5, "spg": 1.7},
    "jrue holiday":             {"team": "BOS", "bpg": 0.7, "spg": 0.9},
    "alex caruso":              {"team": "OKC", "bpg": 0.4, "spg": 1.7},
    "trae young":               {"team": "ATL", "bpg": 0.1, "spg": 1.1},
    "lamelo ball":              {"team": "CHA", "bpg": 0.3, "spg": 1.4},
    "anthony edwards":          {"team": "MIN", "bpg": 0.5, "spg": 1.0},
    "luguentz dort":            {"team": "OKC", "bpg": 0.3, "spg": 1.4},
    "jaylen brown":             {"team": "BOS", "bpg": 0.3, "spg": 1.1},
    "jrue holiday":             {"team": "BOS", "bpg": 0.7, "spg": 0.9},
    # Two-way wings
    "scottie barnes":           {"team": "TOR", "bpg": 1.5, "spg": 1.3},
    "amen thompson":            {"team": "HOU", "bpg": 1.0, "spg": 1.3},
    "rj barrett":               {"team": "TOR", "bpg": 0.3, "spg": 0.7},
    "donovan mitchell":         {"team": "CLE", "bpg": 0.5, "spg": 1.3},
    "kawhi leonard":            {"team": "LAC", "bpg": 0.6, "spg": 1.6},
    "paolo banchero":           {"team": "ORL", "bpg": 0.7, "spg": 0.8},
    "franz wagner":             {"team": "ORL", "bpg": 0.5, "spg": 1.1},
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
        pace_factor = (home_pace + away_pace) / 2 / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            base_bpg = info["bpg"]
            base_spg = info["spg"]
            proj_b = base_bpg * pace_factor
            proj_s = base_spg * pace_factor

            # Block lines: 0.5, 1.5, 2.5
            # Steal lines: 0.5, 1.5, 2.5
            p_b_1plus = _poisson_at_least(1, proj_b)
            p_b_2plus = _poisson_at_least(2, proj_b)
            p_s_1plus = _poisson_at_least(1, proj_s)
            p_s_2plus = _poisson_at_least(2, proj_s)

            edge_class = "NONE"
            best_market = None
            # STRONG when 10%+ edge vs -120 book
            for market, p in [
                ("BLOCKS_OVER_0.5", p_b_1plus), ("BLOCKS_OVER_1.5", p_b_2plus),
                ("STEALS_OVER_0.5", p_s_1plus), ("STEALS_OVER_1.5", p_s_2plus),
            ]:
                if 0.62 <= p <= 0.72:
                    if not best_market or p > best_market["p"]:
                        edge_class = f"STRONG_{market}"
                        best_market = {"market": market, "p": round(p, 3),
                                       "fair_odds": _american(p)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "season_bpg": base_bpg,
                "season_spg": base_spg,
                "projected_b": round(proj_b, 2),
                "projected_s": round(proj_s, 2),
                "p_b_1_plus": round(p_b_1plus, 3),
                "p_b_2_plus": round(p_b_2plus, 3),
                "p_s_1_plus": round(p_s_1plus, 3),
                "p_s_2_plus": round(p_s_2plus, 3),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -(r["projected_b"] + r["projected_s"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "Per-player BPG/SPG × pace_factor. Poisson at 0.5/1.5 lines. "
                       "STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-blk-stl] {o['n_players_projected']} players, {o['n_strong']} strong -> {OUT}")
