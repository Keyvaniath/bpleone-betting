"""
EdgeStat -- honest (book-anchored) game win probabilities at the source.

The game model's raw win probability is OVERCONFIDENT (the same overconfidence the
recalibration engine quantifies; e.g. it had MIL at 78% when the sharp book had
49%). book_vs_model_team.py already defers hard to the book for the EDGE list, but
the raw model prob is still displayed on many surfaces (game.html, mlb.html,
live...). The MLB moneyline close is a sharp, efficient market, and game-line
families are too thin in the ledger for outcome-based calibration -- so the honest
calibration of a game win prob is to shrink it toward the de-vigged book.

This computes, for every game with a free book line (espn_odds.py), a calibrated
win probability and writes a small join file the front-end can opt into -- WITHOUT
mutating today.json (so book_vs_model_team keeps its own raw->book shrink and there
is no double-calibration).

Output: data/game_calibrated.json  (matchup -> {p_home_model, p_home_cal, book...})
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY = os.path.join(DATA_DIR, "today.json")
ESPN = os.path.join(DATA_DIR, "espn_odds.json")
OUT = os.path.join(DATA_DIR, "game_calibrated.json")


def _load(p) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _implied(american) -> Optional[float]:
    if american is None:
        return None
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    return 100.0 / (a + 100.0) if a >= 0 else abs(a) / (abs(a) + 100.0)


def _devig_home(ml_home, ml_away) -> Optional[float]:
    ih, ia = _implied(ml_home), _implied(ml_away)
    if ih is None or ia is None or (ih + ia) <= 0:
        return None
    return ih / (ih + ia)


def _shrink_toward_book(model_p: float, book_devig: float) -> float:
    # Defer HARD to the sharp MLB ML close -- a big model/book disagreement is
    # almost always model overconfidence. Mirrors book_vs_model_team (cap 0.80, x3).
    gap = abs(model_p - book_devig)
    w = min(0.80, gap * 3.0)
    return model_p * (1 - w) + book_devig * w


def run() -> Dict[str, Any]:
    today = _load(TODAY)
    espn_by = (_load(ESPN).get("by_matchup") or {})
    out: Dict[str, Any] = {}
    n_cal = 0
    for g in (today.get("games") or []):
        mk = g.get("matchup")
        nested = g.get("model") or {}
        p_home = nested.get("p_home_win") or g.get("p_home_win")
        market = espn_by.get(mk)
        if mk is None or p_home is None or not market:
            continue
        book_devig = _devig_home(market.get("ml_home"), market.get("ml_away"))
        if book_devig is None:
            continue
        p_home = float(p_home)
        p_cal = round(max(0.01, min(0.99, _shrink_toward_book(p_home, book_devig))), 4)
        out[mk] = {
            "p_home_model": round(p_home, 4),
            "p_home_cal": p_cal,
            "book_home_devig": round(book_devig, 4),
            "shrink_pp": round((p_cal - p_home) * 100, 2),
            "book_ml_home": market.get("ml_home"),
            "book_ml_away": market.get("ml_away"),
        }
        n_cal += 1

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "method": "raw model win prob shrunk toward the de-vigged free book line "
                  "(weight = min(0.80, |gap|*3)); game-line families are too thin for "
                  "outcome calibration, so the sharp book IS the calibration.",
        "n_games": n_cal,
        "by_matchup": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[game-calibrated] {o['n_games']} games book-anchored -> {OUT}")
    for mk, v in list(o["by_matchup"].items())[:10]:
        print(f"    {mk:14s} model {v['p_home_model']:.0%} -> cal {v['p_home_cal']:.0%} "
              f"(book {v['book_home_devig']:.0%}, shrink {v['shrink_pp']:+.1f}pp)")
