"""
EdgeStat -- Slate master brief.

Single consolidated daily brief combining:
  - slate_quality_index (overall tier + advisory)
  - tonight_top_5_curated (top picks)
  - daily_fade_board (top fades)
  - cross_sport_event_board (top events)
  - slate_roi_projection (expected ROI)

This is the ONE OUTPUT for the homepage that gives the user everything
they need to know about tonight in a single document.

Output: data/slate_master_brief.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_master_brief.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    quality = _load(os.path.join(DATA_DIR, "slate_quality_index.json"))
    top_5 = _load(os.path.join(DATA_DIR, "tonight_top_5_curated.json"))
    fade_board = _load(os.path.join(DATA_DIR, "daily_fade_board.json"))
    events = _load(os.path.join(DATA_DIR, "cross_sport_event_board.json"))
    roi = _load(os.path.join(DATA_DIR, "slate_roi_projection.json"))
    lock = _load(os.path.join(DATA_DIR, "tonight_lock_of_night.json"))

    brief = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "headline": {
            "slate_quality_tier": quality.get("tier"),
            "slate_quality_score": quality.get("slate_quality_score"),
            "advisory": quality.get("advisory"),
            "total_locks": quality.get("total_locks"),
            "total_strong": quality.get("total_strong"),
            "total_fades": quality.get("total_fades"),
        },
        "lock_of_night": (lock.get("lock") or {}),
        "top_5_picks": top_5.get("top_5_picks") or [],
        "top_3_fades": top_5.get("top_3_fades") or [],
        "top_events": events.get("top_15") or [],
        "events_by_sport": events.get("by_sport") or {},
        "expected_roi": {
            "n_picks": roi.get("n_picks"),
            "avg_edge_pp": roi.get("avg_edge_pp"),
            "expected_roi_pct_quarter_kelly": roi.get("expected_roi_pct_quarter_kelly"),
            "expected_pl_on_100_bankroll": roi.get("expected_pl_on_100_bankroll"),
        },
        "fade_board_top_5": (fade_board.get("top_15") or [])[:5],
        "method_note": "Master daily brief consolidating slate_quality_index + "
                       "tonight_top_5_curated + daily_fade_board + "
                       "cross_sport_event_board + slate_roi_projection + "
                       "lock_of_night into single homepage feed.",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(brief, f, indent=2)
    return brief


if __name__ == "__main__":
    o = run()
    print(f"[master-brief] quality={o['headline']['slate_quality_tier']} "
          f"({o['headline']['slate_quality_score']} score, "
          f"{o['headline']['total_locks']} LOCKs, "
          f"{o['headline']['total_strong']} STRONG) "
          f"+ {len(o['top_5_picks'])} curated picks "
          f"+ {len(o['top_events'])} top events -> {OUT}")
