"""
EdgeStat -- MLB moneyline edge synthesizer (170-MODULE MILESTONE).

Cross-references the book ML with model-derived win probability to surface
the highest-edge ML picks of the slate.

Method:
  - Pull book_ml from matchups.json (ml_home, ml_away)
  - De-vig the book pair (normalize implied probs to sum to 1.0)
  - Compute model_win_prob from Skellam P(home_runs > away_runs)
    using lam_home / lam_away from team_total_edge
  - Bayesian-shrink toward book consensus (40% weight to book)
  - Edge = anchored_win_prob - book_devig_prob
  - STRONG_ML when edge >= 4% AND p in [25%, 75%] value zone

Output: data/mlb_ml_edge_synthesizer.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_ml_edge_synthesizer.json")


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


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american_to_prob(odds) -> float:
    if odds is None: return 0.5
    try:
        o = int(odds)
    except Exception:
        return 0.5
    if o == 0: return 0.5
    if o > 0: return 100.0 / (o + 100)
    return -o / (-o + 100)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _devig(p_home_raw: float, p_away_raw: float) -> (float, float):
    """Normalize implied probs to sum to 1.0 (remove vig)."""
    total = p_home_raw + p_away_raw
    if total <= 0: return 0.5, 0.5
    return p_home_raw / total, p_away_raw / total


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))

    # Index team total lams by matchup
    lams: Dict[str, Dict[str, float]] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        proj = _safe(r.get("model_expected_runs_anchored"))
        entry = lams.setdefault(m, {})
        if r.get("side") == "HOME": entry["home_lam"] = proj
        elif r.get("side") == "AWAY": entry["away_lam"] = proj

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        market = g.get("market") or {}
        ml_home = market.get("ml_home")
        ml_away = market.get("ml_away")
        if ml_home is None or ml_away is None: continue

        # De-vig book ML
        p_home_raw = _american_to_prob(ml_home)
        p_away_raw = _american_to_prob(ml_away)
        p_home_book, p_away_book = _devig(p_home_raw, p_away_raw)

        # Compute model win prob from Skellam
        lam_data = lams.get(matchup, {})
        lam_h = _safe(lam_data.get("home_lam"))
        lam_a = _safe(lam_data.get("away_lam"))
        if lam_h <= 0 or lam_a <= 0: continue

        mu = lam_h - lam_a
        sigma = math.sqrt(lam_h + lam_a)
        # P(home wins) = P(D >= 1) with continuity correction
        z = (1 - 0.5 - mu) / sigma if sigma > 0 else 0
        p_home_model = 1 - _norm_cdf(z)

        # Bayesian shrink toward book
        anchor_w = 0.40
        p_home_anchored = p_home_book * anchor_w + p_home_model * (1 - anchor_w)
        p_away_anchored = 1 - p_home_anchored

        # Compute edge vs book
        edge_home = p_home_anchored - p_home_book
        edge_away = p_away_anchored - p_away_book

        # ROI vs book odds
        decimal_home = (1 / p_home_book) if p_home_book > 0 else 0
        decimal_away = (1 / p_away_book) if p_away_book > 0 else 0
        roi_home = p_home_anchored * decimal_home - 1
        roi_away = p_away_anchored * decimal_away - 1

        edge_class = "NONE"
        best_market = None
        # STRONG: 4%+ edge AND in value zone [25%, 75%]
        if edge_home >= 0.04 and 0.25 <= p_home_anchored <= 0.75:
            edge_class = "STRONG_HOME_ML"
            best_market = {"market": "HOME_ML",
                           "book_odds": ml_home,
                           "model_prob": round(p_home_anchored, 3),
                           "book_devig_prob": round(p_home_book, 3),
                           "edge_pp": round(edge_home * 100, 1),
                           "roi_pct": round(roi_home * 100, 1)}
        elif edge_away >= 0.04 and 0.25 <= p_away_anchored <= 0.75:
            edge_class = "STRONG_AWAY_ML"
            best_market = {"market": "AWAY_ML",
                           "book_odds": ml_away,
                           "model_prob": round(p_away_anchored, 3),
                           "book_devig_prob": round(p_away_book, 3),
                           "edge_pp": round(edge_away * 100, 1),
                           "roi_pct": round(roi_away * 100, 1)}

        rows.append({
            "matchup": matchup,
            "ml_home": ml_home,
            "ml_away": ml_away,
            "p_home_book_devig": round(p_home_book, 3),
            "p_away_book_devig": round(p_away_book, 3),
            "p_home_model": round(p_home_model, 3),
            "p_home_anchored": round(p_home_anchored, 3),
            "p_away_anchored": round(p_away_anchored, 3),
            "edge_home_pp": round(edge_home * 100, 2),
            "edge_away_pp": round(edge_away * 100, 2),
            "roi_home_pct": round(roi_home * 100, 1),
            "roi_away_pct": round(roi_away * 100, 1),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -max(r["edge_home_pp"], r["edge_away_pp"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_ml_edges": len(strong),
        "method_note": "Model ML from Skellam(lam_h, lam_a), book de-vigged, "
                       "Bayesian-anchored 40% toward book. STRONG when edge >= 4% AND "
                       "anchored prob in [25%, 75%] value zone.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ml-edge] {o['n_games']} games, {o['n_strong_ml_edges']} strong ML edges -> {OUT}")
