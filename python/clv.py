"""
EdgeStat -- Closing Line Value (CLV) tracker.

CLV is the gold-standard predictor of long-term profitability. The math:

  CLV_per_bet = (implied_prob_at_close - implied_prob_at_bet) * 100

If you bet a team at -130 (56.5% implied) and the closing line is -150 (60%),
your CLV is +3.5%. Over a large sample, average CLV > 0 correlates almost
perfectly with positive ROI -- because beating the closing line proves you
got a better number than the sharpest money in the market.

This module:
  1. Reads today's morning snapshot (data/history/YYYY-MM-DD_today.json)
     -- captures the line we recommended at.
  2. Reads the latest data/today.json -- captures the "close" line (latest
     available before game-time; better: pull a final pre-game snapshot
     ~30 min before first pitch).
  3. For each game/recommendation, compute CLV per market.
  4. Append to data/clv_log.json.

Run on the 6 PM ET cron so we capture lines as close to game-time as possible.
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


def compute_clv_for_date(date_iso: str) -> List[Dict[str, Any]]:
    """For each game in the morning snapshot, compare lines to latest today.json
    and emit CLV per side."""
    morning = _load(os.path.join(HISTORY_DIR, f"{date_iso}_today.json"))
    latest = _load(os.path.join(DATA_DIR, "today.json"))
    if not morning.get("games") or not latest.get("games"):
        return []

    # Index latest by matchup
    latest_by_matchup = {g["matchup"]: g for g in latest["games"]}

    out: List[Dict[str, Any]] = []
    for mg in morning["games"]:
        match = mg["matchup"]
        lg = latest_by_matchup.get(match)
        if not lg:
            continue
        m_morning = mg.get("market", {})
        m_close = lg.get("market", {})
        for side_key, label in (("home_ml", "HOME_ML"), ("away_ml", "AWAY_ML")):
            p_open = m_morning.get(side_key)
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
            })
        # Total CLV
        t_open = m_morning.get("total")
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


if __name__ == "__main__":
    today_iso = dt.date.today().isoformat()
    records = compute_clv_for_date(today_iso)
    log = append_clv_log(records)
    s = summary(log)
    print(f"CLV records added today: {len(records)}")
    print(f"Total log records: {len(log.get('records', []))}")
    if s.get("n"):
        print(f"  Lifetime avg CLV: {s['avg_clv_pct']}% ({s['positive_clv_pct']}% positive, "
              f"best {s['best']}%, worst {s['worst']}%)")
    else:
        print("  No graded CLV records yet -- pipeline needs multiple snapshots in one day.")
