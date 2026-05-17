"""
EdgeStat -- Play of the Day historical record.

Every daily cron snapshots today.json.play_of_day into a rolling history.
On subsequent runs, we settle prior PODs against game outcomes from
track_record/outcomes pipeline and compute cumulative ROI on JUST the POD.

This is the historical track record of the flagship pick: hit rate, ROI,
average edge, beat-the-close rate. Surfaces on /pod-history.

Output: data/pod_history.json
  {
    "generated_at": "...",
    "total_pods": 42,
    "n_settled": 38, "n_pending": 4,
    "hit_rate": 0.605, "roi_pct": 6.8, "net_units": +2.58,
    "avg_edge_pct": 4.9, "avg_kelly_units": 1.1,
    "history": [
      { date, matchup, play, model_price, market_price, edge_pct,
        kelly_units, model_prob, settled (true/false), outcome (WIN/LOSS/PENDING),
        actual_result_summary }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
HIST_PATH = os.path.join(DATA_DIR, "pod_history.json")


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


def _settle_game_pod(entry: Dict[str, Any], tr: Dict[str, Any]) -> Dict[str, Any]:
    """Look in track_record.games for the matchup on this date. Return
    settled outcome dict or {} if not yet settled."""
    games = tr.get("games") or []
    for g in games:
        if g.get("date") == entry.get("date") and g.get("matchup") == entry.get("matchup"):
            # Check what side we picked
            play = entry.get("play", "")
            # POD label might be "LAD ML", "Yankees ML", "OVER 8.5", etc.
            # Match on play_hit if game record has it
            if g.get("play_hit") is not None:
                hit = g["play_hit"]
                payout = _payout_units(entry.get("market_price"))
                return {
                    "settled": True,
                    "outcome": "WIN" if hit else "LOSS",
                    "stake_units": entry.get("kelly_units", 1.0),
                    "pl_units": entry.get("kelly_units", 1.0) * (payout if hit else -1),
                    "actual_result_summary": f"Final: {g.get('home_runs','?')}-{g.get('away_runs','?')}",
                }
    return {"settled": False, "outcome": "PENDING"}


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    tr = _load(TR_PATH)
    hist = _load(HIST_PATH).get("history") or []
    today_pod = today.get("play_of_day")
    today_date = (today.get("generated_at") or dt.date.today().isoformat())[:10]

    # 1. Add today's POD if not already in history
    if today_pod:
        already = any(h.get("date") == today_date and h.get("matchup") == today_pod.get("matchup")
                       and h.get("label") == today_pod.get("label") for h in hist)
        if not already:
            hist.append({
                "date": today_date,
                "matchup": today_pod.get("matchup"),
                "label": today_pod.get("label"),
                "play": today_pod.get("play"),
                "model_price": today_pod.get("model_price"),
                "market_price": today_pod.get("market_price"),
                "edge_pct": today_pod.get("edge_pct"),
                "kelly_units": today_pod.get("kelly_units"),
                "model_prob": today_pod.get("model_prob"),
                "confidence": today_pod.get("confidence"),
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    # 2. Re-settle any pending PODs
    for entry in hist:
        if entry.get("settled"):
            continue
        result = _settle_game_pod(entry, tr)
        if result.get("settled"):
            entry.update(result)

    # 3. Compute aggregate stats from settled
    settled = [h for h in hist if h.get("settled")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    net = sum(h.get("pl_units", 0) for h in settled)
    avg_edge = (sum(h.get("edge_pct", 0) for h in hist) / len(hist)) if hist else 0
    avg_kelly = (sum(h.get("kelly_units", 0) for h in hist) / len(hist)) if hist else 0
    total_stake = sum(h.get("kelly_units", 1.0) for h in settled)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_pods": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "wins": wins,
        "losses": len(settled) - wins,
        "hit_rate": round(wins / len(settled), 4) if settled else None,
        "net_units": round(net, 2),
        "roi_pct": round((net / total_stake) * 100, 2) if total_stake else 0,
        "avg_edge_pct": round(avg_edge, 2),
        "avg_kelly_units": round(avg_kelly, 2),
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {HIST_PATH}: {p['total_pods']} PODs ({p['n_settled']} settled, {p['n_pending']} pending)")
    if p["n_settled"]:
        print(f"  Hit rate: {(p['hit_rate'] or 0)*100:.1f}%  Net: {p['net_units']:+.2f}u  ROI: {p['roi_pct']:+.2f}%")
    print(f"  Avg edge: +{p['avg_edge_pct']}%  Avg Kelly: {p['avg_kelly_units']}u")
