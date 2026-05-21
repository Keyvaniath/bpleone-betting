"""
EdgeStat -- MLB innings 1-3 total prop projections.

Different from F5 (innings 1-5). The 1-3 market is a "no-bullpen, pure-starter"
read — typically the cleanest 3-inning sample of pitcher pure quality.

Common lines: 1.5, 2.5, 3.5

Method:
  expected_runs_1_3 = (combined_ERA / 9) × 6  (both pitchers, 3 IP each)
  Poisson approximation.

Adjusters:
  - Park run factor
  - Combined opp_OBP

Output: data/mlb_innings_1_3_totals.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_innings_1_3_totals.json")

LEAGUE_OBP = 0.317


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
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    parks = today.get("parks") or {}
    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]

        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        home_obp = _safe((g.get("home") or {}).get("obp"), LEAGUE_OBP)
        away_obp = _safe((g.get("away") or {}).get("obp"), LEAGUE_OBP)

        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")
        home_sp = p_by_name.get((home_name or "").lower()) or (hp_raw if isinstance(hp_raw, dict) else None)
        away_sp = p_by_name.get((away_name or "").lower()) or (ap_raw if isinstance(ap_raw, dict) else None)
        if not home_sp or not away_sp: continue

        home_era = _safe(home_sp.get("era") or home_sp.get("season", {}).get("era"), 4.20)
        away_era = _safe(away_sp.get("era") or away_sp.get("season", {}).get("era"), 4.20)
        combined_era = (home_era + away_era) / 2

        # Both pitchers in first 3 IP = 6 total IP
        base_runs_1_3 = combined_era / 9.0 * 6.0
        # Opp OBP adjustment
        home_obp_mult = max(0.85, min(1.20, away_obp / LEAGUE_OBP))  # home pitcher faces away batters
        away_obp_mult = max(0.85, min(1.20, home_obp / LEAGUE_OBP))
        avg_obp_mult = (home_obp_mult + away_obp_mult) / 2
        # Park factor
        park_mult = max(0.90, min(1.15, park_run_factor))

        expected_runs = base_runs_1_3 * avg_obp_mult * park_mult
        expected_runs = max(0.8, min(8.0, expected_runs))

        p_over_1_5 = _poisson_at_least(2, expected_runs)
        p_over_2_5 = _poisson_at_least(3, expected_runs)
        p_over_3_5 = _poisson_at_least(4, expected_runs)
        p_under_2_5 = 1 - p_over_2_5

        # Edge classification at nearest 0.5 line
        edge_class = "NONE"
        best_market = None
        nearest = round(expected_runs - 0.5) + 0.5
        for line in (nearest, nearest + 0.5):
            if line not in (1.5, 2.5, 3.5): continue
            if abs(expected_runs - line) > 0.75: continue
            p_over = _poisson_at_least(int(line) + 1, expected_runs)
            p_under = 1 - p_over
            if 0.62 <= p_over <= 0.72:
                if not best_market or p_over > best_market["p"]:
                    edge_class = f"STRONG_OVER_{line}"
                    best_market = {"market": f"INN_1_3_OVER_{line}", "p": round(p_over, 3),
                                   "fair_odds": _american(p_over), "line": line}
            elif 0.62 <= p_under <= 0.72:
                if not best_market or p_under > best_market["p"]:
                    edge_class = f"STRONG_UNDER_{line}"
                    best_market = {"market": f"INN_1_3_UNDER_{line}", "p": round(p_under, 3),
                                   "fair_odds": _american(p_under), "line": line}

        rows.append({
            "matchup": matchup_str,
            "home_pitcher": home_name,
            "away_pitcher": away_name,
            "home_era": home_era,
            "away_era": away_era,
            "combined_era": round(combined_era, 2),
            "park_run_factor": park_run_factor,
            "avg_opp_obp": round((home_obp + away_obp) / 2, 3),
            "expected_runs_1_3": round(expected_runs, 2),
            "p_over_1_5": round(p_over_1_5, 3),
            "p_over_2_5": round(p_over_2_5, 3),
            "p_over_3_5": round(p_over_3_5, 3),
            "p_under_2_5": round(p_under_2_5, 3),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Innings 1-3 total = combined_ERA/9 × 6 IP × opp_OBP × park. "
                       "Poisson at nearest 0.5 line. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[inn-1-3] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
