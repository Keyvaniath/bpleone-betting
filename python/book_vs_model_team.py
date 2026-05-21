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


# 2026-05-21: Bayesian shrinkage toward the book. The book is the market
# consensus — when our model disagrees by >10pp it's usually wrong, not
# the book. Shrink model probability toward book implied with weight that
# grows with the size of the gap:
#   weight_on_book = min(0.40, |gap| * 2.0)
#       e.g. 5pp gap -> 10% book weight
#            15pp gap -> 30% book weight
#            25pp gap -> 40% book weight (capped)
def _shrink_toward_book(model_p: float, book_devig: float) -> float:
    if model_p is None or book_devig is None: return model_p
    gap = abs(model_p - book_devig)
    weight_book = min(0.40, gap * 2.0)
    return model_p * (1 - weight_book) + book_devig * weight_book


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
    total_edges: List[Dict[str, Any]] = []

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
            # Calibrated probability shrinks model toward book consensus
            calibrated_p = _shrink_toward_book(model_p, book_devig)
            calibrated_edge = calibrated_p * book_dec - 1
            edges.append({
                "matchup": matchup,
                "side": side,
                "team": team_abbr or side,
                "model_prob": round(model_p, 4),
                "calibrated_prob": round(calibrated_p, 4),
                "book_implied_devig": round(book_devig, 4),
                "model_book_gap_pp": round((model_p - book_devig) * 100, 2),
                "book_american": book_ml,
                "book_decimal": round(book_dec, 3),
                "edge_pct": round(edge_pct * 100, 2),
                "calibrated_edge_pct": round(calibrated_edge * 100, 2),
                "kelly_fraction": round(max(0, (model_p * book_dec - 1) / (book_dec - 1)), 4) if book_dec > 1 else 0,
                "kelly_calibrated": round(max(0, (calibrated_p * book_dec - 1) / (book_dec - 1)), 4) if book_dec > 1 else 0,
                "is_underdog": book_ml > 0,
            })

        # ----- TOTALS (Over/Under) book-vs-model edge -----
        # Model gives p_over_market (probability OVER the book's posted total).
        # Book total prices are typically -110/-110 each side (decimal ~1.91).
        # Standard -110/-110 means de-vigged 50/50. We compute edge directly
        # using model's p_over and the book's standard ~1.91 decimal.
        p_over_model = nested_model.get("p_over_market") or model_g.get("p_over_market")
        if p_over_model is not None and total_book is not None:
            # Assume -110 each side (typical MLB total juice) unless book provides custom
            over_book_dec = 1.909  # -110 in decimal
            under_book_dec = 1.909
            p_under_model = 1.0 - p_over_model
            edge_over = p_over_model * over_book_dec - 1
            edge_under = p_under_model * under_book_dec - 1

            for tot_side, tot_p, tot_dec, tot_edge in (
                ("OVER", p_over_model, over_book_dec, edge_over),
                ("UNDER", p_under_model, under_book_dec, edge_under),
            ):
                if tot_p < 0.30 or tot_p > 0.78: continue
                if tot_edge < 0.03: continue
                calibrated_p_tot = _shrink_toward_book(tot_p, 0.5)
                calibrated_edge_tot = calibrated_p_tot * tot_dec - 1
                total_edges.append({
                    "matchup": matchup,
                    "side": tot_side,
                    "total_line": total_book,
                    "model_prob": round(tot_p, 4),
                    "calibrated_prob": round(calibrated_p_tot, 4),
                    "book_implied_devig": 0.5,  # standard -110 = 50% devig
                    "model_book_gap_pp": round((tot_p - 0.5) * 100, 2),
                    "book_american": -110,
                    "book_decimal": over_book_dec,
                    "edge_pct": round(tot_edge * 100, 2),
                    "calibrated_edge_pct": round(calibrated_edge_tot * 100, 2),
                    "kelly_fraction": round(max(0, (tot_p * tot_dec - 1) / (tot_dec - 1)), 4),
                    "kelly_calibrated": round(max(0, (calibrated_p_tot * tot_dec - 1) / (tot_dec - 1)), 4),
                })

    # Sort by CALIBRATED edge (post-shrinkage) — this is the honest ranking
    edges.sort(key=lambda e: -e.get("calibrated_edge_pct", e.get("edge_pct", 0)))
    total_edges.sort(key=lambda e: -e.get("calibrated_edge_pct", e.get("edge_pct", 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_ml_edges": len(edges),
        "n_total_edges": len(total_edges),
        "n_edges": len(edges) + len(total_edges),  # combined for backwards compat
        "top_5": edges[:5],
        "all_edges": edges,
        "ml_edges": edges,
        "total_edges": total_edges,
        "method_note": "REAL book-vs-model. ML lines de-vigged from matchups.market.ml_*. "
                       "Totals use standard -110/-110 (1.909 decimal) since matchups.market.total "
                       "doesn't include the price (just the line). Filter 3%+ edge, "
                       "model_prob in [0.30, 0.78].",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[book-vs-model] {o['n_ml_edges']} ML edges + {o['n_total_edges']} total edges -> {OUT}")
    for e in o['top_5']:
        print(f"  ML  {e['matchup']} {e['side']} ({e['team']}) "
              f"model {e['model_prob']:.1%} vs book {e['book_implied_devig']:.1%} "
              f"({'+'if e['book_american']>=0 else ''}{e['book_american']}) "
              f"edge={e['edge_pct']:+.2f}%")
    for e in o['total_edges'][:5]:
        print(f"  TOT {e['matchup']} {e['side']} {e['total_line']} "
              f"model {e['model_prob']:.1%} edge={e['edge_pct']:+.2f}%")
