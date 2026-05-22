"""
EdgeStat -- MLB Today's Whales (ultra-high-conviction picks).

The 'whale' tier of picks: anything with 4+ independent STRONG signals on
the same player AND consistent direction. These are the bet-the-house
plays of the slate.

Method:
  Reads cross_sport_alpha_scanner.confluence_triples (which finds 3+
  signals). Filters to:
    - 4+ signals (not just 3)
    - All in same direction (no mixed OVER/UNDER)
    - p between 35% and 78% (value zone, no heavy chalk)

Output: data/mlb_today_whales.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_whales.json")


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
    """Extract OVER/UNDER/YES/NO from market name."""
    m = (market or "").upper()
    if "OVER" in m or "YES" in m or "_PLUS" in m: return "OVER"
    if "UNDER" in m or "_NO_" in m or m.endswith("_NO"): return "UNDER"
    return "?"


def run() -> Dict[str, Any]:
    scanner = _load(os.path.join(DATA_DIR, "cross_sport_alpha_scanner.json"))
    triples = scanner.get("confluence_triples") or []

    whales: List[Dict[str, Any]] = []
    for t in triples:
        signals = t.get("signals") or []
        if len(signals) < 4: continue

        # Check direction alignment
        directions = [_detect_direction(s.get("market", "")) for s in signals]
        primary = max(set(directions), key=directions.count)
        n_agree = directions.count(primary)
        if n_agree < len(signals) - 1: continue  # require all-but-1 agree

        # Value zone: avg p between 0.35 and 0.78
        avg_p = sum(_safe(s.get("p")) for s in signals) / max(len(signals), 1)
        if avg_p < 0.35 or avg_p > 0.78: continue

        whales.append({
            "player": t.get("player"),
            "matchup": t.get("matchup"),
            "n_signals": len(signals),
            "n_agreeing_direction": n_agree,
            "primary_direction": primary,
            "avg_probability": round(avg_p, 3),
            "signals": signals,
        })

    whales.sort(key=lambda w: -w["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_whales": len(whales),
        "method_note": "Ultra-high-conviction picks: 4+ STRONG signals on same "
                       "player from cross_sport_alpha_scanner. Requires "
                       "directional alignment (all-but-1 agreeing) AND avg "
                       "probability in [0.35, 0.78] value zone.",
        "whales": whales,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[whales] {o['n_whales']} whales identified -> {OUT}")
