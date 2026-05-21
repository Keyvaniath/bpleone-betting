"""
EdgeStat -- MLB innings 4-6 total prop projections.

The bullpen-transition window. Starters typically exit somewhere in inning
5-7, so innings 4-6 are a mix of (a) tiring starter facing batters 3rd time
through, (b) middle-relief bullpen. Higher run expectancy than 1-3.

Common lines: 2.5, 3.5, 4.5

Method:
  Innings 4-6 expected runs = combined_runs_per_game × 0.36 (~ 6 of 18 outs
  weighted by 3rd-time-through penalty + middle relief OBP).

Adjusters:
  - Bullpen quality (from mlb_bullpen_freshness.json if available)
  - Park factor
  - Starter expected_IP (if SP goes long into 6, more pure-quality outs; if
    short, more bullpen runs)

Output: data/mlb_innings_4_6_totals.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_innings_4_6_totals.json")

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
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_freshness.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    parks = today.get("parks") or {}

    # Bullpen fatigue index (team -> 0=fresh, 1=fatigued)
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

        # Each pitcher's expected runs in IP 4-6 = era/9 * 3 IP * 3rd_time_through_penalty
        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")
        home_sp = p_by_name.get((home_name or "").lower()) or (hp_raw if isinstance(hp_raw, dict) else None)
        away_sp = p_by_name.get((away_name or "").lower()) or (ap_raw if isinstance(ap_raw, dict) else None)
        if not home_sp or not away_sp: continue

        home_era = _safe(home_sp.get("era") or home_sp.get("season", {}).get("era"), 4.20)
        away_era = _safe(away_sp.get("era") or away_sp.get("season", {}).get("era"), 4.20)
        home_avg_ip = _safe(home_sp.get("avg_ip"), 5.3)
        away_avg_ip = _safe(away_sp.get("avg_ip"), 5.3)

        # Innings 4-6 each pitcher's expected runs allowed
        # Assume each pitches up to inning 6 = ~min(3, avg_ip - 3) innings of 4-6 covered
        home_sp_ip_in_4_6 = max(0, min(3, home_avg_ip - 3))
        away_sp_ip_in_4_6 = max(0, min(3, away_avg_ip - 3))
        bullpen_ip_home = 3 - home_sp_ip_in_4_6  # bullpen covers rest
        bullpen_ip_away = 3 - away_sp_ip_in_4_6

        # 3rd time through penalty: +15%% runs vs starter when in 4-6
        tto_mult = 1.15

        # Bullpen runs per IP ~ 4.0 ERA league avg + fatigue boost
        home_bp_fatigue = bullpen_fatigue.get(home, 0.5)
        away_bp_fatigue = bullpen_fatigue.get(away, 0.5)
        bp_era_home = 4.0 * (1 + home_bp_fatigue * 0.20)
        bp_era_away = 4.0 * (1 + away_bp_fatigue * 0.20)

        # Combined expected runs in 4-6 (both teams)
        home_runs_4_6 = (home_era / 9 * home_sp_ip_in_4_6 * tto_mult +
                         bp_era_home / 9 * bullpen_ip_home)
        away_runs_4_6 = (away_era / 9 * away_sp_ip_in_4_6 * tto_mult +
                         bp_era_away / 9 * bullpen_ip_away)
        expected_total = home_runs_4_6 + away_runs_4_6

        # Park factor
        expected_total *= max(0.90, min(1.15, park_run_factor))
        expected_total = max(1.5, min(8.0, expected_total))

        p_over_2_5 = _poisson_at_least(3, expected_total)
        p_over_3_5 = _poisson_at_least(4, expected_total)
        p_over_4_5 = _poisson_at_least(5, expected_total)

        # Edge classification at nearest 0.5 line
        edge_class = "NONE"
        best_market = None
        nearest = round(expected_total - 0.5) + 0.5
        for line in (nearest, nearest + 0.5):
            if line not in (2.5, 3.5, 4.5): continue
            if abs(expected_total - line) > 0.75: continue
            p_over = _poisson_at_least(int(line) + 1, expected_total)
            p_under = 1 - p_over
            if 0.62 <= p_over <= 0.72:
                if not best_market or p_over > best_market["p"]:
                    edge_class = "STRONG_OVER"
                    best_market = {"market": f"INN_4_6_OVER_{line}", "p": round(p_over, 3),
                                   "fair_odds": _american(p_over), "line": line}
            elif 0.62 <= p_under <= 0.72:
                if not best_market or p_under > best_market["p"]:
                    edge_class = "STRONG_UNDER"
                    best_market = {"market": f"INN_4_6_UNDER_{line}", "p": round(p_under, 3),
                                   "fair_odds": _american(p_under), "line": line}

        rows.append({
            "matchup": matchup_str,
            "home_sp": home_name,
            "away_sp": away_name,
            "home_avg_ip": home_avg_ip,
            "home_bp_fatigue": round(home_bp_fatigue, 3),
            "away_bp_fatigue": round(away_bp_fatigue, 3),
            "home_sp_ip_in_4_6": round(home_sp_ip_in_4_6, 1),
            "away_sp_ip_in_4_6": round(away_sp_ip_in_4_6, 1),
            "expected_runs_4_6": round(expected_total, 2),
            "p_over_2_5": round(p_over_2_5, 3),
            "p_over_3_5": round(p_over_3_5, 3),
            "p_over_4_5": round(p_over_4_5, 3),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Innings 4-6 = SP_tto_runs + bullpen_runs (fatigue-adjusted) × park. "
                       "TTO penalty +15%% for SP. Poisson at 2.5/3.5/4.5 lines.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[inn-4-6] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
