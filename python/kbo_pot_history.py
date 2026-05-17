"""
EdgeStat -- KBO Play of the Day rolling history.
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "kbo_state.json")
BESTBET_PATH = os.path.join(DATA_DIR, "kbo_bestbet.json")
HIST_PATH = os.path.join(DATA_DIR, "kbo_pot_history.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _payout_units(american) -> float:
    if american is None: return 0
    return american / 100 if american >= 0 else 100 / abs(american)


def _settle(entry, state):
    if entry.get("settled"):
        return entry
    for m in (state.get("matches") or []):
        if m.get("state") != "post": continue
        teams = {m.get("home_team"), m.get("away_team")}
        if teams != {entry["team"], entry["opponent"]}:
            continue
        sh, sa = m.get("home_score") or 0, m.get("away_score") or 0
        if sh + sa == 0: return entry
        winner = m.get("home_team") if sh > sa else m.get("away_team") if sa > sh else None
        won = winner == entry["team"]
        payout = _payout_units(entry.get("fair_american"))
        entry.update({
            "settled": True,
            "outcome": "WIN" if won else "LOSS",
            "pl_units": 1.0 * (payout if won else -1),
            "actual_score": f"{sa}-{sh}",
            "actual_winner": winner,
        })
        return entry
    return entry


def run():
    state = _load(STATE_PATH)
    bestbet = _load(BESTBET_PATH)
    hist = _load(HIST_PATH).get("history") or []
    pot = bestbet.get("top_bet")
    today = dt.date.today().isoformat()
    if pot and pot.get("kind") == "ML":
        key = (pot.get("team"), pot.get("opponent"), pot.get("kind"))
        if not any((h.get("team"), h.get("opponent"), h.get("kind")) == key and not h.get("settled") for h in hist):
            hist.append({
                "date": today,
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
            hist[i] = _settle(e, state)
    settled = [h for h in hist if h.get("settled")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    net = sum(h.get("pl_units", 0) for h in settled)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "wins": wins,
        "losses": len(settled) - wins,
        "hit_rate": round(wins / len(settled), 4) if settled else None,
        "net_units": round(net, 2),
        "roi_pct": round(100 * net / len(settled), 2) if settled else 0,
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"KBO POD history: {p['total_pots']} total ({p['n_settled']} settled, {p['n_pending']} pending)")
