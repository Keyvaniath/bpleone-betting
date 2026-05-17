"""
EdgeStat -- League of Legends Play of the Tournament rolling history.

Snapshots each cron's lol_bestbet.top_bet into a rolling record. Auto-settles
when the underlying match completes (winner field becomes truthy in lol_state).

Output: data/lol_pot_history.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "lol_state.json")
BESTBET_PATH = os.path.join(DATA_DIR, "lol_bestbet.json")
HIST_PATH = os.path.join(DATA_DIR, "lol_pot_history.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _payout_units(american) -> float:
    if american is None: return 0
    return american / 100 if american >= 0 else 100 / abs(american)


def _find_match(state: Dict[str, Any], team_a: str, team_b: str) -> Dict[str, Any]:
    for m in (state.get("all_matches") or []):
        a, b = m.get("team_a"), m.get("team_b")
        if {a, b} == {team_a, team_b}:
            return m
    return {}


def _settle_entry(entry: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    if entry.get("settled"):
        return entry
    m = _find_match(state, entry["team"], entry["opponent"])
    if not m or not m.get("is_completed"):
        return entry
    kind = entry.get("kind", "ML")
    if kind == "ML":
        won = m.get("winner") == entry["team"]
    elif kind == "SWEEP":
        # Need the team to win every game in the series
        best_of = m.get("best_of") or 1
        target = (best_of + 1) // 2
        team_score = m.get("team_a_score") if m.get("team_a") == entry["team"] else m.get("team_b_score")
        opp_score = m.get("team_b_score") if m.get("team_a") == entry["team"] else m.get("team_a_score")
        won = (team_score == target) and (opp_score == 0)
    else:
        return entry
    payout = _payout_units(entry.get("fair_american"))
    stake = 1.0
    entry.update({
        "settled": True,
        "outcome": "WIN" if won else "LOSS",
        "pl_units": stake * (payout if won else -1),
        "actual_score": f"{m.get('team_a_score','?')}-{m.get('team_b_score','?')}",
        "actual_winner": m.get("winner"),
    })
    return entry


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    bestbet = _load(BESTBET_PATH)
    hist = _load(HIST_PATH).get("history") or []
    pot = bestbet.get("top_bet")
    today = dt.date.today().isoformat()

    if pot:
        key = (pot.get("team"), pot.get("opponent"), pot.get("kind"))
        already = any((h.get("team"), h.get("opponent"), h.get("kind")) == key
                       and not h.get("settled") for h in hist)
        if not already:
            hist.append({
                "date": today,
                "league": pot.get("league"),
                "best_of": pot.get("best_of"),
                "kind": pot.get("kind"),
                "team": pot.get("team"),
                "opponent": pot.get("opponent"),
                "prob": pot.get("prob"),
                "fair_american": pot.get("fair_american"),
                "confidence": pot.get("confidence"),
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    for i, e in enumerate(hist):
        if not e.get("settled"):
            hist[i] = _settle_entry(e, state)

    settled = [h for h in hist if h.get("settled")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    net = sum(h.get("pl_units", 0) for h in settled)
    stake = len(settled)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "wins": wins,
        "losses": len(settled) - wins,
        "hit_rate": round(wins / len(settled), 4) if settled else None,
        "net_units": round(net, 2),
        "roi_pct": round((net / stake) * 100, 2) if stake else 0,
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"LoL POT history: {p['total_pots']} total, {p['n_settled']} settled, {p['n_pending']} pending")
    if p["n_settled"]:
        print(f"  Hit rate: {(p['hit_rate'] or 0)*100:.1f}%  Net: {p['net_units']:+.2f}u  ROI: {p['roi_pct']:+.2f}%")
