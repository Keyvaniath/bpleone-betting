"""
EdgeStat -- calibration drift detector.

Compares today's calibration corrections to yesterday's (rolling git
history of data/calibration_live.json) and alerts when a correction
factor moves significantly. Drift can mean:
  - Genuine model improvement (residuals tightening as more data settles)
  - Genuine model degradation (a recent week was unusual; correction
    over-fits to a fluke)
  - Data quality issue (a market suddenly has way fewer settled records)

Writes data/drift.json:
  {
    "generated_at": "...",
    "vs_snapshot": {date or "previous"},
    "by_market": [
      {market, prev_cf, curr_cf, delta, prev_n, curr_n, n_delta, alert}
    ],
    "any_alert": bool
  }

`alert` triggers if:
  - |cf_delta| > 0.05 (correction moved >5%)
  - OR n shrank by > 20% (lost samples?)
  - OR a market vanished entirely
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")
DRIFT_PATH = os.path.join(DATA_DIR, "drift.json")
PREV_CAL_PATH = os.path.join(DATA_DIR, ".calibration_prev.json")


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    curr = _load(CAL_PATH)
    prev = _load(PREV_CAL_PATH)

    curr_markets = curr.get("markets") or {}
    prev_markets = prev.get("markets") or {}

    by_market: List[Dict[str, Any]] = []
    any_alert = False
    for mk in sorted(set(curr_markets) | set(prev_markets)):
        cm = curr_markets.get(mk) or {}
        pm = prev_markets.get(mk) or {}
        curr_cf = cm.get("correction_factor")
        prev_cf = pm.get("correction_factor")
        curr_n = cm.get("n", 0)
        prev_n = pm.get("n", 0)

        alerts: List[str] = []
        # New market
        if not pm and curr_n > 0:
            alerts.append("new market enrolled")
        # Market vanished
        if pm and not cm:
            alerts.append("market dropped from calibration -- check for upstream failure")
        # CF moved >5%
        if curr_cf is not None and prev_cf is not None:
            delta = curr_cf - prev_cf
            if abs(delta) > 0.05:
                alerts.append(f"correction moved {delta:+.3f}")
        # N shrank
        if prev_n > 10 and curr_n < prev_n * 0.8:
            alerts.append(f"sample count dropped from {prev_n} to {curr_n} (-{prev_n - curr_n})")

        rec = {
            "market": mk,
            "prev_cf": prev_cf,
            "curr_cf": curr_cf,
            "cf_delta": (round(curr_cf - prev_cf, 4) if (curr_cf is not None and prev_cf is not None) else None),
            "prev_n": prev_n,
            "curr_n": curr_n,
            "n_delta": curr_n - prev_n,
            "alert": "; ".join(alerts) if alerts else None,
        }
        if alerts:
            any_alert = True
        by_market.append(rec)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "vs_snapshot": prev.get("generated_at"),
        "by_market": by_market,
        "any_alert": any_alert,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DRIFT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    # Save the current calibration as previous for tomorrow's comparison.
    if curr:
        with open(PREV_CAL_PATH, "w") as f:
            json.dump(curr, f)

    return payload


if __name__ == "__main__":
    p = run()
    print(f"Drift check vs snapshot: {p.get('vs_snapshot')}")
    print(f"  any_alert: {p['any_alert']}")
    for m in p["by_market"]:
        if m["alert"]:
            print(f"  [!] {m['market']}: {m['alert']}")
        else:
            print(f"  [ok] {m['market']}: cf {m['prev_cf']} -> {m['curr_cf']} (n {m['prev_n']} -> {m['curr_n']})")
