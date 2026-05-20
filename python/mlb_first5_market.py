"""
EdgeStat -- MLB First-5-Innings (F5) market projections.

F5 ML + F5 total are the highest signal-to-noise MLB markets: bullpens are
excluded so the projection collapses onto just the two starting pitchers and
their first ~5 innings against the opposing lineup.

For each game:
  - Projects each starter's expected runs allowed in their first 5 IP
  - Builds Poisson convolution -> F5 team-total + F5 total + F5 ML
  - Fair odds vs typical book lines (-115 to -120 vig)
  - Edge classification (STRONG / STANDARD / NONE)

Method:
  Per-PA runs-allowed rate from pitcher logs, conditioned on:
    - Opposing lineup OBP
    - Park run factor
    - Pitcher form delta (recent 3 starts vs season)
    - Weather (wind / temp)
  Expected PA in first 5 = ~21 (5 IP / 3 outs per IP × 1.27 BFP per out)
  Then Poisson(lambda=runs_per_PA × 21) for distribution.

Source data:
  - data/matchups.json (lineups, pitchers, park, weather)
  - data/mlb_pitcher_logs.json (pitcher season stats)
  - data/mlb_pitcher_form_regression.json (form deltas)
  - data/today.json (park factors)

Output: data/mlb_first5_market.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_first5_market.json")

# Empirically-fit constants
PA_PER_FIRST5 = 21.0  # ~21 PA for SP in first 5 IP
LEAGUE_BABIP = 0.295
LEAGUE_R_PER_PA = 0.117  # 4.5 R/g / ~38.5 PA/g per team
F5_VIG = 0.04  # typical book hold % on F5


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


def _poisson_total_above(thresh: float, lam_h: float, lam_a: float, max_total=15) -> float:
    """P(home_runs + away_runs > thresh) when each side is Poisson."""
    # Convolve home + away
    p_over = 0.0
    for h in range(max_total):
        for a in range(max_total):
            if h + a > thresh:
                p_over += _poisson_pmf(h, lam_h) * _poisson_pmf(a, lam_a)
    return p_over


def _poisson_team_a_beats_b(lam_a: float, lam_b: float, max_total=15) -> float:
    """P(team A scores more than team B) when each Poisson."""
    p_a_wins = 0.0
    for a in range(max_total):
        for b in range(max_total):
            if a > b:
                p_a_wins += _poisson_pmf(a, lam_a) * _poisson_pmf(b, lam_b)
    return p_a_wins


def _american_from_p(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _expected_pitcher_lambda(pitcher: Dict[str, Any], opp_obp: float,
                              park_run_factor: float, form_delta: float,
                              weather_runs_adj: float) -> float:
    """Expected runs allowed by this pitcher in his first 5 IP."""
    if not pitcher: return 2.6  # league avg F5 RA
    era = _safe(pitcher.get("era") or pitcher.get("season", {}).get("era"), 4.20)
    # ERA / 9 * 5 = expected ER in 5 IP
    base = era / 9.0 * 5.0
    # Adjust by opposing OBP (league avg .317)
    obp_mult = max(0.75, min(1.30, opp_obp / 0.317))
    # Park run factor (1.0 = neutral)
    park_mult = max(0.85, min(1.20, park_run_factor))
    # Form delta: -1 to +1 -> 0.90x to 1.10x
    form_mult = 1.0 - max(-0.10, min(0.10, form_delta * 0.10))
    # Weather (+/- runs)
    weather_add = max(-0.5, min(0.5, weather_runs_adj))
    return max(0.5, base * obp_mult * park_mult * form_mult + weather_add)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_regression.json"))

    # Index
    pitchers_by_name: Dict[str, Dict[str, Any]] = {}
    for p in (pitcher_logs.get("pitchers") or []):
        nm = (p.get("name") or "").lower()
        if nm: pitchers_by_name[nm] = p
    form_by_name: Dict[str, float] = {}
    for row in (form.get("rows") or form.get("pitchers") or []):
        nm = (row.get("name") or row.get("pitcher") or "").lower()
        d = _safe(row.get("delta") or row.get("form_delta") or row.get("z_score"), 0.0)
        if nm: form_by_name[nm] = d

    parks = today.get("parks") or {}
    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away_team, home_team = [s.strip().upper() for s in matchup_str.split("@", 1)]

        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        # Weather adjustment: warm wind out = +0.2 runs, cold wind in = -0.2
        weather = g.get("weather") or {}
        weather_runs_adj = 0.0
        wind_dir = (weather.get("wind_direction") or "").lower()
        wind_mph = _safe(weather.get("wind_mph"), 0)
        temp = _safe(weather.get("temp_f") or weather.get("temperature_f"), 70)
        if "out" in wind_dir and wind_mph >= 10: weather_runs_adj += 0.15
        if "in" in wind_dir and wind_mph >= 10: weather_runs_adj -= 0.15
        if temp >= 85: weather_runs_adj += 0.10
        if temp <= 50: weather_runs_adj -= 0.10

        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")
        home_sp = pitchers_by_name.get((home_name or "").lower())
        away_sp = pitchers_by_name.get((away_name or "").lower())
        if not home_sp and isinstance(hp_raw, dict): home_sp = hp_raw
        if not away_sp and isinstance(ap_raw, dict): away_sp = ap_raw
        if not home_sp or not away_sp: continue

        # Opposing OBP (from team stats in matchups.json)
        home_obp = _safe((g.get("home") or {}).get("obp"), 0.317) or 0.317
        away_obp = _safe((g.get("away") or {}).get("obp"), 0.317) or 0.317

        home_form = form_by_name.get((home_name or "").lower(), 0.0)
        away_form = form_by_name.get((away_name or "").lower(), 0.0)

        # Home SP faces away lineup
        lam_home_ra = _expected_pitcher_lambda(home_sp, away_obp, park_run_factor, home_form, weather_runs_adj)
        lam_away_ra = _expected_pitcher_lambda(away_sp, home_obp, park_run_factor, away_form, weather_runs_adj)

        # Convert to TEAM lambdas (away_team_scores = lam_home_ra; home_team_scores = lam_away_ra)
        lam_away_scores = lam_home_ra
        lam_home_scores = lam_away_ra
        total_lambda = lam_away_scores + lam_home_scores

        # F5 markets
        # Total: typical book line is 4.0 or 4.5; we compute both
        p_over_4 = _poisson_total_above(4.0, lam_home_scores, lam_away_scores)
        p_over_4_5 = _poisson_total_above(4.5, lam_home_scores, lam_away_scores)

        # ML
        p_home_wins = _poisson_team_a_beats_b(lam_home_scores, lam_away_scores)
        p_away_wins = _poisson_team_a_beats_b(lam_away_scores, lam_home_scores)
        p_draw = 1 - p_home_wins - p_away_wins  # tie -> push on F5 ML

        # Edge tagging (vs typical -120 = 54.5% breakeven)
        edge_class = "NONE"
        edge_market = None
        edge_value = 0
        for market, p, label in [
            ("F5_total_over_4", p_over_4, "OVER 4.0"),
            ("F5_total_under_4", 1 - p_over_4, "UNDER 4.0"),
            ("F5_total_over_4_5", p_over_4_5, "OVER 4.5"),
            ("F5_total_under_4_5", 1 - p_over_4_5, "UNDER 4.5"),
            ("F5_home_ml", p_home_wins, f"{home_team} F5 ML"),
            ("F5_away_ml", p_away_wins, f"{away_team} F5 ML"),
        ]:
            if p >= 0.62:
                if p > edge_value:
                    edge_value = p
                    edge_class = "STRONG"
                    edge_market = {"market": market, "pick": label, "model_p": round(p, 3),
                                    "fair_odds": _american_from_p(p)}
            elif p >= 0.56 and edge_class != "STRONG":
                if p > edge_value:
                    edge_value = p
                    edge_class = "STANDARD"
                    edge_market = {"market": market, "pick": label, "model_p": round(p, 3),
                                    "fair_odds": _american_from_p(p)}

        rows.append({
            "matchup": matchup_str,
            "home_team": home_team,
            "away_team": away_team,
            "home_pitcher": home_name,
            "away_pitcher": away_name,
            "park": park,
            "park_run_factor": park_run_factor,
            "weather_adj_runs": round(weather_runs_adj, 2),
            "home_sp_expected_ra_5ip": round(lam_home_ra, 2),
            "away_sp_expected_ra_5ip": round(lam_away_ra, 2),
            "f5_total_lambda": round(total_lambda, 2),
            "p_over_4_0": round(p_over_4, 3),
            "p_under_4_0": round(1 - p_over_4, 3),
            "p_over_4_5": round(p_over_4_5, 3),
            "p_under_4_5": round(1 - p_over_4_5, 3),
            "p_home_ml": round(p_home_wins, 3),
            "p_away_ml": round(p_away_wins, 3),
            "p_draw_push": round(p_draw, 3),
            "edge_class": edge_class,
            "best_edge": edge_market,
        })

    rows.sort(key=lambda r: (-{"STRONG":2,"STANDARD":1,"NONE":0}[r["edge_class"]],
                              -r["f5_total_lambda"]))
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Per-pitcher per-PA RA model -> Poisson convolution for F5 ML + Total. "
                       "Sharps prefer F5 because bullpens are excluded.",
        "games": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f5-market] {o['n_games']} games, {o['n_strong_edges']} strong edges -> {OUT}")
