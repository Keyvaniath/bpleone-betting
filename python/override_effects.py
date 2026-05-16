"""
EdgeStat -- override effect tracker.

Closes the self-tuning loop. For every entry in config_history.json, measures
the model's performance BEFORE the override took effect vs AFTER, and assigns
a verdict: improved / flat / degraded.

This is the "did the tweak actually help?" empirical answer. The recommender
proposes, the operator (or model) applies, and this module measures whether
the change moved Brier / hit rate / ROI in the right direction.

Approach:
  1. Read config_history.json (each entry has ts + key + old + new)
  2. For each override-change entry, determine the eval window:
       - pre_start  = ts - 7 days
       - pre_end    = ts
       - post_start = ts
       - post_end   = min(ts + 7 days, next change to SAME key, today)
  3. Compute pre/post Brier from track_record.json (props within window)
  4. Compute pre/post hit rate
  5. Assign verdict:
       - improved if Brier dropped >= 0.005 OR hit_rate climbed >= 1pp
       - degraded if Brier rose   >= 0.005 OR hit_rate dropped >= 1pp
       - flat    otherwise
  6. Apply ONLY to entries with at least 50 records in each window (else
     mark "insufficient_data" so we don't draw conclusions from noise)

Output: data/override_effects.json
  {
    "generated_at": "...",
    "n_changes_analyzed": 3,
    "changes": [
      {
        "ts": "2026-05-10T10:00:00", "key": "calibration.n_prior_default",
        "old": 8, "new": 5,
        "window_days": 7,
        "pre":  {"brier": 0.21, "hit_rate": 0.54, "n": 1200},
        "post": {"brier": 0.19, "hit_rate": 0.56, "n": 1180},
        "brier_delta": -0.02, "hit_rate_delta": 0.02,
        "verdict": "improved",
        "verdict_color": "good"
      }
    ]
  }

/config.html surfaces this so the operator sees the empirical result of
each tweak right next to the history entry that caused it.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HIST_PATH = os.path.join(DATA_DIR, "config_history.json")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "override_effects.json")

WINDOW_DAYS = 7
MIN_RECORDS = 50
BRIER_IMPROVE_THRESH = 0.005
HIT_RATE_IMPROVE_THRESH = 0.01


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


def _record_ts(r: Dict[str, Any]) -> Optional[dt.datetime]:
    """Best-effort to get a settled-on datetime from a track_record prop entry."""
    for k in ("settled_at", "date", "ts"):
        v = r.get(k)
        if not v:
            continue
        try:
            if "T" in v:
                return dt.datetime.fromisoformat(v.replace("Z", ""))
            return dt.datetime.fromisoformat(v + "T23:59:59")
        except Exception:
            continue
    return None


def _window_metrics(records: List[Dict[str, Any]],
                    start: dt.datetime, end: dt.datetime) -> Dict[str, Any]:
    valid = []
    for r in records:
        t = _record_ts(r)
        if not t or t < start or t >= end:
            continue
        if r.get("model_prob_over") is None or r.get("over_hit") is None:
            continue
        valid.append(r)
    if len(valid) < MIN_RECORDS:
        return {"n": len(valid), "insufficient": True}
    brier_sum = 0.0
    hits = 0
    for r in valid:
        p = max(0.001, min(0.999, float(r["model_prob_over"])))
        y = 1 if r["over_hit"] else 0
        brier_sum += (p - y) ** 2
        side = "OVER" if p >= 0.5 else "UNDER"
        if (side == "OVER" and y == 1) or (side == "UNDER" and y == 0):
            hits += 1
    return {
        "n": len(valid),
        "brier": round(brier_sum / len(valid), 4),
        "hit_rate": round(hits / len(valid), 4),
        "insufficient": False,
    }


def run() -> Dict[str, Any]:
    hist = _load(HIST_PATH)
    tr = _load(TR_PATH)
    entries: List[Dict[str, Any]] = hist.get("entries") or []
    props: List[Dict[str, Any]] = tr.get("props") or []
    now = dt.datetime.now()

    # Pre-index: for each key, the sorted list of all change timestamps
    by_key_ts: Dict[str, List[dt.datetime]] = {}
    for e in entries:
        t = _parse_ts(e.get("ts"))
        if not t:
            continue
        by_key_ts.setdefault(e["key"], []).append(t)
    for k in by_key_ts:
        by_key_ts[k].sort()

    changes: List[Dict[str, Any]] = []
    for e in entries:
        t = _parse_ts(e.get("ts"))
        if not t:
            continue
        key = e["key"]
        # Determine post window end = min(now, t + WINDOW_DAYS, next change ts for same key)
        post_end = t + dt.timedelta(days=WINDOW_DAYS)
        # Look for next change in same key after this one
        ts_for_key = by_key_ts.get(key, [])
        next_change = None
        for tk in ts_for_key:
            if tk > t:
                next_change = tk
                break
        if next_change is not None and next_change < post_end:
            post_end = next_change
        if post_end > now:
            post_end = now

        pre_start = t - dt.timedelta(days=WINDOW_DAYS)
        pre = _window_metrics(props, pre_start, t)
        post = _window_metrics(props, t, post_end)

        # Determine verdict
        if pre.get("insufficient") or post.get("insufficient"):
            verdict, color, delta_b, delta_h = "insufficient_data", "muted", None, None
        else:
            delta_b = round(post["brier"] - pre["brier"], 4)  # negative = better
            delta_h = round(post["hit_rate"] - pre["hit_rate"], 4)  # positive = better
            improved = (delta_b <= -BRIER_IMPROVE_THRESH) or (delta_h >= HIT_RATE_IMPROVE_THRESH)
            degraded = (delta_b >= BRIER_IMPROVE_THRESH) or (delta_h <= -HIT_RATE_IMPROVE_THRESH)
            if improved and not degraded:
                verdict, color = "improved", "good"
            elif degraded and not improved:
                verdict, color = "degraded", "bad"
            else:
                verdict, color = "flat", "neutral"

        changes.append({
            "ts": e["ts"],
            "key": key,
            "type": e.get("type"),
            "old": e.get("old"),
            "new": e.get("new"),
            "window_days": WINDOW_DAYS,
            "pre": pre,
            "post": post,
            "brier_delta": delta_b,
            "hit_rate_delta": delta_h,
            "verdict": verdict,
            "verdict_color": color,
            "post_window_end": post_end.isoformat(timespec="seconds"),
        })

    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "min_records": MIN_RECORDS,
        "n_changes_analyzed": len(changes),
        "changes": changes[-50:],  # last 50
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_changes_analyzed']} change(s) analyzed")
    for c in p["changes"][-5:]:
        b = c.get("brier_delta")
        h = c.get("hit_rate_delta")
        b_str = f"{'+' if (b is not None and b >= 0) else ''}{b}" if b is not None else "n/a"
        h_str = f"{'+' if (h is not None and h >= 0) else ''}{h}" if h is not None else "n/a"
        print(f"  {c['ts']} {c['key']} ({c.get('old')} -> {c.get('new')}): "
              f"dBrier {b_str} dHitRate {h_str} -> {c['verdict']}")
