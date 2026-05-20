"""
EdgeStat -- pipeline watchdog.

Runs in the live-games workflow (every 10 min). Checks freshness of
critical data files and writes data/pipeline_health.json. If today.json
is more than 8 hours stale, surfaces an alarm so the dashboard shows a
"data freshness" warning instead of silently serving yesterday's slate.

Without this, the daily-pipeline failure I shipped last night went
undetected for 13 hours -- the live site kept showing TEX @ COL as
"tonight's pick" while that game had already finished hours ago.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "pipeline_health.json")

# Per-file freshness thresholds (minutes)
THRESHOLDS = {
    "today.json": {"warn": 240, "critical": 480},          # 4h warn, 8h critical
    "matchups.json": {"warn": 240, "critical": 480},
    "todays_top_plays.json": {"warn": 60, "critical": 180},   # refreshed in live cycle
    "live_clv.json": {"warn": 30, "critical": 90},            # every 10 min
    "all_picks_ledger.json": {"warn": 60, "critical": 180},
    "pod_pl.json": {"warn": 120, "critical": 360},
    "calibration_status.json": {"warn": 240, "critical": 720},
}


def run() -> Dict[str, Any]:
    now = dt.datetime.now()
    file_health = {}
    n_critical = 0
    n_warn = 0
    n_ok = 0

    for fn, thr in THRESHOLDS.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            file_health[fn] = {"status": "MISSING", "age_min": None}
            n_critical += 1
            continue
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
        age_min = (now - mtime).total_seconds() / 60
        if age_min > thr["critical"]:
            status = "CRITICAL"
            n_critical += 1
        elif age_min > thr["warn"]:
            status = "WARN"
            n_warn += 1
        else:
            status = "OK"
            n_ok += 1
        file_health[fn] = {
            "status": status,
            "age_min": round(age_min, 1),
            "warn_threshold_min": thr["warn"],
            "critical_threshold_min": thr["critical"],
            "last_modified": mtime.isoformat(timespec="seconds"),
        }

    overall = "CRITICAL" if n_critical > 0 else ("WARN" if n_warn > 0 else "OK")

    # Suggest action if critical
    action = None
    if overall == "CRITICAL":
        oldest = max([(v["age_min"] or 999999, k) for k, v in file_health.items()
                       if v["status"] == "CRITICAL"], default=(0, None))
        action = (f"Manually trigger daily-pipeline workflow. Stale file: "
                  f"{oldest[1]} ({oldest[0]:.0f} min old)")

    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "overall_status": overall,
        "n_critical": n_critical,
        "n_warn": n_warn,
        "n_ok": n_ok,
        "suggested_action": action,
        "file_health": file_health,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Pipeline health: {p['overall_status']} ({p['n_ok']} OK / {p['n_warn']} WARN / {p['n_critical']} CRITICAL)")
    if p["suggested_action"]:
        print(f"  -> {p['suggested_action']}")
    for fn, f in p["file_health"].items():
        marker = {"OK":"[+]", "WARN":"[!]", "CRITICAL":"[X]", "MISSING":"[?]"}.get(f["status"], "?")
        age = f"{f['age_min']:.0f}min" if f["age_min"] is not None else "MISSING"
        print(f"  {marker} {fn:35s}  {age:>10s}  ({f['status']})")
