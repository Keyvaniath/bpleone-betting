"""
EdgeStat -- MLB Today's Locks.

Surfaces the day's HIGHEST-CONFIDENCE picks — what real bettors call "locks"
or "single-leg whales". Requires:
  - probability >= 80% (heavy chalk side)
  - 3+ confirming signals
  - directional agreement across all signals (no contradictions)

These aren't necessarily the best EV bets (chalk has lower EV), but they're
the safest single-leg plays — useful for SGP anchors, parlays, and "money in
the bank" picks for new bettors.

Output: data/mlb_today_locks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_locks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _detect_direction(market: str) -> str:
    m = (market or "").upper()
    if "OVER" in m or "YES" in m or "_PLUS" in m: return "OVER"
    if "UNDER" in m or "_NO_" in m or m.endswith("_NO"): return "UNDER"
    return "?"


def run() -> Dict[str, Any]:
    scanner = _load(os.path.join(DATA_DIR, "cross_sport_alpha_scanner.json"))
    triples = scanner.get("confluence_triples") or []

    locks: List[Dict[str, Any]] = []
    for t in triples:
        signals = t.get("signals") or []
        if len(signals) < 3: continue

        # Direction alignment
        directions = [_detect_direction(s.get("market", "")) for s in signals]
        # Filter to known directions
        known_dirs = [d for d in directions if d != "?"]
        if not known_dirs: continue
        primary = max(set(known_dirs), key=known_dirs.count)
        n_agree = known_dirs.count(primary)
        if n_agree < len(known_dirs): continue  # require ALL agree (no exceptions)

        # Probability filter: ≥ 0.80 average (lock-tier)
        ps = [_safe(s.get("p")) for s in signals if s.get("p") is not None]
        if not ps: continue
        avg_p = sum(ps) / len(ps)
        if avg_p < 0.80: continue

        # Add to locks
        locks.append({
            "player": t.get("player"),
            "matchup": t.get("matchup"),
            "category": "LOCK",
            "primary_direction": primary,
            "n_signals": len(signals),
            "avg_probability": round(avg_p, 3),
            "signals": signals,
        })

    locks.sort(key=lambda l: -l["avg_probability"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_locks": len(locks),
        "method_note": "LOCK criteria: 3+ confirming signals + 100% directional "
                       "alignment + avg probability >= 80%. Safest single-leg "
                       "plays of the slate — chalk by design, low EV but high "
                       "hit rate. Useful for SGP anchors + parlay legs.",
        "locks": locks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[locks] {o['n_locks']} locks identified -> {OUT}")
    for l in o['locks'][:5]:
        print(f"  · {l['player']:25s} ({l['matchup']:18s}) {l['primary_direction']} "
              f"avg_p={l['avg_probability']*100:.0f}% across {l['n_signals']} signals")
