"""
EdgeStat -- Tonight's bet ticket master.

Final consolidated bet ticket. Combines:
  - tonight_lock_of_night (highest conviction single pick)
  - tonight_top_5_curated (top 5 curated picks)
  - cross_sport_best_parlays_board (top 3 parlays)
  - tonight_anchor_stack (4-leg cross-sport stack)
  - slate_quality_index (sizing guidance)
  - slate_roi_projection (Kelly sizing)

Produces:
  - 1 LOCK of the night with stake recommendation
  - 5 SINGLES (top 5 curated, smaller stakes)
  - 3 PARLAYS (top parlays, smallest stakes)
  - 1 ANCHOR STACK (cross-sport showpiece)
  - Total expected bankroll allocation %

Output: data/tonight_bet_ticket_master.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_bet_ticket_master.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    quality = _load(os.path.join(DATA_DIR, "slate_quality_index.json"))
    lock = _load(os.path.join(DATA_DIR, "tonight_lock_of_night.json"))
    top_5 = _load(os.path.join(DATA_DIR, "tonight_top_5_curated.json"))
    parlays = _load(os.path.join(DATA_DIR, "cross_sport_best_parlays_board.json"))
    anchor = _load(os.path.join(DATA_DIR, "tonight_anchor_stack.json"))
    roi = _load(os.path.join(DATA_DIR, "slate_roi_projection.json"))

    quality_tier = quality.get("tier") or "MODEST_NIGHT"

    # Sizing per slate quality tier
    sizing_map = {
        "ELITE_NIGHT":     {"lock": 5.0, "singles": 2.0, "parlays": 0.5, "anchor": 1.0},
        "STRONG_NIGHT":    {"lock": 3.0, "singles": 1.5, "parlays": 0.4, "anchor": 0.75},
        "MODEST_NIGHT":    {"lock": 2.0, "singles": 1.0, "parlays": 0.25, "anchor": 0.5},
        "NO_ACTION_NIGHT": {"lock": 0.5, "singles": 0.0, "parlays": 0.0, "anchor": 0.0},
    }
    sizes = sizing_map.get(quality_tier, sizing_map["MODEST_NIGHT"])

    ticket: List[Dict[str, Any]] = []

    # Lock of the night
    lock_pick = lock.get("lock") or {}
    if lock_pick and quality_tier != "NO_ACTION_NIGHT":
        ticket.append({
            "type": "LOCK_OF_NIGHT",
            "subject": lock_pick.get("subject"),
            "source": lock_pick.get("source"),
            "sport": lock_pick.get("sport"),
            "stake_pct_of_bankroll": sizes["lock"],
        })

    # Top 5 singles
    for i, p in enumerate(top_5.get("top_5_picks") or [], 1):
        if not isinstance(p, dict): continue
        if quality_tier == "NO_ACTION_NIGHT": break
        ticket.append({
            "type": f"SINGLE_{i}",
            "subject": p.get("subject"),
            "play": p.get("play"),
            "sport": p.get("sport"),
            "stake_pct_of_bankroll": sizes["singles"],
        })

    # Top 3 parlays
    for i, p in enumerate((parlays.get("top_10_diverse") or [])[:3], 1):
        if not isinstance(p, dict): continue
        if sizes["parlays"] <= 0: break
        ticket.append({
            "type": f"PARLAY_{i}",
            "subject": p.get("subject"),
            "sport": p.get("sport"),
            "source": p.get("source"),
            "n_legs": p.get("n_legs"),
            "parlay_p": p.get("parlay_p"),
            "stake_pct_of_bankroll": sizes["parlays"],
        })

    # Anchor stack (one big cross-sport showpiece)
    anchor_legs = anchor.get("legs") or []
    if anchor_legs and sizes["anchor"] > 0:
        ticket.append({
            "type": "ANCHOR_STACK",
            "tier": anchor.get("tier"),
            "n_legs": len(anchor_legs),
            "legs": anchor_legs,
            "stake_pct_of_bankroll": sizes["anchor"],
        })

    total_pct = sum(t.get("stake_pct_of_bankroll", 0) for t in ticket)

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "slate_quality_tier": quality_tier,
        "n_tickets": len(ticket),
        "total_stake_pct_of_bankroll": round(total_pct, 2),
        "expected_pl_on_100_bankroll": roi.get("expected_pl_on_100_bankroll"),
        "method_note": "Final bet ticket master. Sizing per slate quality tier: "
                       "ELITE 5%/2%/0.5%/1%; STRONG 3%/1.5%/0.4%/0.75%; "
                       "MODEST 2%/1%/0.25%/0.5%; NO_ACTION 0.5%/0/0/0 (lock only). "
                       "All stakes as % of bankroll.",
        "tickets": ticket,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bet-ticket] {o['n_tickets']} tickets, "
          f"total {o['total_stake_pct_of_bankroll']}% bankroll "
          f"({o['slate_quality_tier']}) -> {OUT}")
