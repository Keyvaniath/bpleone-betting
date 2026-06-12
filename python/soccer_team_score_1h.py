"""
EdgeStat -- Soccer team to score in 1st half yes/no prop.

DK soccer alt. Typical pricing:
  - Home favorite vs weak away: +120 to +180 YES
  - Avg matchup: +180 to +260 YES
  - Heavy underdog: +400+

Method:
  P(team scores in 1H) = 1 - exp(-lam_team_1H)
  where lam_team_1H = lam_team_total * 0.42 (first half tends to be
  slightly less productive than 2H — 42% of goals).

  STRONG_YES at p in [0.40, 0.58] (vs +130 book = 43.5% breakeven)
  STRONG_NO at p_no in [0.60, 0.74] vs -180 NO book

Output: data/soccer_team_score_1h.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_team_score_1h.json")

LEAGUE_BASELINES = {
    "epl": 1.42, "mls": 1.35, "ucl": 1.55, "la_liga": 1.32, "serie_a": 1.36,
    "bundesliga": 1.50, "ligue_1": 1.30,
}
HOME_ADVANTAGE = 0.30
FIRST_HALF_SHARE = 0.42  # 1H tends to be 42% of total goals


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
    base = LEAGUE_BASELINES.get(league, 1.4)

    rows = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        elo_diff = (home_elo - away_elo) / 400.0
        lam_home_full = max(0.4, min(3.5, base + HOME_ADVANTAGE + 0.15 * elo_diff))
        lam_away_full = max(0.4, min(3.5, base - 0.15 * elo_diff))

        for side, lam_full, team in (("home", lam_home_full, home),
                                     ("away", lam_away_full, away)):
            lam_1h = lam_full * FIRST_HALF_SHARE
            p_score = 1 - math.exp(-lam_1h)
            p_no = 1 - p_score

            edge_class = "NONE"
            best_market = None
            # Tightened: league cluster ~0.48, so STRONG zones require true deviation
            if 0.54 <= p_score <= 0.62:
                edge_class = "STRONG_YES"
                best_market = {"market": f"{side.upper()}_SCORE_1H_YES",
                               "p": round(p_score, 3),
                               "fair_odds": _american(p_score)}
            elif 0.66 <= p_no <= 0.78:
                edge_class = "STRONG_NO"
                best_market = {"market": f"{side.upper()}_SCORE_1H_NO",
                               "p": round(p_no, 3),
                               "fair_odds": _american(p_no)}

            rows.append({
                "league": league.upper(),
                "matchup": f"{away} @ {home}",
                "side": side.upper(),
                "team": team,
                "lam_team_full_match": round(lam_full, 3),
                "lam_team_1h": round(lam_1h, 3),
                "p_score_1h": round(p_score, 3),
                "p_no_score_1h": round(p_no, 3),
                "fair_yes": _american(p_score),
                "fair_no": _american(p_no),
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
        "n_team_sides": len(all_rows),
        "n_strong_edges": len(strong),
        "method_note": "P(team scores in 1H) = 1 - exp(-lam_team_1H) where "
                       "lam_1H = lam_full_match * 0.42 (1H goal share). "
                       "STRONG_YES p in [0.40, 0.58] vs +130 book; STRONG_NO "
                       "p_no in [0.60, 0.74] vs -180 NO.",
        "rows": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soc-1h] {o['n_team_sides']} team-sides, {o['n_strong_edges']} strong -> {OUT}")
