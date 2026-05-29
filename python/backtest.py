"""
EdgeStat -- REAL track-record backtest from the settled-picks ledger.

NO SYNTHETIC DATA. Every number here derives from data/all_picks_ledger.json,
which records actual recommended picks and their graded outcomes. This module
replaces the old synthetic-season generator (which fabricated a fake 62.75% /
+26% ROI track record) -- a hard violation of "no fake numbers".

It emits data/backtest.json consumed by backtest.html / backtest-dashboard.html:
  - metrics:    real hit%, ROI, net units, drawdown, Sharpe (1u flat stake)
  - bankroll_path / drawdown_path: cumulative units P&L over settled picks,
    chronological (no look-ahead -- this is just the realized record)
  - by_source:  per-source W/L/ROI so the blended number is decomposable
                (the edge concentrates in a few sharp sources)
  - recent_bets: the most recent real settled picks

Staking model: 1 unit flat per pick at the model's fair price (matches the
ledger's own net_units accounting; sum(payout_units) reconciles to net_units
exactly). Pushes return the stake (0 P&L).
"""
from __future__ import annotations

import os
import json
import math
import statistics
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "backtest.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _result_class(r: str) -> str:
    r = (r or "").lower()
    if r in ("won", "win"):
        return "WIN"
    if r in ("lost", "loss"):
        return "LOSS"
    return "PUSH"


def run() -> Dict[str, Any]:
    ledger = _load(LEDGER)
    picks = [p for p in (ledger.get("picks") or []) if p.get("settled")]
    # Chronological order -- realized track record, no look-ahead.
    picks.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))

    cum = 0.0
    peak = 0.0
    bankroll_path: List[float] = [0.0]   # cumulative units P&L, starts at 0
    drawdown_path: List[float] = [0.0]
    pls: List[float] = []
    wins = losses = pushes = 0

    for p in picks:
        u = float(p.get("payout_units") or 0.0)
        pls.append(u)
        cum += u
        peak = max(peak, cum)
        bankroll_path.append(round(cum, 3))
        drawdown_path.append(round(peak - cum, 3))
        cls = _result_class(p.get("result"))
        if cls == "WIN":
            wins += 1
        elif cls == "LOSS":
            losses += 1
        else:
            pushes += 1

    graded = wins + losses               # pushes excluded from hit% / ROI denom
    net = round(cum, 2)
    metrics = {
        "n_plays": len(picks),
        "hit_pct": round(wins / graded * 100, 2) if graded else 0.0,
        "roi_pct": round(net / graded * 100, 2) if graded else 0.0,
        "avg_clv_pct": None,             # per-pick CLV not yet attached (honest --)
        "total_units": net,
        "max_drawdown": round(max(drawdown_path), 2) if drawdown_path else 0.0,
        "sharpe_per_n": (round((statistics.mean(pls) / (statistics.pstdev(pls) or 1.0))
                               * math.sqrt(len(pls)), 2) if len(pls) > 1 else 0.0),
        "best_play": round(max(pls), 2) if pls else 0.0,
        "worst_play": round(min(pls), 2) if pls else 0.0,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "date_range": [picks[0].get("date"), picks[-1].get("date")] if picks else None,
    }

    # Per-source decomposition (real, straight from the ledger), best ROI first.
    by_source = ledger.get("by_source") or {}
    src_rows = sorted(
        [{"source": s, **v} for s, v in by_source.items() if isinstance(v, dict)],
        key=lambda r: -(r.get("net_units") or 0.0),
    )

    recent_bets = [{
        "day": p.get("date"),
        "matchup": p.get("player_or_matchup") or p.get("market") or "?",
        "side": p.get("market") or "",
        "source": p.get("source"),
        "stake": 1.0,
        "price": p.get("fair_american"),
        "edge": p.get("edge_pct"),
        "result": _result_class(p.get("result")),
        "pl": round(float(p.get("payout_units") or 0.0), 3),
        "clv": None,
    } for p in picks[-50:][::-1]]

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "is_real": True,
        "source_note": ("Real track record from data/all_picks_ledger.json -- "
                        "actual recommended picks, graded outcomes, 1u flat stake "
                        "at model fair price. No synthetic data."),
        "stake_assumption": "1u flat per pick",
        "metrics": metrics,
        "bankroll_path": bankroll_path,      # cumulative units P&L (from 0)
        "drawdown_path": drawdown_path,
        "by_source": src_rows,
        "recent_bets": recent_bets,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    m = p["metrics"]
    print(f"REAL backtest from {m['n_plays']} settled picks "
          f"({m['date_range']}): {m['wins']}-{m['losses']}-{m['pushes']}, "
          f"hit {m['hit_pct']}%, ROI {m['roi_pct']}%, net {m['total_units']}u, "
          f"maxDD {m['max_drawdown']}u")
    print(f"  top sources: " + ", ".join(
        f"{r['source']} {r.get('net_units', 0):+.1f}u" for r in p["by_source"][:4]))
