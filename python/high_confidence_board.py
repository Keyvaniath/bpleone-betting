"""
EdgeStat -- High-Confidence Board (a tier above a single Alpha Pick of the Day).

Surfaces the slate's strongest model-conviction plays as a ranked board. Built
from the ODDS-INDEPENDENT model picks (so it populates even while the book-odds
feed is dark), drawn from the segments that actually win -- player props (the
MLB-PP book hits ~85%), game edges, golf/UFC -- with the overconfident heavy
favorites FILTERED OUT using the same gate as the ledger (they bleed -20% ROI).

Each play gets a confidence score (model probability, with a small boost for the
proven player-prop segment) and a tier: ELITE / STRONG / SOLID.

Output: data/high_confidence_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "high_confidence_board.json")

FAV_FLOOR = -150          # game lines: exclude heavy favorites (the overconfident segment the ledger gates)
PROP_PRICE_FLOOR = -350   # props: exclude trivially-juicy lays (e.g. -900 "pitcher won't get the win")
                          # -- 90%+ but no value; a featured PLAY must have a real payout.
MIN_PROB = 0.60           # a real lean, not a coin flip
PLAYER_PROP_BOOST = 1.5   # confidence pts -- the player-prop book is the best-calibrated segment

# Cross-sport player-prop feeds (read their strong_edges/rows). MLB comes from the
# already-joined game cards. Each entry: (file, sport, subject_keys).
XSPORT = [
    ("nba_player_points_props.json", "NBA", ("player",)),
    ("nba_player_pra_props.json", "NBA", ("player",)),
    ("nhl_skater_sog_props.json", "NHL", ("player", "skater")),
    ("nhl_anytime_goal_props.json", "NHL", ("player",)),
    ("wnba_player_pts_props.json", "WNBA", ("player",)),
    ("golf_top_finish_props.json", "GOLF", ("name", "player")),
]


def _load(name: str) -> Any:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _num(x) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def _tier(prob: float) -> str:
    if prob >= 0.72:
        return "ELITE"
    if prob >= 0.66:
        return "STRONG"
    return "SOLID"


def _add(out, *, sport, subject, matchup, market, prob, fair, family, source):
    prob = _num(prob)
    if prob is None or prob < MIN_PROB:
        return
    fair = _num(fair)
    # Price gates by segment. Game lines: drop heavy favorites (the overconfident,
    # bleeding segment). Props: keep favorites (well-calibrated) but drop the
    # trivially-juicy lays that have no real payout.
    if fair is not None:
        if family in ("game", "team") and fair <= FAV_FLOOR:
            return
        if family not in ("game", "team") and fair <= PROP_PRICE_FLOOR:
            return
    score = round(prob * 100 + (PLAYER_PROP_BOOST if family in ("pitcher", "batter", "player") else 0), 1)
    out.append({
        "sport": sport, "subject": subject, "matchup": matchup, "market": market,
        "prob": round(prob, 3), "fair_odds": (int(fair) if fair is not None else None),
        "family": family, "source": source,
        "confidence": score, "tier": _tier(prob),
    })


def run() -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []

    # MLB: reuse the already-joined per-game predictions
    cards = _load("mlb_game_cards.json").get("games") or []
    for c in cards:
        for p in (c.get("predictions") or []):
            _add(out, sport="MLB", subject=p.get("subject"), matchup=c.get("matchup"),
                 market=p.get("market"), prob=p.get("prob"), fair=p.get("fair_odds"),
                 family=p.get("family"), source="mlb_props")

    # Cross-sport player props (strong edges)
    for fname, sport, subj_keys in XSPORT:
        j = _load(fname)
        rows = j.get("strong_edges") or j.get("rows") or []
        for r in rows:
            if not isinstance(r, dict):
                continue
            bm = r.get("best_market") or {}
            subject = next((r.get(k) for k in subj_keys if r.get(k)), None)
            _add(out, sport=sport, subject=subject, matchup=r.get("matchup"),
                 market=bm.get("market") or r.get("market"),
                 prob=bm.get("p") if bm.get("p") is not None else r.get("p_scores") or r.get("prob"),
                 fair=bm.get("fair_odds") or r.get("fair_odds") or r.get("fair_yes"),
                 family="player", source=fname.replace(".json", ""))

    out.sort(key=lambda p: -p["confidence"])
    board = out[:24]
    counts = {t: sum(1 for p in board if p["tier"] == t) for t in ("ELITE", "STRONG", "SOLID")}

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_board": len(board),
        "n_candidates": len(out),
        "tier_counts": counts,
        "method_note": "Top model-conviction plays (odds-independent), drawn from the "
                       "well-calibrated player-prop + game-edge segments. Heavy favorites "
                       f"(fair <= {FAV_FLOOR}) excluded -- that segment bleeds. Tier by model "
                       "probability: ELITE >=72%, STRONG >=66%, SOLID >=60%.",
        "board": board,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[high-conf] {o['n_board']} plays on board ({o['tier_counts']}) "
          f"from {o['n_candidates']} candidates -> {OUT}")
