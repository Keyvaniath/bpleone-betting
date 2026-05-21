"""
EdgeStat -- MLB team stolen base total prop projections.

Niche DK market:
  - Team total SB 1.5 over/under (usually -150 to +150)
  - Team total SB 2.5 (for high-running teams like CIN, KC, NYM)

Per-team SB rate per game baseline (2024-25 season):
  CIN 1.42, KC 1.20, ATL 1.05, NYM 0.95, TBR 0.92, LAD 0.85, ARI 0.85
  ...lots of teams ~ 0.5-0.7
  Tigers, Rockies, Marlins at ~ 0.3-0.4

Adjusters:
  - Opp catcher pop time (already have mlb_catcher_framing.py with arm data)
  - Opp pitcher delivery (mlb_steal_props.py has the slow-pitcher DB)

Output: data/mlb_team_sb_total_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_sb_total_props.json")

# 2024-25 team SB per game (May 2026 data)
TEAM_SB_PER_GAME = {
    "CIN": 1.42, "KC": 1.20, "ATL": 1.05, "NYM": 0.95, "TBR": 0.92,
    "LAD": 0.85, "ARI": 0.85, "TEX": 0.80, "HOU": 0.78, "SDP": 0.75,
    "SEA": 0.70, "STL": 0.68, "MIL": 0.68, "BAL": 0.65, "NYY": 0.62,
    "TOR": 0.62, "BOS": 0.58, "PHI": 0.55, "OAK": 0.55, "CWS": 0.52,
    "CHC": 0.52, "MIN": 0.50, "CLE": 0.50, "SFG": 0.48, "WAS": 0.45,
    "LAA": 0.42, "PIT": 0.42, "DET": 0.38, "COL": 0.35, "MIA": 0.32,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


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
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    catcher_framing = _load(os.path.join(DATA_DIR, "mlb_catcher_framing.json"))

    # Build opposing catcher arm adjustment by team
    opp_catcher_adj = {}
    for adj in (catcher_framing.get("adjustments") or []):
        team = (adj.get("team") or "").upper()
        # Use catcher framing pop time as proxy -- we don't have pop_time directly
        # but catcher RPCP correlates with overall defensive quality
        tier = adj.get("tier", "average")
        if tier == "elite": opp_catcher_adj[team] = 0.80   # elite arm shuts down SB
        elif tier == "above_avg": opp_catcher_adj[team] = 0.90
        elif tier == "below_avg": opp_catcher_adj[team] = 1.10
        elif tier == "poor": opp_catcher_adj[team] = 1.20
        else: opp_catcher_adj[team] = 1.0

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]

        for team, opp in ((home, away), (away, home)):
            base_sb = TEAM_SB_PER_GAME.get(team, 0.55)
            opp_mult = opp_catcher_adj.get(opp, 1.0)
            expected_sb = base_sb * opp_mult

            # Edge classification: line 0.5/1.5/2.5
            edge_class = "NONE"
            best_market = None
            # OVER 1.5 (2+) -- requires high-running team in good matchup
            p_over_1_5 = _poisson_at_least(2, expected_sb)
            p_over_0_5 = _poisson_at_least(1, expected_sb)
            p_over_2_5 = _poisson_at_least(3, expected_sb)
            p_under_1_5 = 1 - p_over_1_5
            p_under_0_5 = 1 - p_over_0_5

            # STRONG when material edge over typical book pricing
            if 0.62 <= p_over_1_5 <= 0.72:
                edge_class = "STRONG_OVER_1_5"
                best_market = {"market": "TEAM_SB_OVER_1.5", "p": round(p_over_1_5, 3),
                               "fair_odds": _american(p_over_1_5)}
            elif p_over_1_5 >= 0.78:  # high-running matchup
                edge_class = "STRONG_OVER_1_5_HEAVY"
                best_market = {"market": "TEAM_SB_OVER_1.5", "p": round(p_over_1_5, 3),
                               "fair_odds": _american(p_over_1_5)}
            elif 0.65 <= p_under_0_5 <= 0.75:  # low-running team
                edge_class = "STRONG_NO_SB"
                best_market = {"market": "TEAM_SB_UNDER_0.5", "p": round(p_under_0_5, 3),
                               "fair_odds": _american(p_under_0_5)}

            rows.append({
                "matchup": matchup_str,
                "team": team,
                "opp_team": opp,
                "season_sb_per_game": base_sb,
                "opp_catcher_mult": round(opp_mult, 3),
                "expected_sb": round(expected_sb, 2),
                "p_over_0_5": round(p_over_0_5, 3),
                "p_over_1_5": round(p_over_1_5, 3),
                "p_over_2_5": round(p_over_2_5, 3),
                "fair_over_0_5": _american(p_over_0_5),
                "fair_over_1_5": _american(p_over_1_5),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["expected_sb"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_lines": len(rows),
        "n_strong": len(strong),
        "method_note": "Team SB/game baseline × opp_catcher_arm_factor. Poisson. "
                       "STRONG OVER 1.5 in [0.62, 0.72] range OR >= 0.78 (heavy). "
                       "STRONG NO_SB when low-running team facing elite catcher.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[team-sb] {o['n_team_lines']} team-lines, {o['n_strong']} strong -> {OUT}")
