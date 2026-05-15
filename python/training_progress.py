"""
EdgeStat -- training progress + ETA projection.

Tells the operator "when will market X have enough samples to be fully
trained?". For each market, projects:
  - Current settled-record count
  - Daily settlement rate (last 14 days)
  - Days until 200 / 500 / 1000 settled records (the practical milestones
    at which calibration goes from noisy -> directional -> tight -> stable)
  - Bayesian data-weight at the next milestone vs today (what does crossing
    the threshold actually do to the correction?)
  - "Training stage": embryonic / learning / directional / tight / stable

The point: turn the abstract "the model is training" into concrete dates.
"batter_doubles hits the 500-record stable threshold on June 4" is something
the operator can plan around.

Output: data/training_progress.json
  {
    "generated_at": "...",
    "milestones": [200, 500, 1000],
    "by_market": [
      {
        "market": "batter_total_bases",
        "n_settled": 14292,
        "daily_rate": 410,
        "stage": "stable",
        "eta_to_next_milestone": null,    # already past all
        "weight_now": 0.998,
        "weight_at_next_milestone": null
      },
      {
        "market": "pitcher_strikeouts",
        "n_settled": 2880,
        "daily_rate": 82,
        "stage": "stable",
        "eta_to_next_milestone": null,
        ...
      }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")
OUT_PATH = os.path.join(DATA_DIR, "training_progress.json")

MILESTONES = [200, 500, 1000]

try:
    import config as _cfg
    N_PRIOR_DEFAULT = _cfg.get("calibration.n_prior_default", 8)
    N_PRIOR_PER_MARKET = _cfg.get("calibration.n_prior_per_market", {}) or {}
except Exception:
    N_PRIOR_DEFAULT = 8
    N_PRIOR_PER_MARKET = {}


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _date_of(r: Dict[str, Any]) -> Optional[dt.date]:
    s = r.get("date")
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def _stage(n: int) -> str:
    if n < 50:   return "embryonic"
    if n < 200:  return "learning"
    if n < 500:  return "directional"
    if n < 1000: return "tight"
    return "stable"


def _weight(n: int, n_prior: int) -> float:
    """Bayesian data weight: n / (n + N_PRIOR). 0.5 at n=N_PRIOR; 0.99 at n=99*N_PRIOR."""
    return round(n / (n + n_prior), 4) if n + n_prior > 0 else 0.0


def run() -> Dict[str, Any]:
    tr = _load(TR_PATH)
    cal = _load(CAL_PATH)
    props = tr.get("props", []) or []
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=14)

    # Group by market: total count + records in last 14 days
    by_market_total: Dict[str, int] = {}
    by_market_recent: Dict[str, int] = {}
    for r in props:
        m = r.get("market")
        if not m:
            continue
        by_market_total[m] = by_market_total.get(m, 0) + 1
        d = _date_of(r)
        if d and d >= cutoff:
            by_market_recent[m] = by_market_recent.get(m, 0) + 1

    rows: List[Dict[str, Any]] = []
    for market in sorted(by_market_total.keys()):
        n = by_market_total[market]
        recent_n = by_market_recent.get(market, 0)
        daily_rate = round(recent_n / 14, 1) if recent_n > 0 else 0.0
        n_prior = N_PRIOR_PER_MARKET.get(market, N_PRIOR_DEFAULT)
        weight_now = _weight(n, n_prior)
        # Find the next unachieved milestone
        next_milestone = next((m for m in MILESTONES if m > n), None)
        if next_milestone is None or daily_rate <= 0:
            eta_days = None
            eta_date = None
            weight_at_next = None
        else:
            eta_days = max(0, (next_milestone - n) / daily_rate)
            eta_date = (today + dt.timedelta(days=int(eta_days))).isoformat()
            weight_at_next = _weight(next_milestone, n_prior)
        rows.append({
            "market": market,
            "n_settled": n,
            "n_last_14d": recent_n,
            "daily_rate": daily_rate,
            "n_prior": n_prior,
            "weight_now": weight_now,
            "stage": _stage(n),
            "next_milestone": next_milestone,
            "eta_days": round(eta_days, 1) if eta_days is not None else None,
            "eta_date": eta_date,
            "weight_at_next_milestone": weight_at_next,
        })

    # Sort by n_settled descending for the UI
    rows.sort(key=lambda r: -r["n_settled"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "milestones": MILESTONES,
        "rate_window_days": 14,
        "by_market": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {len(p['by_market'])} markets")
    for r in p["by_market"][:10]:
        eta = f"+{r['eta_days']}d ({r['eta_date']})" if r["eta_days"] is not None else "(stable)"
        print(f"  {r['market']:25} n={r['n_settled']:6} rate={r['daily_rate']:5.1f}/d "
              f"stage={r['stage']:11} next={r['next_milestone']} {eta}")
