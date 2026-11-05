"""
EdgeStat -- golf 2-3-leg parlay builder.

Generates the highest-EV 2-leg and 3-leg parlays from tonight's golf board.
Leg candidates pulled from:
  - WIN bets (top 8 by P(win))
  - TOP 5 bets (top 15 by P(top5))
  - TOP 10 bets (top 25 by P(top10))
  - MAKE CUT bets (top 20 with non-trivial P(cut), early-tournament only)
  - H2H matchups (close 50/50 to 65/35 from top-30)

Joint probability:
  - Assume mostly-independent legs (no SG model coupling yet)
  - Apply small NEGATIVE correlation penalty when two legs are same-player
    (same-player legs are *positively* correlated — book overcharges for that,
     we slightly under-price to be conservative)
  - For different-player legs we assume independence (golf finishes
    are weakly correlated; books treat them as independent for parlays)

Output: data/golf_parlays.json
  { tournament, generated_at, n_parlays, parlays: [...] }

PARLAY BOARD RETIRED (2026-11-03): every leg is an unvalidated model
projection with no sportsbook price, and the old "EV" compared the joint
model probability with the product of the model's OWN fair odds (and the leg
labels read "@ -100" as if those were lines). `parlays` is now always empty so
no desk or cross-sport injector recommends a parlay by default. When a
tournament is in progress the combinations are kept under `research_exhibit`
with joint model probability only -- no price, no EV, not a recommendation.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from itertools import combinations
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "golf_props.json")
MAKECUT_PATH = os.path.join(DATA_DIR, "golf_makecut.json")
H2H_PATH = os.path.join(DATA_DIR, "golf_h2h.json")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
OUT_PATH = os.path.join(DATA_DIR, "golf_parlays.json")

MAX_LEGS = 3
MAX_PARLAYS = 15
MIN_LEG_PROB = 0.10       # don't build parlays out of < 10% legs
SAME_PLAYER_CORR_BUMP = 1.10  # legs on same player get a 10% joint-prob bump


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _amer(p: float) -> int:
    if p <= 0 or p >= 1:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _decimal(american) -> float:
    if american is None or american == 0:
        return 1.0
    if american > 0:
        return 1 + (american / 100)
    return 1 + (100 / abs(american))


# (2026-11-03) _ev_pct removed: it measured the joint model prob against the
# product of the model's own fair odds -- not an expected value vs any book.


def _build_legs() -> List[Dict[str, Any]]:
    """Pool of all candidate legs (each one a single playable bet)."""
    props = _load(PROPS_PATH)
    makecut = _load(MAKECUT_PATH)
    h2h = _load(H2H_PATH)
    legs: List[Dict[str, Any]] = []

    # WIN legs
    for p in (props.get("players") or [])[:8]:
        if (p.get("p_win") or 0) >= MIN_LEG_PROB:
            legs.append({
                "kind": "WIN",
                "player": p["name"],
                "prob": p["p_win"],
                "fair_american": p.get("fair_win_american"),
                "label": f"{p['name']} WIN (model projection)",   # (2026-11-03) no "@ price"
            })

    # TOP5 legs
    for p in (props.get("players") or [])[:15]:
        if (p.get("p_top5") or 0) >= MIN_LEG_PROB:
            legs.append({
                "kind": "TOP5",
                "player": p["name"],
                "prob": p["p_top5"],
                "fair_american": p.get("fair_top5_american"),
                "label": f"{p['name']} TOP 5 (model projection)",   # (2026-11-03) no "@ price"
            })

    # TOP10 legs
    for p in (props.get("players") or [])[:25]:
        if (p.get("p_top10") or 0) >= 0.15:    # tighter floor for top10
            legs.append({
                "kind": "TOP10",
                "player": p["name"],
                "prob": p["p_top10"],
                "fair_american": p.get("fair_top10_american"),
                "label": f"{p['name']} TOP 10 (model projection)",   # (2026-11-03) no "@ price"
            })

    # MAKE CUT legs (only when cut is in play and prob between 0.50 and 0.85)
    if makecut.get("cut_in_play"):
        for p in (makecut.get("players") or [])[:20]:
            pc = p.get("p_makecut") or 0
            if 0.50 <= pc <= 0.85:
                legs.append({
                    "kind": "MAKE_CUT",
                    "player": p["name"],
                    "prob": pc,
                    "fair_american": p.get("fair_makecut_american"),
                    "label": f"{p['name']} MAKE CUT (model projection)",   # (2026-11-03) no "@ price"
                })

    # H2H legs (one side at a time, only when ~50-70%)
    for m in (h2h.get("matchups") or [])[:30]:
        for side in ("a", "b"):
            prob = m["p_a_beats_b"] if side == "a" else m["p_b_beats_a"]
            fair = m["fair_a_american"] if side == "a" else m["fair_b_american"]
            player = m["player_a"] if side == "a" else m["player_b"]
            opp = m["player_b"] if side == "a" else m["player_a"]
            if 0.50 < prob <= 0.70:
                legs.append({
                    "kind": "H2H",
                    "player": player,
                    "opponent": opp,
                    "prob": prob,
                    "fair_american": fair,
                    "label": f"{player} beats {opp} (model projection)",   # (2026-11-03) no "@ price"
                })

    return legs


def _joint(legs: List[Dict[str, Any]]) -> Tuple[float, float]:
    """Returns (joint_prob, parlay_decimal). Joint prob applies same-player
    bump; parlay decimal is the multiplicative fair-odds product."""
    prob = 1.0
    decimal = 1.0
    for leg in legs:
        prob *= leg["prob"]
        decimal *= _decimal(leg["fair_american"])
    # Bump if any two legs share a player (positive correlation)
    players = [leg["player"] for leg in legs]
    if len(set(players)) < len(players):
        prob = min(0.99, prob * SAME_PLAYER_CORR_BUMP)
    return prob, decimal


RETIRED_NOTE = ("Parlay board retired (2026-11-03): legs are unvalidated model "
                "projections with no sportsbook price -- not a recommendation.")


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    t = state.get("active_tournament") or {}
    # (2026-11-03) pre-event: nothing to combine (an all-"E" field produced
    # coin-flip H2H legs and "+700" parlays for a tournament not yet started).
    if not (t.get("is_in_progress") or t.get("is_complete")):
        start = (t.get("start_date") or "")[:10]
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "is_pre_event": True,
            "note": (f"Tournament starts {start}; projections appear once play begins. "
                     if start else "") + RETIRED_NOTE,
            "n_parlays": 0,
            "parlays": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload
    if t.get("is_complete"):
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "tournament complete -- no live parlays",
            "n_parlays": 0,
            "parlays": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    legs = _build_legs()
    if not legs:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no qualifying legs",
            "n_parlays": 0,
            "parlays": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # Build all 2-leg and 3-leg combinations (cap input pool to keep combinatorial
    # explosion in check)
    pool = legs[:40]
    parlays: List[Dict[str, Any]] = []
    for n in range(2, MAX_LEGS + 1):
        for combo in combinations(pool, n):
            joint, dec = _joint(list(combo))
            if joint < 0.005:         # parlays below 0.5% are noise
                continue
            # (2026-11-03) ev_pct / parlay fair odds removed: the "EV" was the
            # model's joint prob against the product of its own fair odds.
            # Quality score: prefer balanced parlays in the sweet-spot
            # 1-10% joint prob, n>=2 legs, modest correlation bump
            sweet = 1.0 / (1.0 + abs(joint - 0.05) * 4)
            quality = sweet * (1.0 + (n - 2) * 0.05)
            parlays.append({
                "n_legs": n,
                "joint_model_prob": round(joint, 4),
                "quality_score": round(quality, 4),
                "legs": [{
                    "kind": l["kind"],
                    "label": l["label"],
                    "player": l["player"],
                    "opponent": l.get("opponent"),
                    "model_prob": round(l["prob"], 4),
                } for l in combo],
            })

    parlays.sort(key=lambda p: -p["quality_score"])
    top = parlays[:MAX_PARLAYS]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": t.get("name"),
        "note": RETIRED_NOTE,
        "n_legs_in_pool": len(pool),
        "n_parlays_evaluated": len(parlays),
        # (2026-11-03) no recommended parlays, ever, by default
        "n_parlays": 0,
        "parlays": [],
        "research_exhibit": {
            "label": "research exhibit, not a recommendation -- unvalidated "
                     "model projections, no sportsbook price, no EV",
            "combinations": top,
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_parlays']} recommended parlays (board retired 2026-11-03)")
    print(f"  {p.get('note', '')}")
    ex = (p.get("research_exhibit") or {}).get("combinations") or []
    for i, par in enumerate(ex[:5], 1):
        print(f"  exhibit [{i}] {par['n_legs']}-leg -- joint model prob {par['joint_model_prob']*100:.2f}%")
        for l in par["legs"]:
            print(f"      - {l['label']}")
