"""
EdgeStat -- MLB innings 7-9 total prop projections.

The closer/setup-man market. Three full innings handled almost entirely by
bullpen. Distinct edge market because:
  - Closer + 8th-inning + setup ERA usually MUCH better than starter ERA
  - But goalies pulled / desperate teams = more late runs
  - Garbage-time blowouts mean weaker relievers in the 9th

Common lines: 1.5, 2.5, 3.5

Method:
  expected_runs_7_9 ≈ bullpen_era / 9 × 6 IP (both teams × 3 IP) × adjusters
  Bullpen ERA cleaner than full-team ERA for late-inning relievers (~3.6 avg).

Output: data/mlb_innings_7_9_totals.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_innings_7_9_totals.json")

LEAGUE_LATE_RELIEF_ERA = 3.6  # closer/setup ERA league average ~3.6


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


# 2024-25 per-team late-inning bullpen ERA (closer + setup, last-25 outings avg)
TEAM_LATE_BP_ERA = {
    "ATL": 3.20, "BAL": 3.50, "BOS": 3.85, "CHC": 3.40, "CHW": 4.80,
    "CIN": 3.85, "CLE": 3.10, "COL": 4.95, "DET": 3.50, "HOU": 3.20,
    "KCR": 3.40, "LAA": 4.20, "LAD": 3.05, "MIA": 3.95, "MIL": 3.30,
    "MIN": 3.50, "NYM": 3.40, "NYY": 3.20, "OAK": 4.50, "PHI": 3.45,
    "PIT": 3.80, "SDP": 3.10, "SEA": 3.35, "SFG": 3.40, "STL": 3.65,
    "TBR": 3.40, "TEX": 3.65, "TOR": 3.50, "WSN": 4.10, "ARI": 3.70,
}


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_freshness.json"))

    parks = today.get("parks") or {}
    bullpen_fatigue = {}
    for row in (bullpen.get("rows") or bullpen.get("teams") or []):
        t = (row.get("team") or "").upper()
        bullpen_fatigue[t] = _safe(row.get("fatigue_index") or row.get("usage_pct"), 0.5)

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        home_bp_era = TEAM_LATE_BP_ERA.get(home, LEAGUE_LATE_RELIEF_ERA)
        away_bp_era = TEAM_LATE_BP_ERA.get(away, LEAGUE_LATE_RELIEF_ERA)
        home_fatigue = bullpen_fatigue.get(home, 0.5)
        away_fatigue = bullpen_fatigue.get(away, 0.5)

        # Each team's expected runs allowed in 7-9 = bp_era / 9 × 3 IP × fatigue mult
        home_runs_allowed = home_bp_era / 9 * 3 * (1 + home_fatigue * 0.20)
        away_runs_allowed = away_bp_era / 9 * 3 * (1 + away_fatigue * 0.20)
        expected_total = (home_runs_allowed + away_runs_allowed) * max(0.90, min(1.15, park_run_factor))
        expected_total = max(1.0, min(7.0, expected_total))

        p_over_1_5 = _poisson_at_least(2, expected_total)
        p_over_2_5 = _poisson_at_least(3, expected_total)
        p_over_3_5 = _poisson_at_least(4, expected_total)

        edge_class = "NONE"
        best_market = None
        nearest = round(expected_total - 0.5) + 0.5
        for line in (nearest, nearest + 0.5):
            if line not in (1.5, 2.5, 3.5): continue
            if abs(expected_total - line) > 0.75: continue
            p_over = _poisson_at_least(int(line) + 1, expected_total)
            p_under = 1 - p_over
            if 0.62 <= p_over <= 0.72:
                if not best_market or p_over > best_market["p"]:
                    edge_class = "STRONG_OVER"
                    best_market = {"market": f"INN_7_9_OVER_{line}", "p": round(p_over, 3),
                                   "fair_odds": _american(p_over), "line": line}
            elif 0.62 <= p_under <= 0.72:
                if not best_market or p_under > best_market["p"]:
                    edge_class = "STRONG_UNDER"
                    best_market = {"market": f"INN_7_9_UNDER_{line}", "p": round(p_under, 3),
                                   "fair_odds": _american(p_under), "line": line}

        rows.append({
            "matchup": matchup_str,
            "home_late_bp_era": home_bp_era,
            "away_late_bp_era": away_bp_era,
            "home_fatigue": round(home_fatigue, 3),
            "away_fatigue": round(away_fatigue, 3),
            "park_run_factor": park_run_factor,
            "expected_runs_7_9": round(expected_total, 2),
            "p_over_1_5": round(p_over_1_5, 3),
            "p_over_2_5": round(p_over_2_5, 3),
            "p_over_3_5": round(p_over_3_5, 3),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Innings 7-9 = late_bp_era/9 × 3 IP × fatigue × park (both teams). "
                       "Late-inning bullpen ERA much lower than overall (3.6 avg vs ~4.2). "
                       "Closer windows means lower variance, sharper book pricing.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[inn-7-9] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
