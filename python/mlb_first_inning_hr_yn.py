"""
EdgeStat -- MLB first inning HR yes/no prop projections.

Common DK line: First inning HR scored (yes/no, typically +1200 to +1800 YES,
                                                       -2000 to -1500 NO).

Method:
  P(HR in 1st inning) = 1 - product over both teams of P(no HR in their half)

  For each team's half-inning:
    expected_HRs_half = HR_per_PA * expected_PA_in_half (~ 4.5 PA)
    P(no HR) = exp(-expected_HRs_half)

Adjusters:
  - Park HR factor
  - Combined lineup HR/PA (heavy power lineups: NYY, LAD, ATL boost)
  - Opp starter HR/9 allowed

Output: data/mlb_first_inning_hr_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_first_inning_hr_yn.json")

LEAGUE_HR_PER_PA = 0.030  # ~3% PA result in HR
LEAGUE_HR_PER_9 = 1.2


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
        park_hr_factor = _safe((park_info or {}).get("hr_factor"), 1.0) or 1.0

        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")
        home_sp = p_by_name.get((home_name or "").lower()) or (hp_raw if isinstance(hp_raw, dict) else None)
        away_sp = p_by_name.get((away_name or "").lower()) or (ap_raw if isinstance(ap_raw, dict) else None)
        if not home_sp or not away_sp: continue

        home_hr_per_9 = _safe(home_sp.get("hr_per_9") or home_sp.get("season", {}).get("hr_per_9"), LEAGUE_HR_PER_9)
        away_hr_per_9 = _safe(away_sp.get("hr_per_9") or away_sp.get("season", {}).get("hr_per_9"), LEAGUE_HR_PER_9)

        # Per-PA HR rate for each pitcher (HR/9 / 38.5 PA/9)
        home_pitcher_hr_per_pa = home_hr_per_9 / 38.5
        away_pitcher_hr_per_pa = away_hr_per_9 / 38.5

        # Average with league baseline (and lineup quality proxy from team OPS)
        home_lineup_ops = _safe((g.get("home") or {}).get("ops"), 0.72)
        away_lineup_ops = _safe((g.get("away") or {}).get("ops"), 0.72)
        # Power lineup adjustment: each .020 OPS above .720 = +5% HR rate
        home_lineup_mult = 1.0 + (home_lineup_ops - 0.72) / 0.020 * 0.05
        away_lineup_mult = 1.0 + (away_lineup_ops - 0.72) / 0.020 * 0.05
        home_lineup_mult = max(0.75, min(1.30, home_lineup_mult))
        away_lineup_mult = max(0.75, min(1.30, away_lineup_mult))

        # Each half-inning ~4.5 PA. P(HR for batting team in their half) =
        # 1 - exp(- (their HR rate × opposing pitcher HR rate) × 4.5)
        # We use the BATTING team's lineup HR rate × OPPOSING pitcher's HR allowed rate
        # to avoid double-counting -- use AVG of the two as effective rate.
        away_half_hr_rate = ((LEAGUE_HR_PER_PA * away_lineup_mult) + away_pitcher_hr_per_pa) / 2 * park_hr_factor
        home_half_hr_rate = ((LEAGUE_HR_PER_PA * home_lineup_mult) + home_pitcher_hr_per_pa) / 2 * park_hr_factor

        # AWAY bats top of 1st vs HOME pitcher. Each half = ~3.5 PA (3 outs).
        # Per-PA HR rate is the GEOMETRIC product of lineup propensity * pitcher allow
        # rate normalized by league average. This avoids the addition-doubling bug.
        # Effective HR/PA = league × lineup_mult × (pitcher_HR_per_9 / league_HR_per_9) × park
        away_half_hr_per_pa = (LEAGUE_HR_PER_PA * away_lineup_mult *
                               (home_hr_per_9 / LEAGUE_HR_PER_9) * park_hr_factor)
        home_half_hr_per_pa = (LEAGUE_HR_PER_PA * home_lineup_mult *
                               (away_hr_per_9 / LEAGUE_HR_PER_9) * park_hr_factor)

        # P(HR in first inning) = 1 - P(no HR away) × P(no HR home), each half ≈ 3.5 PA
        expected_hr_away_half = away_half_hr_per_pa * 3.5
        expected_hr_home_half = home_half_hr_per_pa * 3.5
        p_no_hr = math.exp(-expected_hr_away_half) * math.exp(-expected_hr_home_half)
        p_hr_yes = 1 - p_no_hr

        # Edge: book YES typically +1500 (6.25%% breakeven). Real rate ~7-9%%.
        # STRONG_YES needs material outlier (high HR pitchers + power lineups + Coors).
        # STRONG_NO needs unusual low (low HR pitchers + weak lineups + pitcher park).
        edge_class = "NONE"
        best_market = None
        # Tightened: STRONG_YES needs material outlier above natural ~19%% baseline.
        # Look for game-specific advantage (Coors + HR-prone pitcher + power lineup).
        if p_hr_yes >= 0.27:  # 27%%+ = unusual outlier (Coors + slumping HR pitcher)
            edge_class = "STRONG_YES"
            best_market = {"market": "FIRST_INNING_HR_YES", "p": round(p_hr_yes, 4),
                           "fair_odds": _american(p_hr_yes)}
        elif p_hr_yes <= 0.10:  # very low HR matchup -- pitcher park + low-HR pitchers
            edge_class = "STRONG_NO"
            best_market = {"market": "FIRST_INNING_HR_NO", "p": round(p_no_hr, 4),
                           "fair_odds": _american(p_no_hr)}

        rows.append({
            "matchup": matchup_str,
            "home_sp": home_name,
            "away_sp": away_name,
            "park_hr_factor": park_hr_factor,
            "home_lineup_ops": home_lineup_ops,
            "away_lineup_ops": away_lineup_ops,
            "home_pitcher_hr_per_9": home_hr_per_9,
            "away_pitcher_hr_per_9": away_hr_per_9,
            "expected_hr_first_inning": round(expected_hr_away_half + expected_hr_home_half, 4),
            "p_hr_yes": round(p_hr_yes, 4),
            "p_hr_no": round(p_no_hr, 4),
            "fair_odds_yes": _american(p_hr_yes),
            "fair_odds_no": _american(p_no_hr),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_hr_yes"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(HR in 1st) = 1 - exp(-away_half_HR_rate × 4.5) × exp(-home_half_HR_rate × 4.5). "
                       "Each half rate = (lineup_HR + opp_pitcher_HR_allowed) / 2 × park_HR_factor. "
                       "STRONG_YES p>=10%% (book ~+1500), STRONG_NO p<=5%% (book ~-2000).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[first-inn-hr] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
