"""
EdgeStat -- Soccer Both Teams To Score (BTTS) prop projections.

BTTS is one of the most-bet European soccer markets. Common prices:
  - BTTS Yes: -130 to +130 (close to coin flip in EPL)
  - BTTS No: similar range

Approach:
  For each match, project home_goals and away_goals expected via Poisson.
  P(BTTS Yes) = P(home >= 1) * P(away >= 1)
              = (1 - exp(-lam_home)) * (1 - exp(-lam_away))

Per-team expected goals scaled by:
  - League baseline (EPL ~1.4/team, MLS ~1.3, UCL ~1.5, La Liga ~1.3)
  - ELO-derived attacking strength differential
  - Home advantage (~0.30 goals home boost)

Output: data/soccer_btts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_btts_props.json")

# League per-team goals-per-game baselines (2024 season)
LEAGUE_BASELINES = {
    "epl": 1.42, "mls": 1.35, "ucl": 1.55, "la_liga": 1.32, "serie_a": 1.36,
}
HOME_ADVANTAGE = 0.30  # goals/game boost for home team


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
    base_per_team = LEAGUE_BASELINES.get(league, 1.4)

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        # Higher-ELO attack creates more goals; ELO differential affects which side scores
        # Translate ELO diff into goal expectancy
        elo_diff = (home_elo - away_elo) / 400.0  # rescaled
        # Stronger team scores ~0.3 more goals/game per 400-ELO advantage
        home_attack = base_per_team + HOME_ADVANTAGE + 0.15 * elo_diff
        away_attack = base_per_team - 0.15 * elo_diff
        home_attack = max(0.4, min(3.5, home_attack))
        away_attack = max(0.4, min(3.5, away_attack))

        # P(team scores >= 1) = 1 - exp(-lambda)
        p_home_scores = 1 - math.exp(-home_attack)
        p_away_scores = 1 - math.exp(-away_attack)
        # BTTS Yes assumes independence
        p_btts_yes = p_home_scores * p_away_scores
        p_btts_no = 1 - p_btts_yes

        # Edge classification: STRONG = 10%+ edge vs typical -130 book (56.5% breakeven)
        edge_class = "NONE"
        best_market = None
        # Differentiation gate: require ELO diff to be meaningful
        elo_meaningful = abs(elo_diff) >= 0.15 or league in ("ucl", "epl")  # high-variance leagues
        if elo_meaningful:
            if 0.62 <= p_btts_yes <= 0.74:
                edge_class = "STRONG_BTTS_YES"
                best_market = {"market": "BTTS_YES", "p": round(p_btts_yes, 3),
                               "fair_odds": _american(p_btts_yes)}
            elif 0.62 <= p_btts_no <= 0.74:
                edge_class = "STRONG_BTTS_NO"
                best_market = {"market": "BTTS_NO", "p": round(p_btts_no, 3),
                               "fair_odds": _american(p_btts_no)}

        rows.append({
            "league": league.upper(),
            "matchup": f"{away} @ {home}",
            "game_date": (g.get("date") or "")[:10],  # date the pick to kickoff -> dedup + clean settle
            "home_team": home,
            "away_team": away,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "league_baseline_per_team": base_per_team,
            "home_attack_lambda": round(home_attack, 3),
            "away_attack_lambda": round(away_attack, 3),
            "p_home_scores": round(p_home_scores, 3),
            "p_away_scores": round(p_away_scores, 3),
            "p_btts_yes": round(p_btts_yes, 3),
            "p_btts_no": round(p_btts_no, 3),
            "fair_odds_yes": _american(p_btts_yes),
            "fair_odds_no": _american(p_btts_no),
            "edge_class": edge_class,
            "best_market": best_market,
        })
    return rows


def run() -> Dict[str, Any]:
    all_rows = []
    for state_file, league in [
        ("mls_state.json", "mls"),
        ("epl_state.json", "epl"),
        ("ucl_state.json", "ucl"),
        ("worldcup_state.json", "worldcup"),
    ]:
        rows = _process_league(state_file, league)
        all_rows.extend(rows)

    all_rows.sort(key=lambda r: -r["p_btts_yes"])
    strong = [r for r in all_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(all_rows),
        "n_strong": len(strong),
        "league_baselines_per_team": LEAGUE_BASELINES,
        "method_note": "P(BTTS Yes) = P(home scores) × P(away scores) under Poisson "
                       "independence. Home advantage = +0.30 goals; 400-ELO diff = "
                       "+0.15 goal swing. STRONG only when ELO differential is meaningful "
                       "OR in high-variance leagues (UCL/EPL).",
        "matches": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[btts] {o['n_matches']} matches, {o['n_strong']} strong -> {OUT}")
