"""
EdgeStat -- config override audit log.

Runs at the START of every cron. Diffs data/runtime_config.json against the
last seen snapshot. If anything changed (operator applied a recommendation,
or hand-tweaked a knob), append an audit entry with what changed.

This is the "did we change something?" half of the closed loop. The other
half is "did it help?" -- correlate audit entries with training_feedback
to see whether overrides actually improved the model.

Output: data/config_history.json
  {
    "generated_at": "...",
    "current_config_hash": "abc123",
    "entries": [
      {
        "ts": "2026-05-16T10:00:00",
        "type": "override_added",      // or override_changed, override_removed
        "key": "calibration.n_prior_default",
        "old": null,                    // null when type=override_added
        "new": 12,
        "source": "operator"            // future: "recommendation_apply" if we add that
      }
    ]
  }

/config.html reads this and renders a "Override History" card below the
recommendations.
"""
from __future__ import annotations

import os
import json
import hashlib
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OVERRIDES_PATH = os.path.join(DATA_DIR, "runtime_config.json")
HIST_PATH = os.path.join(DATA_DIR, "config_history.json")
LAST_SNAP_PATH = os.path.join(DATA_DIR, ".last_runtime_config.json")

MAX_HISTORY = 200


def _load(p: str) -> Any:
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _hash_obj(obj: Dict[str, Any]) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _diff(prev: Dict[str, Any], curr: Dict[str, Any]) -> List[Dict[str, Any]]:
    prev = prev or {}
    curr = curr or {}
    out = []
    prev_keys = set(prev.keys())
    curr_keys = set(curr.keys())
    for k in curr_keys - prev_keys:
        out.append({"type": "override_added", "key": k, "old": None, "new": curr[k]})
    for k in prev_keys - curr_keys:
        out.append({"type": "override_removed", "key": k, "old": prev[k], "new": None})
    for k in prev_keys & curr_keys:
        if prev[k] != curr[k]:
            out.append({"type": "override_changed", "key": k, "old": prev[k], "new": curr[k]})
    return out


def run() -> Dict[str, Any]:
    curr = _load(OVERRIDES_PATH) or {}
    prev = _load(LAST_SNAP_PATH)  # may be None on first run
    curr_hash = _hash_obj(curr)

    existing = _load(HIST_PATH) or {}
    entries: List[Dict[str, Any]] = existing.get("entries") or []

    now = dt.datetime.now().isoformat(timespec="seconds")
    new_entries: List[Dict[str, Any]] = []

    if prev is None:
        # First-ever run: log a seed entry only if there are any overrides
        if curr:
            for k, v in sorted(curr.items()):
                new_entries.append({
                    "ts": now, "type": "override_added",
                    "key": k, "old": None, "new": v,
                    "source": "seed",
                })
    else:
        diffs = _diff(prev, curr)
        for d in diffs:
            entry = {"ts": now, "source": "operator", **d}
            new_entries.append(entry)

    if new_entries:
        entries.extend(new_entries)
        entries = entries[-MAX_HISTORY:]

    payload = {
        "generated_at": now,
        "current_config_hash": curr_hash,
        "n_overrides": len(curr),
        "entries": entries,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    # Update last-seen snapshot for next run
    with open(LAST_SNAP_PATH, "w") as f:
        json.dump(curr, f)

    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {HIST_PATH}")
    print(f"  current_config_hash: {p['current_config_hash']}")
    print(f"  total history entries: {len(p['entries'])}")
    if p["entries"]:
        latest = p["entries"][-3:]
        for e in latest:
            print(f"  - {e['ts']} {e['type']} {e['key']}: {e.get('old')} -> {e.get('new')}")
