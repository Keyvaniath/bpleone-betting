"""
EdgeStat -- REAL book-vs-model team-level edge detection.

matchups.json already has live Bovada lines per game:
  market.ml_home, market.ml_away, market.total

Combined with the model's per-game projection (p_home_win, fair_total)
this lets us compute genuine pricing errors:

  book_implied_prob = 1 / book_decimal  (after de-vigging)
  model_prob        = p_home_win (or 1 - p_home_win for away)
  edge_pct          = model_prob * book_decimal - 1

Filter: edge_pct >= 3% and model_prob in [0.30, 0.78] (avoid extremes).
Surface the top mispriced sides as the "Book Edge Board" — these are
the REAL +EV plays from real book lines, not model-priced fairs.

Output: data/book_vs_model_team.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "book_vs_model_team.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(a):
    if a is None: return None
    try: a = int(a)
    except Exception: return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _decimal_to_american(d):
    if d is None or d <= 1.0: return None
    if d >= 2.0: return int(round((d - 1) * 100))
    return -int(round(100 / (d - 1)))


def _implied_from_decimal(d):
    if d is None or d <= 1.0: return None
    return 1.0 / d


def _devig_pair(home_ml, away_ml):
    """Remove vig by normalizing implied probs to sum to 1."""
    dh = _american_to_decimal(home_ml)
    da = _american_to_decimal(away_ml)
    if not dh or not da: return None, None
    ih = 1.0 / dh
    ia = 1.0 / da
    total = ih + ia
    return ih / total, ia / total  # de-vigged probs


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    # Index model picks by gamePk or matchup string
    model_by_key = {}
    today_games = today.get("games") or []
    for g in today_games:
        k = g.get("matchup") or g.get("gamePk")
        if k: model_by_key[k] = g

    games = matchups.get("games") or []
    edges: List[Dict[str, Any]] = []

    for g in games:
        market = g.get("market") or {}
        ml_home_book = market.get("ml_home")
        ml_away_book = market.get("ml_away")
        total_book = market.get("total")
        if ml_home_book is None or ml_away_book is None: continue

        matchup = g.get("matchup")
        model_g = model_by_key.get(matchup) or {}
        # today.json nests model output: model_g["model"]["p_home_win"]
        nested_model = model_g.get("model") or {}
        p_home_model = (
            nested_model.get("p_home_win")
            or model_g.get("p_home_win")
            or model_g.get("model_home_win")
        )
        fair_total_model = (
            nested_model.get("fair_total")
            or model_g.get("fair_total")
            or model_g.get("model_total")
        )

        # Skip if no model probability available
        if p_home_model is None: continue
        p_away_model = 1.0 - p_home_model

        # Book de-vigged probs (no juice)
        book_home_devig, book_away_devig = _devig_pair(ml_home_book, ml_away_book)
        if book_home_devig is None: continue

        # Book decimals (with juice — that's what you actually bet at)
        book_home_decimal = _american_to_decimal(ml_home_book)
        book_away_decimal = _american_to_decimal(ml_away_book)

        # EDGE per side: model_prob * book_decimal_paid - 1
        edge_home = p_home_model * book_home_decimal - 1
        edge_away = p_away_model * book_away_decimal - 1

        for side, model_p, book_ml, book_dec, book_devig, edge_pct in (
            ("HOME", p_home_model, ml_home_book, book_home_decimal, book_home_devig, edge_home),
            ("AWAY", p_away_model, ml_away_book, book_away_decimal, book_away_devig, edge_away),
        ):
            if model_p < 0.30 or model_p > 0.78: continue
            if edge_pct < 0.03: continue   # need 3% edge to surface
            team = (g.get("home") if side == "HOME" else g.get("away")) or {}
            team_abbr = team.get("abbr") if isinstance(team, dict) else side
            edges.append({
                "matchup": matchup,
                "side": side,
                "team": team_abbr or side,
                "model_prob": round(model_p, 4),
                "book_implied_devig": round(book_devig, 4),
                "model_book_gap_pp": round((model_p - book_devig) * 100, 2),
                "book_american": book_ml,
                "book_decimal": round(book_dec, 3),
                "edge_pct": round(edge_pct * 100, 2),
                "kelly_fraction": round(max(0, (model_p * book_dec - 1) / (book_dec - 1)), 4) if book_dec > 1 else 0,
                "is_underdog": book_ml > 0,
            })

    edges.sort(key=lambda e: -e["edge_pct"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_edges": len(edges),
        "top_5": edges[:5],
        "all_edges": edges,
        "method_note": "REAL book vs model team-ML comparison. Bovada ML lines de-vigged. "
                       "edge_pct = model_prob * book_decimal - 1. Filter 3%+ edge, "
                       "model_prob in [0.30, 0.78].",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[book-vs-model] {o['n_edges']} edges -> {OUT}")
    for e in o['top_5']:
        print(f"  {e['matchup']} {e['side']} ({e['team']}) "
              f"model {e['model_prob']:.1%} vs book {e['book_implied_devig']:.1%} "
              f"({'+'if e['book_american']>=0 else ''}{e['book_american']}) "
              f"edge={e['edge_pct']:+.2f}%")
