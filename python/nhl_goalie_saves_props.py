"""
EdgeStat -- NHL goalie saves prop projections.

Common DK/FD lines:
  - Saves 25.5, 27.5, 29.5, 31.5 over/under

Approach:
  expected_saves = expected_shots_against × SV%
  expected_shots_against = opp_shots_per_game (league avg ~31)
  SV% = goalie's recent SV% (clamped 0.88-0.94)

Normal CDF around projection with sigma ~ 4.5 saves.

Output: data/nhl_goalie_saves_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_saves_props.json")

LEAGUE_SHOTS_PER_GAME = 31.0
SAVES_STDDEV = 4.5

# 2024-25 NHL playoff-active goalies + SV% + recent form
GOALIE_DB = {
    "sergei bobrovsky":   {"team": "FLA", "sv_pct": 0.916, "team_workload": 0.95},
    "stuart skinner":     {"team": "EDM", "sv_pct": 0.907, "team_workload": 1.05},
    "frederik andersen":  {"team": "CAR", "sv_pct": 0.928, "team_workload": 0.88},
    "pyotr kochetkov":    {"team": "CAR", "sv_pct": 0.910, "team_workload": 0.90},
    "logan thompson":     {"team": "WSH", "sv_pct": 0.920, "team_workload": 1.05},
    "charlie lindgren":   {"team": "WSH", "sv_pct": 0.914, "team_workload": 1.02},
    "ilya sorokin":       {"team": "NYI", "sv_pct": 0.913, "team_workload": 1.10},
    "igor shesterkin":    {"team": "NYR", "sv_pct": 0.917, "team_workload": 0.95},
    "jeremy swayman":     {"team": "BOS", "sv_pct": 0.910, "team_workload": 1.00},
    "linus ullmark":      {"team": "OTT", "sv_pct": 0.910, "team_workload": 1.05},
    "anthony stolarz":    {"team": "TOR", "sv_pct": 0.926, "team_workload": 0.98},
    "joseph woll":        {"team": "TOR", "sv_pct": 0.915, "team_workload": 0.97},
    "andrei vasilevskiy": {"team": "TBL", "sv_pct": 0.917, "team_workload": 0.95},
    "connor hellebuyck":  {"team": "WPG", "sv_pct": 0.921, "team_workload": 0.92},
    "juuse saros":        {"team": "NSH", "sv_pct": 0.908, "team_workload": 1.05},
    "thatcher demko":     {"team": "VAN", "sv_pct": 0.914, "team_workload": 1.02},
    "kevin lankinen":     {"team": "VAN", "sv_pct": 0.908, "team_workload": 1.00},
    "adin hill":          {"team": "VGK", "sv_pct": 0.911, "team_workload": 0.93},
    "logan thompson_2":   {"team": "VGK", "sv_pct": 0.918, "team_workload": 0.95},
    "mackenzie blackwood":{"team": "COL", "sv_pct": 0.915, "team_workload": 0.95},
    "jake oettinger":     {"team": "DAL", "sv_pct": 0.911, "team_workload": 0.92},
    "casey desmith":      {"team": "DAL", "sv_pct": 0.905, "team_workload": 0.95},
    "filip gustavsson":   {"team": "MIN", "sv_pct": 0.911, "team_workload": 1.00},
    "marc-andre fleury":  {"team": "MIN", "sv_pct": 0.895, "team_workload": 1.00},
    "calvin pickard":     {"team": "EDM", "sv_pct": 0.900, "team_workload": 1.00},
    "vitek vanecek":      {"team": "SJS", "sv_pct": 0.895, "team_workload": 1.15},
    "ukko-pekka luukkonen":{"team": "BUF","sv_pct": 0.908, "team_workload": 1.05},
    "tristan jarry":      {"team": "PIT", "sv_pct": 0.903, "team_workload": 1.05},
    "alex nedeljkovic":   {"team": "PIT", "sv_pct": 0.901, "team_workload": 1.05},
    "samsonov ilya":      {"team": "VGK", "sv_pct": 0.902, "team_workload": 0.95},
}


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
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue

        # Try abbreviation match
        teams_in_game = set([home, away, home[:3], away[:3]])

        for goalie_name, info in GOALIE_DB.items():
            if info["team"] not in teams_in_game: continue
            is_home = info["team"] == home or info["team"] == home[:3]

            # Expected shots against = league avg × opponent workload factor
            # No team-specific shot data available, use league avg
            expected_sa = LEAGUE_SHOTS_PER_GAME * info["team_workload"]
            sv_pct = max(0.88, min(0.94, info["sv_pct"]))
            expected_saves = expected_sa * sv_pct

            # Edge classification at nearest 0.5 line within 1.0 saves of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(expected_saves * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 20.5: continue
                if abs(expected_saves - line) > 1.0: continue
                z = (expected_saves - line) / SAVES_STDDEV
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"SAVES_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"SAVES_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "goalie": goalie_name,
                "team": info["team"],
                "sv_pct": sv_pct,
                "expected_shots_against": round(expected_sa, 1),
                "expected_saves": round(expected_saves, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["expected_saves"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_goalies_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_goalies_in_db": len(GOALIE_DB),
        "method_note": "expected_saves = league_shots_per_game × team_workload × SV%%. "
                       "Normal CDF with sigma=4.5. STRONG only at nearest 0.5 line within "
                       "1.0 of projection with 10%%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[goalie-saves] {o['n_goalies_projected']} goalies, {o['n_strong_edges']} strong edges -> {OUT}")
