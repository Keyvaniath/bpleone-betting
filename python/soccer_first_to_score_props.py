"""
EdgeStat -- Soccer "first team to score" prop projections.

DK market: which team scores first goal. Also offers "no goal scored" outcome.

Typical book pricing:
  - Strong home favorite (e.g. Man City home): -150 to score first
  - Even matchups: +110 / +130 / +600 (home / away / no goal)
  - Strong away favorite: +110 / -110 / +700

Method:
  Per-team expected_goals lambda (from BTTS module pattern, ELO-adjusted).
  P(team scores first | someone scores) = lam_team / lam_total
  P(no goal) = exp(-lam_total) (rare in EPL/La Liga ~5-8%; higher in MLS/lower leagues)

  Conditional:
    p_home_first = (1 - p_no_goal) * lam_home / lam_total
    p_away_first = (1 - p_no_goal) * lam_away / lam_total

  STRONG when p deviates 5%+ from typical book breakeven.

Output: data/soccer_first_to_score_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_first_to_score_props.json")

LEAGUE_BASELINES = {
    "epl": 1.42, "mls": 1.35, "ucl": 1.55, "la_liga": 1.32, "serie_a": 1.36,
    "bundesliga": 1.50, "ligue_1": 1.30,
}
HOME_ADVANTAGE = 0.30


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


def _process_league(state_file: str, league: str) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or state.get("events") or []
    rows = []
    base = LEAGUE_BASELINES.get(league, 1.4)

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        elo_diff = (home_elo - away_elo) / 400.0
        lam_home = max(0.4, min(3.5, base + HOME_ADVANTAGE + 0.15 * elo_diff))
        lam_away = max(0.4, min(3.5, base - 0.15 * elo_diff))
        lam_total = lam_home + lam_away

        p_no_goal = math.exp(-lam_total)
        p_some_goal = 1 - p_no_goal

        # Conditional first-scorer probs
        share_home = lam_home / lam_total if lam_total > 0 else 0.5
        share_away = lam_away / lam_total if lam_total > 0 else 0.5
        p_home_first = p_some_goal * share_home
        p_away_first = p_some_goal * share_away

        edge_class = "NONE"
        best_market = None
        # STRONG_HOME when p_home_first >= 55% (favorite at -110 book = 52.4%)
        if p_home_first >= 0.55 and p_home_first <= 0.70:
            edge_class = "STRONG_HOME_FIRST"
            best_market = {"market": "HOME_FIRST_GOAL",
                           "p": round(p_home_first, 3),
                           "fair_odds": _american(p_home_first)}
        elif p_away_first >= 0.50 and p_away_first <= 0.65:
            edge_class = "STRONG_AWAY_FIRST"
            best_market = {"market": "AWAY_FIRST_GOAL",
                           "p": round(p_away_first, 3),
                           "fair_odds": _american(p_away_first)}
        # STRONG_NO_GOAL when p_no_goal >= 12% (vs +700 book = 12.5% breakeven)
        elif p_no_goal >= 0.13 and p_no_goal <= 0.20:
            edge_class = "STRONG_NO_GOAL"
            best_market = {"market": "NO_GOAL_SCORED",
                           "p": round(p_no_goal, 3),
                           "fair_odds": _american(p_no_goal)}

        rows.append({
            "league": league.upper(),
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "lam_home": round(lam_home, 3),
            "lam_away": round(lam_away, 3),
            "p_home_first": round(p_home_first, 3),
            "p_away_first": round(p_away_first, 3),
            "p_no_goal": round(p_no_goal, 3),
            "fair_yes_home": _american(p_home_first),
            "fair_yes_away": _american(p_away_first),
            "fair_yes_no_goal": _american(p_no_goal),
            "edge_class": edge_class,
            "best_market": best_market,
        })
    return rows


def run() -> Dict[str, Any]:
    all_rows = []
    for state_file, league in (
        ("epl_state.json", "epl"),
        ("mls_state.json", "mls"),
        ("ucl_state.json", "ucl"),
        ("worldcup_state.json", "worldcup"),
        ("la_liga_state.json", "la_liga"),
        ("serie_a_state.json", "serie_a"),
        ("bundesliga_state.json", "bundesliga"),
        ("ligue_1_state.json", "ligue_1"),
    ):
        all_rows.extend(_process_league(state_file, league))

    strong = [r for r in all_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(all_rows),
        "n_strong_edges": len(strong),
        "method_note": "P(first scorer) = (1-exp(-lam_total)) * lam_team/lam_total. "
                       "Per-team lambda = league_baseline +/- home_adv +/- ELO_diff. "
                       "STRONG_HOME_FIRST p in [0.55, 0.70] vs -110 book; "
                       "STRONG_NO_GOAL p in [0.13, 0.20] vs +700 book.",
        "rows": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soc-first] {o['n_matches']} matches, {o['n_strong_edges']} strong -> {OUT}")
