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

import prob_calibration as pc   # real-outcome curation + empirical calibration

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
    raw = _num(prob)
    if raw is None:
        return
    # Guard 1 -- CURATION: never surface a market family the settled ledger proves
    # loses money (e.g. to_hit_hr -122u, k_1plus -189u), no matter the raw hit rate.
    if pc.is_proven_negative(market):
        return
    # Guard 2 -- EMPIRICAL CALIBRATION: blend the raw model prob toward the family's
    # realized hit rate from the ledger, so the displayed number is honest.
    cal, meta = pc.empirical_calibrate(raw, market)
    if cal is None or cal < MIN_PROB:
        return
    # Display the fair price implied by the CALIBRATED prob, so probability and odds
    # never disagree. Then gate on that: game lines drop heavy favorites (bleeding
    # segment); props drop trivially-juicy lays with no real payout.
    fair_cal = pc.prob_to_american(cal)
    if fair_cal is not None:
        if family in ("game", "team") and fair_cal <= FAV_FLOOR:
            return
        if family not in ("game", "team") and fair_cal <= PROP_PRICE_FLOOR:
            return
    score = round(cal * 100 + (PLAYER_PROP_BOOST if family in ("pitcher", "batter", "player") else 0), 1)
    rec = {
        "sport": sport, "subject": subject, "matchup": matchup, "market": market,
        "prob": round(cal, 3), "raw_prob": round(raw, 3),
        "fair_odds": (int(fair_cal) if fair_cal is not None else None),
        "family": family, "source": source,
        "confidence": score, "tier": _tier(cal),
        "calibration": meta.get("method"),
    }
    if meta.get("method") == "empirical":
        rec["cal_n"] = meta.get("n")
        rec["cal_realized"] = meta.get("realized")
    out.append(rec)


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
    n_empirical = sum(1 for p in board if p.get("calibration") == "empirical")

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_board": len(board),
        "n_candidates": len(out),
        "tier_counts": counts,
        "n_calibrated_on_outcomes": n_empirical,
        "n_proven_negative_families_excluded": len(pc.proven_negative_families()),
        "method_note": "Top model-conviction plays (odds-independent). TWO real-outcome guards "
                       "from the settled ledger: (1) CURATION -- market families proven to lose "
                       "money are hard-excluded (ROI, not hit rate); (2) EMPIRICAL CALIBRATION -- "
                       "each probability is blended toward its family's realized hit rate, so the "
                       f"number shown is honest. Heavy game-line favorites (fair <= {FAV_FLOOR}) "
                       f"and trivially-juicy prop lays (fair <= {PROP_PRICE_FLOOR}) excluded. Tier "
                       "by calibrated probability: ELITE >=72%, STRONG >=66%, SOLID >=60%.",
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
