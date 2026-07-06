"""
EdgeStat -- day-of-week P&L analysis, from the REAL settled ledger.

Slices the settled pick record by day of week (Mon - Sun) and per-market
by-day-of-week to surface performance patterns.

HONESTY NOTE: previously read the deprecated SYNTHETIC track_record.json
(118k backfilled props frozen 2026-06-02), which put absurd +40%-every-day
splits on the public track-record page. Now reads all_picks_ledger.json --
real graded picks, net from the ledger's recorded payout_units, 1u flat.

Output: data/dow_pl.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT_PATH = os.path.join(DATA_DIR, "dow_pl.json")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _net(p) -> float:
    pu = p.get("payout_units")
    if pu is not None:
        return float(pu)
    return 0.91 if p.get("result") == "won" else (-1.0 if p.get("result") == "lost" else 0.0)


def _agg(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [r for r in records if r.get("result") in ("won", "lost")]
    if not settled:
        return {"n": 0, "wins": 0, "hit_rate": None, "net_units": 0, "roi_pct": None}
    wins = sum(1 for r in settled if r["result"] == "won")
    net = sum(_net(r) for r in settled)
    return {
        "n": len(settled),
        "wins": wins, "losses": len(settled) - wins,
        "hit_rate": round(wins / len(settled), 3),
        "net_units": round(net, 2),
        "roi_pct": round(net / len(settled) * 100, 2),
    }


def run() -> Dict[str, Any]:
    led = _load(LEDGER)
    props = [p for p in (led.get("picks") or [])
             if p.get("settled") and p.get("result") in ("won", "lost")
             and not p.get("voided")]
    by_dow: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(7)}
    by_market_dow: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
    for r in props:
        d = r.get("date")
        if not d:
            continue
        try:
            dow = dt.date.fromisoformat(d).weekday()
        except Exception:
            continue
        by_dow[dow].append(r)
        m = r.get("market") or "?"
        by_market_dow.setdefault(m, {i: [] for i in range(7)})
        by_market_dow[m][dow].append(r)

    dow_out = []
    for i in range(7):
        a = _agg(by_dow[i])
        dow_out.append({"dow": DAY_NAMES[i], "dow_idx": i, **a})

    # Per-market x per-dow grid (only markets with 30+ total samples)
    market_dow_grid = []
    for market, days in by_market_dow.items():
        total = sum(len(records) for records in days.values())
        if total < 30:
            continue
        row = {"market": market, "total": total, "by_dow": {}}
        for i in range(7):
            a = _agg(days[i])
            row["by_dow"][DAY_NAMES[i]] = a
        market_dow_grid.append(row)
    market_dow_grid.sort(key=lambda r: -r["total"])

    # Find best/worst day
    valid_days = [d for d in dow_out if d["n"] >= 10]
    best_day = max(valid_days, key=lambda d: d["roi_pct"] or -1e9) if valid_days else None
    worst_day = min(valid_days, key=lambda d: d["roi_pct"] or 1e9) if valid_days else None

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_settled": sum(d["n"] for d in dow_out),
        "by_day": dow_out,
        "by_market_dow": market_dow_grid[:12],
        "best_day": best_day,
        "worst_day": worst_day,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_settled']} settled props by day-of-week")
    if p["best_day"]:
        print(f"  Best day:  {p['best_day']['dow']} -- {p['best_day']['n']} bets, "
                f"{(p['best_day']['hit_rate'] or 0)*100:.1f}% hit, ROI {p['best_day']['roi_pct']}%")
    if p["worst_day"]:
        print(f"  Worst day: {p['worst_day']['dow']} -- {p['worst_day']['n']} bets, "
                f"{(p['worst_day']['hit_rate'] or 0)*100:.1f}% hit, ROI {p['worst_day']['roi_pct']}%")
    print("  Full week:")
    for d in p["by_day"]:
        if d["n"] >= 5:
            print(f"    {d['dow']:4} n={d['n']:5} hit={(d.get('hit_rate') or 0)*100:5.1f}% ROI={d.get('roi_pct')}%")
