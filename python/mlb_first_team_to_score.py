"""
EdgeStat -- MLB which team scores first prop.

DK alt: 'First team to score' — popular pre-game prop, also key live betting
anchor.

Method:
  Per-team P(scores >= 1 in 1st inning) from mlb_team_first_inning_run.
  P(home scores first | someone scores) ≈ p_home_1st / (p_home_1st + p_away_1st)
  Then weight by p_someone_scores_first = home_or_away_in_1st_inning.

  STRONG_HOME at p_home_first >= 0.55 (vs -130 book = 56.5%)

Output: data/mlb_first_team_to_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_first_team_to_score.json")


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
    first_inn = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))

    # Aggregate per matchup
    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in (first_inn.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        side = r.get("side")
        p_score = _safe(r.get("p_score"))
        team = r.get("team")
        entry = by_matchup.setdefault(m, {"matchup": m})
        if side == "HOME":
            entry["home_team"] = team
            entry["home_p_1st"] = p_score
        elif side == "AWAY":
            entry["away_team"] = team
            entry["away_p_1st"] = p_score

    rows: List[Dict[str, Any]] = []
    for m, g in by_matchup.items():
        ph_1st = _safe(g.get("home_p_1st"))
        pa_1st = _safe(g.get("away_p_1st"))
        if ph_1st <= 0 or pa_1st <= 0: continue

        # Approximate first-scorer split:
        # Even if both score in 1st, the AWAY team bats first (top of 1st),
        # so they have first crack. Account for that with a slight away bias
        # in 1st inning specifically (home tempo advantage cancels out elsewhere)
        # but here away gets first chance in inning 1.
        # Use combined Poisson-like share with mild away-first-inning boost.
        p_someone_1st = 1 - (1 - ph_1st) * (1 - pa_1st)
        # AWAY bats first, so if both teams score 1+, AWAY scores first ~58% of time.
        # Use weighted share: away_share_1st = pa / (ph + pa) + 0.040 (away batting first bias)
        away_share = pa_1st / (ph_1st + pa_1st) + 0.040
        away_share = max(0.30, min(0.75, away_share))

        # If nobody scores in 1st inning, score comes later; mild home tempo
        # advantage applies (home builds rhythm). Use 50/50 with slight home boost.
        p_first_in_later = 1 - p_someone_1st
        away_share_later = 0.475  # slight home edge in innings 2-9

        # Combined: p_away_first = p_first_in_1st * away_share_1st +
        #                          p_first_later * away_share_later
        p_away_first = p_someone_1st * away_share + p_first_in_later * away_share_later
        p_home_first = 1 - p_away_first

        edge_class = "NONE"
        best_market = None
        if 0.55 <= p_home_first <= 0.68:
            edge_class = "STRONG_HOME_FIRST"
            best_market = {"market": "HOME_FIRST_TO_SCORE",
                           "p": round(p_home_first, 3),
                           "fair_odds": _american(p_home_first)}
        elif 0.55 <= p_away_first <= 0.68:
            edge_class = "STRONG_AWAY_FIRST"
            best_market = {"market": "AWAY_FIRST_TO_SCORE",
                           "p": round(p_away_first, 3),
                           "fair_odds": _american(p_away_first)}

        rows.append({
            "matchup": m,
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_p_1st_inning_score": ph_1st,
            "away_p_1st_inning_score": pa_1st,
            "p_someone_scores_1st_inning": round(p_someone_1st, 3),
            "p_home_first_to_score": round(p_home_first, 3),
            "p_away_first_to_score": round(p_away_first, 3),
            "fair_home_first": _american(p_home_first),
            "fair_away_first": _american(p_away_first),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -max(r["p_home_first_to_score"], r["p_away_first_to_score"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Combines 1st-inning scoring probs with weighted share (away "
                       "+4% in 1st since they bat first, home +2.5% in later innings). "
                       "STRONG when team_first prob in [0.55, 0.68].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-team] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
