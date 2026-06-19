"""
EdgeStat -- TENNIS Play of the Day history + settlement.

The tennis desk prices surface-adjusted match-win edges (tennis_match_win_props)
but nothing settled, so it never tracked a record. This snapshots the day's single
best STRONG match-win edge and settles it from tennis_results.json -- the ESPN
finals feed already pulled by espn_event_results (p1/p2/winner per completed
match). Flat 1u per pick, exactly what was modeled.

Output: data/tennis_pot_history.json  (sport_coverage reads this -> Tennis shows a
real settled record instead of "no outcome feed yet").
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MW_PATH = os.path.join(DATA_DIR, "tennis_match_win_props.json")
RESULTS_PATH = os.path.join(DATA_DIR, "tennis_results.json")
HIST_PATH = os.path.join(DATA_DIR, "tennis_pot_history.json")
MAX_HISTORY = 400


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _norm(n) -> str:
    return " ".join(str(n or "").lower().split())


def _payout_units(american) -> float:
    try:
        american = int(american)
    except (TypeError, ValueError):
        return 0.91
    return american / 100 if american >= 0 else 100 / abs(american)


def _best_pick(mw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The day's single highest-conviction STRONG match-win edge (favored side)."""
    strong = [r for r in (mw.get("rows") or [])
              if str(r.get("edge_class") or "").startswith("STRONG")
              and r.get("p_p1_wins") is not None and r.get("p_p2_wins") is not None]
    if not strong:
        return None
    strong.sort(key=lambda r: -max(r["p_p1_wins"], r["p_p2_wins"]))
    r = strong[0]
    a_fav = r["p_p1_wins"] >= r["p_p2_wins"]
    return {
        "player": r["p1"] if a_fav else r["p2"],
        "opponent": r["p2"] if a_fav else r["p1"],
        "prob": round(max(r["p_p1_wins"], r["p_p2_wins"]), 3),
        "fair_american": r["fair_p1_odds"] if a_fav else r["fair_p2_odds"],
        "surface": r.get("surface"),
    }


def _find_result(entry: Dict[str, Any], results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The completed match for this pick: same two players, within +/-4 days of the
    pick date (a slate match may be played the same or next day)."""
    teams = {_norm(entry.get("player")), _norm(entry.get("opponent"))}
    if "" in teams:
        return None
    try:
        bd = dt.date.fromisoformat(str(entry.get("date"))[:10])
    except Exception:
        bd = None
    for m in results:
        if {_norm(m.get("p1")), _norm(m.get("p2"))} != teams:
            continue
        if bd is not None:
            try:
                md = dt.date.fromisoformat(str(m.get("date"))[:10])
                if abs((md - bd).days) > 4:
                    continue
            except Exception:
                pass
        return m
    return None


def _settle(entry: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if entry.get("settled"):
        return entry
    m = _find_result(entry, results)
    if not m:
        return entry
    winner = _norm(m.get("winner") or m.get("winner_name"))
    if not winner:
        return entry
    won = winner == _norm(entry.get("player"))
    payout = _payout_units(entry.get("fair_american"))
    entry.update({
        "settled": True,
        "outcome": "WIN" if won else "LOSS",
        "pl_units": round(payout if won else -1.0, 3),
        "actual_winner": m.get("winner_name") or m.get("winner"),
        "actual_score": m.get("sets"),
        "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
    })
    return entry


def run() -> Dict[str, Any]:
    mw = _load(MW_PATH)
    results = _load(RESULTS_PATH).get("matches") or []
    hist: List[Dict[str, Any]] = _load(HIST_PATH).get("history") or []
    today = dt.date.today().isoformat()

    pick = _best_pick(mw)
    if pick:
        key = (today, _norm(pick["player"]), _norm(pick["opponent"]))
        if not any((h.get("date"), _norm(h.get("player")), _norm(h.get("opponent"))) == key
                   for h in hist):
            hist.append({
                "date": today,
                "kind": "ML",
                "player": pick["player"],
                "opponent": pick["opponent"],
                "surface": pick.get("surface"),
                "prob": pick.get("prob"),
                "fair_american": pick.get("fair_american"),
                "label": f'{pick["player"]} ML vs {pick["opponent"]}',
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    n_before = sum(1 for h in hist if h.get("settled"))
    for i, e in enumerate(hist):
        if not e.get("settled"):
            hist[i] = _settle(e, results)
    hist = hist[-MAX_HISTORY:]

    # Void picks too old to ever settle (no matchable final) so they don't linger
    # as "pending" forever.
    today_d = dt.date.today()
    for e in hist:
        if e.get("settled") or e.get("voided"):
            continue
        try:
            ed = dt.date.fromisoformat(str(e.get("date"))[:10])
        except Exception:
            ed = None
        if ed is not None and (today_d - ed).days > 7:
            e.update(voided=True, outcome="VOID", void_reason="no final matched within 7 days")

    settled = [h for h in hist if h.get("settled")]
    pending = [h for h in hist if not h.get("settled") and not h.get("voided")]
    voided = [h for h in hist if h.get("voided")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    losses = sum(1 for h in settled if h.get("outcome") == "LOSS")
    net = round(sum(h.get("pl_units", 0) for h in settled), 2)
    decided = wins + losses

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": "Tennis",
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_voided": len(voided),
        "n_settled_this_run": len(settled) - n_before,
        "wins": wins, "losses": losses,
        "record": f"{wins}-{losses}" if decided else None,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(100 * net / decided, 2) if decided else None,
        "stake_assumption": "1u flat per POD (best STRONG match-win edge), settled off ESPN tennis finals",
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[tennis-history] {p['total_pots']} picks, {p['n_settled']} settled, {p['n_pending']} pending "
          f"(+{p['n_settled_this_run']} this run)")
    if p["record"]:
        print(f"  Record {p['record']} net {p['net_units']:+.2f}u "
              f"ROI {p['roi_pct'] if p['roi_pct'] is not None else 0:+.1f}%")
    for h in p["history"][:6]:
        print(f"    {h['date']} {str(h.get('label',''))[:40]:40s} -> {h['outcome']}")
