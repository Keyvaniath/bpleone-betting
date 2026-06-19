"""
EdgeStat -- golf Play of the Tournament selector.

Picks the top 3 highest-quality golf bets right now, scored by:
  - model probability (higher is more sample-rich)
  - fair odds value (sweet spot 8% to 25% implied prob)
  - rounds_left * sample_floor (low rounds_left = noisier estimates)
  - leader/contender position bias (top 15 only -- field bets too noisy)

Pulls from golf_props.json (winner / top5 / top10) and golf_h2h.json.

Output: data/golf_bestbet.json
  { tournament, generated_at,
    top_bet: { type, player, fair_american, model_prob, confidence, reasoning },
    runners_up: [ ... ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "golf_props.json")
H2H_PATH = os.path.join(DATA_DIR, "golf_h2h.json")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
OUT_PATH = os.path.join(DATA_DIR, "golf_bestbet.json")


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _score(prob: float, market_implied: float = 0.5,
           rounds_left: int = 4) -> float:
    """Quality score: a balanced bet has:
       - 8%-25% probability (sweet spot — high enough to hit, valuable enough to bet)
       - rounds_left >= 1 (any progress remaining)
       - confidence proxy = 1/(1+abs(prob - 0.15)) — prefers probs near 15%
    """
    if not (0.04 < prob < 0.45):
        return 0.0
    confidence = 1.0 / (1.0 + abs(prob - 0.15) * 6)
    # Bonus for tournaments in earlier rounds (more leverage on model)
    round_bonus = 1.0 + (rounds_left - 1) * 0.1
    return confidence * round_bonus


def _pos_phrase(p: Dict[str, Any]) -> str:
    """'#43 (-2)' when a live position exists, else 'pre-tournament field' so a
    pre-event outright never prints a phantom '#None'."""
    pos = p.get("current_pos")
    return f"#{pos} ({p.get('current_total')})" if pos else "pre-tournament field"


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    h2h = _load(H2H_PATH)
    state = _load(STATE_PATH)
    t = state.get("active_tournament") or {}

    if not props.get("players") or t.get("is_complete"):
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no active props" if not props.get("players") else "tournament complete",
            "top_bet": None,
            "runners_up": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # Position-based bets (TOP5 / TOP10, and the WIN reasoning) read the live
    # leaderboard. Between events golf_props keeps the LAST event's final
    # positions during the transition, so those bets go stale and surface a
    # phantom pick (e.g. "Rory top 10, #43" with no live tournament). Treat the
    # leaderboard as valid only when a tournament is genuinely IN PROGRESS.
    # NB: gate on golf_state.active_tournament -- golf_live_tracker.is_live
    # under-reports during live majors (says "not live" mid-round).
    in_progress = (bool(t.get("is_in_progress"))
                   or str(t.get("status") or "").lower() in ("in progress", "in_progress", "live", "active"))
    players = props.get("players") or []
    has_positions = any(p.get("current_pos") for p in players)
    if has_positions and not in_progress:
        # Loaded field carries leaderboard positions but nothing is live -> stale.
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "is_in_progress": False,
            "note": ("between events -- leaderboard positions are stale (no live "
                     "tournament); suppressing position-based bets"),
            "top_bet": None,
            "runners_up": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    rounds_left = props.get("rounds_left", 4)
    candidates: List[Dict[str, Any]] = []

    # Candidate type 1: WIN bets — top 15 by P(win)
    for p in props["players"][:15]:
        s = _score(p.get("p_win", 0), rounds_left=rounds_left)
        if s > 0:
            candidates.append({
                "type": "WIN",
                "player": p["name"],
                "country": p.get("country"),
                "current_pos": p.get("current_pos"),
                "current_total": p.get("current_total"),
                "model_prob": p["p_win"],
                "fair_american": p.get("fair_win_american"),
                "score": s,
                "reasoning": f"P(win) {p['p_win']*100:.1f}% with {rounds_left} round(s) left -- sweet-spot value at {_pos_phrase(p)}.",
                "bet_key": f"GOLF|{p['name']}|win|{p.get('fair_win_american','?')}",
                "bet_label": f"{p['name']} to win {t.get('name','')}",
            })

    # Candidate type 2: TOP 5 — best implied EV from sample
    for p in props["players"][:40]:
        s = _score(p.get("p_top5", 0), rounds_left=rounds_left)
        if s > 0:
            candidates.append({
                "type": "TOP5",
                "player": p["name"],
                "country": p.get("country"),
                "current_pos": p.get("current_pos"),
                "current_total": p.get("current_total"),
                "model_prob": p["p_top5"],
                "fair_american": p.get("fair_top5_american"),
                "score": s * 0.95,    # slight discount vs WIN since lower vig
                "reasoning": f"P(top 5) {p['p_top5']*100:.1f}% -- lower variance than outright but compelling line.",
                "bet_key": f"GOLF|{p['name']}|top5|{p.get('fair_top5_american','?')}",
                "bet_label": f"{p['name']} top 5 at {t.get('name','')}",
            })

    # Candidate type 3: TOP 10 — safer floor for contenders
    for p in props["players"][:60]:
        s = _score(p.get("p_top10", 0), rounds_left=rounds_left)
        if s > 0 and p.get("p_top10", 0) > 0.12:    # only worthwhile if double-digit
            candidates.append({
                "type": "TOP10",
                "player": p["name"],
                "country": p.get("country"),
                "current_pos": p.get("current_pos"),
                "current_total": p.get("current_total"),
                "model_prob": p["p_top10"],
                "fair_american": p.get("fair_top10_american"),
                "score": s * 0.9,
                "reasoning": f"P(top 10) {p['p_top10']*100:.1f}% -- safest finish bet ({_pos_phrase(p)}).",
                "bet_key": f"GOLF|{p['name']}|top10|{p.get('fair_top10_american','?')}",
                "bet_label": f"{p['name']} top 10 at {t.get('name','')}",
            })

    # Candidate type 4: Best H2H matchup (closest to 50/50 but slight edge)
    for m in (h2h.get("matchups") or [])[:30]:
        # Look for matchups where one side has 55%-65% prob -- good leverage
        for side in ("a", "b"):
            p_side = m["p_a_beats_b"] if side == "a" else m["p_b_beats_a"]
            if 0.55 <= p_side <= 0.68:
                player_a = m["player_a"] if side == "a" else m["player_b"]
                player_b = m["player_b"] if side == "a" else m["player_a"]
                fair = m["fair_a_american"] if side == "a" else m["fair_b_american"]
                candidates.append({
                    "type": "H2H",
                    "player": player_a,
                    "opponent": player_b,
                    "model_prob": p_side,
                    "fair_american": fair,
                    "score": (1.0 - abs(p_side - 0.60)) * 0.85,
                    "reasoning": f"P({player_a} beats {player_b}) = {p_side*100:.1f}%. Tight matchup with model lean.",
                    "bet_key": f"GOLF|{player_a}|h2h_{player_b}|{fair or '?'}",
                    "bet_label": f"{player_a} beats {player_b} (H2H)",
                })

    if not candidates:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no candidates passed quality filter",
            "top_bet": None,
            "runners_up": [],
        }
    else:
        candidates.sort(key=lambda c: -c["score"])
        # Compute confidence label
        def conf(s):
            if s >= 0.8: return "HIGH"
            if s >= 0.5: return "MED"
            return "LOW"
        for c in candidates:
            c["confidence"] = conf(c["score"])
            c["score"] = round(c["score"], 4)
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "is_in_progress": in_progress,
            "rounds_left": rounds_left,
            "n_candidates": len(candidates),
            "top_bet": candidates[0],
            "runners_up": candidates[1:5],
        }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    if p.get("top_bet"):
        b = p["top_bet"]
        print(f"  POT: {b['type']} -- {b.get('player')} (fair {b.get('fair_american')})")
        print(f"  {b.get('reasoning')}")
        print(f"  Runners up: {len(p.get('runners_up',[]))}")
    else:
        print(f"  {p.get('note')}")
