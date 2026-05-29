"""
EdgeStat -- Closing Line Value (CLV) tracker.

CLV is the gold-standard predictor of long-term profitability. The math:

  CLV_per_bet = (implied_prob_at_close - implied_prob_at_bet) * 100

If you bet a team at -130 (56.5% implied) and the closing line is -150 (60%),
your CLV is +3.5%. Over a large sample, average CLV > 0 correlates almost
perfectly with positive ROI -- because beating the closing line proves you
got a better number than the sharpest money in the market.

Mechanism (open/close snapshot lifecycle):
  1. capture_snapshots() freezes an OPEN snapshot once per slate date
     (history/{date}_open.json, write-once -- never clobbered) and refreshes
     a CLOSE snapshot every run (history/{date}_close.json, always-latest).
  2. compute_clv_for_date() computes implied(close) - implied(open) per market.
  3. Append to data/clv_log.json (idempotent, replaces the date's records).

Driven by the Daily MLB Pipeline crons: the 6 AM ET run freezes the morning
OPEN; the 6 PM ET run captures the near-game-time CLOSE. CLV = the move from
posting to close, the gold-standard sharpness proxy.

History / why this exists: the prior version read a "morning snapshot" that
was rewritten by the SAME pipeline run that computed CLV, so open == close and
clv_pct was structurally 0.0 on every record -- which also capped every source
in the learning-integrity model at grade B (grade A requires CLV >= +2pp).
Write-once open fixes that: the 6 AM open survives the 6 PM run.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
LOG_PATH = os.path.join(DATA_DIR, "clv_log.json")


def implied_prob(price: int) -> float:
    """American odds -> implied probability after removing vig is too aggressive
    for one-side measurement; this is the raw implied prob."""
    if price >= 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _line_payload(latest: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal line-only snapshot extracted from a today.json blob."""
    return {
        "captured_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "slate_date": (latest.get("generated_at") or "")[:10],
        "games": [
            {"matchup": g.get("matchup"), "market": g.get("market", {})}
            for g in (latest.get("games") or []) if g.get("matchup")
        ],
    }


def capture_snapshots(latest: Dict[str, Any]) -> Optional[str]:
    """Freeze an OPEN line snapshot once per slate date (write-once) and refresh
    a CLOSE snapshot every run (always-latest). Returns the slate date or None.

    This is what makes CLV real. Previously "open" was just today.json from a
    few minutes earlier (same pipeline run) -> open == close -> CLV always 0.
    Now open is frozen the first time we see lines for a slate and is never
    clobbered; close converges toward the true closing line as the every-2h
    heartbeat re-runs through the day. Keyed by today.json's own slate date so
    a stale off-hours run can't freeze a bogus open under the wrong day.
    """
    games = latest.get("games") or []
    if not games:
        return None
    date_iso = (latest.get("generated_at") or dt.date.today().isoformat())[:10]
    os.makedirs(HISTORY_DIR, exist_ok=True)
    payload = _line_payload(latest)
    open_path = os.path.join(HISTORY_DIR, f"{date_iso}_open.json")
    close_path = os.path.join(HISTORY_DIR, f"{date_iso}_close.json")
    # Write-once open: never overwrite the first lines frozen for this slate.
    if not os.path.exists(open_path):
        with open(open_path, "w") as f:
            json.dump(payload, f, indent=2)
    # Always-latest close: each run pulls it nearer to game-time.
    with open(close_path, "w") as f:
        json.dump(payload, f, indent=2)
    return date_iso


def compute_clv_for_date(date_iso: str) -> List[Dict[str, Any]]:
    """CLV = implied(close) - implied(open) per market for the slate.

    Open = frozen first-seen lines (history/{date}_open.json); close = latest
    pre-game lines (history/{date}_close.json). Falls back to the legacy morning
    snapshot / live today.json when the new frozen files are not present yet."""
    open_blob = (_load(os.path.join(HISTORY_DIR, f"{date_iso}_open.json"))
                 or _load(os.path.join(HISTORY_DIR, f"{date_iso}_today.json")))
    close_blob = (_load(os.path.join(HISTORY_DIR, f"{date_iso}_close.json"))
                  or _load(os.path.join(DATA_DIR, "today.json")))
    if not open_blob.get("games") or not close_blob.get("games"):
        return []

    close_by_matchup = {g["matchup"]: g for g in close_blob["games"] if g.get("matchup")}

    out: List[Dict[str, Any]] = []
    for og in open_blob["games"]:
        match = og.get("matchup")
        cg = close_by_matchup.get(match)
        if not cg:
            continue
        m_open = og.get("market", {})
        m_close = cg.get("market", {})
        for side_key, label in (("home_ml", "HOME_ML"), ("away_ml", "AWAY_ML")):
            p_open = m_open.get(side_key)
            p_close = m_close.get(side_key)
            if p_open is None or p_close is None:
                continue
            try:
                clv = round((implied_prob(p_close) - implied_prob(p_open)) * 100, 2)
            except Exception:
                continue
            out.append({
                "date": date_iso,
                "matchup": match,
                "market": label,
                "open_price": p_open,
                "close_price": p_close,
                "open_implied_pct": round(implied_prob(p_open) * 100, 2),
                "close_implied_pct": round(implied_prob(p_close) * 100, 2),
                "clv_pct": clv,
                "open_book": m_open.get("book"),
                "close_book": m_close.get("book"),
            })
        # Total CLV (line move)
        t_open = m_open.get("total")
        t_close = m_close.get("total")
        if t_open is not None and t_close is not None and t_open != t_close:
            out.append({
                "date": date_iso,
                "matchup": match,
                "market": "TOTAL",
                "open_line": t_open,
                "close_line": t_close,
                "clv_line_delta": round(t_close - t_open, 1),
                "note": "Total line move",
            })
    return out


def append_clv_log(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Idempotent append: replaces records for the given date."""
    log: Dict[str, Any]
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            log = json.load(f)
    else:
        log = {"records": [], "last_updated": None}
    if not records:
        log["last_updated"] = dt.datetime.now().isoformat(timespec="seconds")
        with open(LOG_PATH, "w") as f:
            json.dump(log, f, indent=2)
        return log
    date = records[0]["date"]
    log["records"] = [r for r in log.get("records", []) if r.get("date") != date] + records
    log["last_updated"] = dt.datetime.now().isoformat(timespec="seconds")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
    return log


def summary(log: Dict[str, Any]) -> Dict[str, Any]:
    records = log.get("records", [])
    ml_records = [r for r in records if r.get("market", "").endswith("_ML") and r.get("clv_pct") is not None]
    if not ml_records:
        return {"n": 0}
    clvs = [r["clv_pct"] for r in ml_records]
    return {
        "n": len(ml_records),
        "avg_clv_pct": round(sum(clvs) / len(clvs), 3),
        "positive_clv_pct": round(sum(1 for c in clvs if c > 0) / len(clvs) * 100, 1),
        "best": max(clvs),
        "worst": min(clvs),
    }


def run() -> Dict[str, Any]:
    """Capture open/close snapshots for the current slate, then (re)compute its
    CLV records. Idempotent: safe to run on every heartbeat + pipeline cron."""
    latest = _load(os.path.join(DATA_DIR, "today.json"))
    date_iso = capture_snapshots(latest) or dt.date.today().isoformat()
    records = compute_clv_for_date(date_iso)
    log = append_clv_log(records)
    return {"date": date_iso, "n_records": len(records), "log": log}


if __name__ == "__main__":
    res = run()
    log = res["log"]
    s = summary(log)
    print(f"CLV snapshot+compute for {res['date']}: {res['n_records']} records this slate")
    print(f"Total log records: {len(log.get('records', []))}")
    if s.get("n"):
        print(f"  Lifetime avg CLV: {s['avg_clv_pct']}% ({s['positive_clv_pct']}% positive, "
              f"best {s['best']}%, worst {s['worst']}%)")
    else:
        print("  No non-zero CLV yet -- open is frozen; close converges as the "
              "every-2h heartbeat re-runs and lines move.")
