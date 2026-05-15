"""
EdgeStat -- pipeline health monitor.

Runs after every cron and writes data/pipeline_health.json: a snapshot of
which artifacts are fresh, which are stale, which are missing, and which
look subtly wrong (e.g., today.json with is_demo=True games, props.json
with 0 rows, calibration_live.json with no markets).

The audit page reads this. Designed to catch the kinds of silent failures
we hit earlier this session:
  - DEMO_SLATE silent fallback wrote fake matchups that lost game-line
    settlements for a full day
  - Odds API 401 wrote book=None everywhere and 0 prop rows
  - Pages deploy queue backed up so live site showed stale data

Categories:
  ok     - artifact exists, is fresh (within expected_h), has data
  stale  - exists + has data but older than expected
  empty  - exists + fresh but has no data (e.g., 0 games)
  demo   - exists but contains demo-flagged records
  missing- artifact file doesn't exist on disk
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HEALTH_PATH = os.path.join(DATA_DIR, "pipeline_health.json")


CHECKS = [
    # (filename, count_key, expected_h, freshness_h, label)
    ("today.json",            "games",          8,  "Slate"),
    ("matchups.json",         "games",          8,  "Matchup digest"),
    ("props.json",            "top_edges",      8,  "Player props"),
    ("parlays.json",          "parlays",        8,  "Parlay engine"),
    ("pickem.json",           "modeled_props",  24, "PrizePicks"),
    ("pickem_optimizer.json", "by_size",        24, "PP optimizer"),
    ("top_plays.json",        "plays",          8,  "Top plays aggregator"),
    ("clv_log.json",          "records",        8,  "CLV log"),
    ("track_record.json",     "props",          48, "Settled track record"),
    ("calibration_live.json", "markets",        48, "Calibration corrections"),
    ("residuals.json",        "markets",        48, "Residual analysis"),
    ("nrfi.json",             "projections",    8,  "NRFI / YRFI"),
    ("first_five.json",       "projections",    8,  "First-5 totals"),
    ("run_line.json",         "projections",    8,  "Run line"),
    ("live_state.json",       "games",          1,  "Live in-game"),
]


def _check(filename: str, count_key: str, expected_h: float, label: str) -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, filename)
    result: Dict[str, Any] = {"label": label, "file": filename, "expected_h": expected_h}

    if not os.path.exists(path):
        result["status"] = "missing"
        result["count"] = None
        result["age_h"] = None
        result["notes"] = "file not on disk"
        return result

    mtime = os.path.getmtime(path)
    age_h = (dt.datetime.now().timestamp() - mtime) / 3600
    result["age_h"] = round(age_h, 2)
    result["generated_at"] = dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")

    notes = []
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception as e:
        result["status"] = "parse_error"
        result["count"] = None
        result["notes"] = f"json parse error: {str(e)[:80]}"
        return result

    # Count records
    count: Any = None
    if isinstance(d, dict):
        v = d.get(count_key)
        if isinstance(v, list):
            count = len(v)
        elif isinstance(v, dict):
            count = len(v)
    elif isinstance(d, list):
        count = len(d)
    result["count"] = count

    # Demo-flag detection on slate-like files
    if filename == "today.json":
        games = (d.get("games") or [])
        if games and all(g.get("is_demo") for g in games):
            result["status"] = "demo"
            notes.append("all games tagged is_demo=True (real-data pull failed)")
            result["notes"] = "; ".join(notes)
            return result
        # Detect placeholder pricing: book=null on every game
        if games and not any((g.get("market") or {}).get("book") for g in games):
            notes.append("no game has a real book attached (Odds API + Bovada both down?)")

    # Zero-data flag
    if count == 0:
        result["status"] = "empty"
        notes.append(f"{count_key} is empty")
        result["notes"] = "; ".join(notes)
        return result

    # Freshness
    if age_h <= expected_h:
        status = "ok"
    elif age_h <= expected_h * 2:
        status = "stale"
        notes.append(f"older than expected (>{expected_h}h)")
    else:
        status = "old"
        notes.append(f"much older than expected (>{expected_h * 2}h)")

    result["status"] = status
    result["notes"] = "; ".join(notes) if notes else "fresh + populated"
    return result


def run() -> Dict[str, Any]:
    results = [_check(*c) for c in CHECKS]
    overall_status = "ok"
    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_empty = sum(1 for r in results if r["status"] == "empty")
    n_stale = sum(1 for r in results if r["status"] in ("stale", "old"))
    n_demo = sum(1 for r in results if r["status"] == "demo")
    n_missing = sum(1 for r in results if r["status"] == "missing")
    n_err = sum(1 for r in results if r["status"] == "parse_error")
    if n_demo or n_err or n_missing >= 3:
        overall_status = "critical"
    elif n_empty >= 2 or n_stale >= 4:
        overall_status = "warning"
    elif n_stale >= 1 or n_empty >= 1:
        overall_status = "degraded"

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "overall_status": overall_status,
        "n_ok": n_ok,
        "n_empty": n_empty,
        "n_stale": n_stale,
        "n_demo": n_demo,
        "n_missing": n_missing,
        "n_parse_error": n_err,
        "total_artifacts": len(results),
        "artifacts": results,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HEALTH_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Overall: {p['overall_status']}")
    print(f"  ok: {p['n_ok']}/{p['total_artifacts']}, empty: {p['n_empty']}, "
          f"stale: {p['n_stale']}, demo: {p['n_demo']}, missing: {p['n_missing']}, "
          f"parse_error: {p['n_parse_error']}")
    print()
    for r in p["artifacts"]:
        flag = "[ok]" if r["status"] == "ok" else f"[{r['status']}]"
        print(f"  {flag:12} {r['label']:30}  age={r['age_h']}h  n={r['count']}  -- {r['notes']}")
