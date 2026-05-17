"""
EdgeStat -- golf Play of the Tournament historical record.

Every cron snapshots the current golf_bestbet.top_bet into a rolling history,
keyed by (tournament, date). On subsequent runs, settles each entry against
the actual tournament result (winner / top5 / top10 status, H2H outcome).

Settlement happens when state.active_tournament.is_complete = True and a
final leaderboard is available. Past picks before the leaderboard cleared
to a new tournament are auto-settled the moment they go final.

Output: data/golf_pot_history.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
BESTBET_PATH = os.path.join(DATA_DIR, "golf_bestbet.json")
HIST_PATH = os.path.join(DATA_DIR, "golf_pot_history.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _payout_units(american) -> float:
    if american is None:
        return 0
    return american / 100 if american >= 0 else 100 / abs(american)


def _final_position(field: List[Dict[str, Any]], player_name: str) -> Optional[int]:
    for p in field:
        if p.get("name") == player_name:
            return p.get("order")
    return None


def _settle_entry(entry: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Look at the current state -- if it's a different tournament or this
    one is complete, settle the entry."""
    t = state.get("active_tournament") or {}
    state_tname = t.get("name")
    entry_tname = entry.get("tournament")

    # Entry has already settled
    if entry.get("settled"):
        return entry

    # Tournament still in progress for the same name -- not yet settleable
    if state_tname == entry_tname and not t.get("is_complete"):
        return entry

    # Different tournament now active or this one complete -- settle.
    # We can settle if we have a final field snapshot.
    field = state.get("field") or []
    if not field or state_tname != entry_tname:
        # Tournament has rolled over; we lost the final field. Mark UNRESOLVED.
        # In a real system we'd persist a copy. For now mark NOT_SETTLED.
        return entry

    bet_type = entry.get("type")
    player = entry.get("player")
    payout = _payout_units(entry.get("fair_american"))
    stake = 1.0

    if bet_type == "WIN":
        winner_pos = _final_position(field, player)
        hit = winner_pos == 1
    elif bet_type == "TOP5":
        pos = _final_position(field, player)
        hit = pos is not None and pos <= 5
    elif bet_type == "TOP10":
        pos = _final_position(field, player)
        hit = pos is not None and pos <= 10
    elif bet_type == "H2H":
        a_pos = _final_position(field, player)
        b_pos = _final_position(field, entry.get("opponent"))
        if a_pos is None or b_pos is None:
            return entry
        hit = a_pos < b_pos       # ties = push, not counted as hit here
    else:
        return entry

    entry.update({
        "settled": True,
        "outcome": "WIN" if hit else "LOSS",
        "pl_units": stake * (payout if hit else -1),
        "actual_result_summary": f"{player} finished #{_final_position(field, player)} of {len(field)}",
    })
    return entry


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    bestbet = _load(BESTBET_PATH)
    hist = _load(HIST_PATH).get("history") or []
    pot = bestbet.get("top_bet")
    today = dt.date.today().isoformat()
    tname = bestbet.get("tournament")

    # 1. Add today's POT if we have a new one for the active tournament
    if pot and tname:
        # Dedup: per (tournament, type, player, opponent)
        key = (tname, pot.get("type"), pot.get("player"), pot.get("opponent"))
        already = any((h.get("tournament"), h.get("type"), h.get("player"), h.get("opponent")) == key
                       and not h.get("settled") for h in hist)
        if not already:
            hist.append({
                "date": today,
                "tournament": tname,
                "type": pot.get("type"),
                "player": pot.get("player"),
                "opponent": pot.get("opponent"),
                "model_prob": pot.get("model_prob"),
                "fair_american": pot.get("fair_american"),
                "confidence": pot.get("confidence"),
                "reasoning": pot.get("reasoning"),
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    # 2. Re-settle pending entries
    for i, entry in enumerate(hist):
        if not entry.get("settled"):
            hist[i] = _settle_entry(entry, state)

    # 3. Aggregate stats
    settled = [h for h in hist if h.get("settled")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    net = sum(h.get("pl_units", 0) for h in settled)
    total_stake = len(settled)   # 1u stake

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "wins": wins,
        "losses": len(settled) - wins,
        "hit_rate": round(wins / len(settled), 4) if settled else None,
        "net_units": round(net, 2),
        "roi_pct": round((net / total_stake) * 100, 2) if total_stake else 0,
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {HIST_PATH}: {p['total_pots']} POTs ({p['n_settled']} settled, {p['n_pending']} pending)")
    if p["n_settled"]:
        print(f"  Hit rate: {(p['hit_rate'] or 0)*100:.1f}%  Net: {p['net_units']:+.2f}u  ROI: {p['roi_pct']:+.2f}%")
