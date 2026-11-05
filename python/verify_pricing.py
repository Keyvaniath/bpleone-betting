"""
EdgeStat -- pricing guard (2026-11-04). Fails the build if a pick surface
publishes a pick that is not backed by a real sportsbook price.

The contract (docs/ODDS-INTEGRITY.md, python/quotes.py): a PICK needs a
sportsbook quote -- a price that is not the model's own fair price, observed
<= 180 min before the artifact was written, for an event that had not started.
Anything else is a projection and must say so (actionable: false / is_pick:
false). -110 is a legitimate price; what is rejected is a price with no
sportsbook provenance.

Two parts, like verify_calibration:
  1. SELF-TEST: synthetic rows prove each check rejects what it should (a guard
     that passes everything is worse than none).
  2. LIVE: every pick list in the published artifacts is checked.

Exit 1 on any violation. Run: python verify_pricing.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MAX_QUOTE_AGE_MIN = 180

# Fields that may hold a SPORTSBOOK price, in the order producers use them.
PRICE_FIELDS = ("book_american", "market_american", "dk_american")

# (artifact, list key) -> every row is a pick unless it says it is not.
PICK_SURFACES: List[Tuple[str, str]] = [
    ("todays_picks.json", "picks"),
    ("todays_top_plays.json", "top_25"),
    ("todays_top_plays.json", "top_5_by_kelly"),
    ("todays_top_plays.json", "top_5_by_prob"),
    ("best_bets.json", "bets"),
    ("multi_sport_top.json", "picks"),
    ("pregame_alerts.json", "alerts"),
    ("bet_slate.json", "slate"),
    ("fade_picks.json", "all_fades"),
    ("whale_picks.json", "whales"),
    ("alpha_pick_of_day.json", "top_5_alphas"),
    ("alpha_pick_of_day.json", "other_picks"),
    # (2026-11-05) found by a scan of every data/*.json list carrying a price
    # and an edge/play: these published model-fair rows (or a DK price with no
    # observation time) with no projection flag.
    ("cfb_model.json", "edges"),
    ("picks_export.json", "picks"),
    ("player_pot.json", "top_5"),
]
# (artifact, key) -> a single pick dict (or a no-pick marker).
SINGLE_PICKS: List[Tuple[str, str]] = [
    ("alpha_pick_of_day.json", "alpha_pick"),
]


def _parse(ts) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        t = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _is_projection(row: Dict[str, Any]) -> bool:
    return (row.get("actionable") is False or row.get("is_pick") is False
            or row.get("no_pick") is True or row.get("projection") is True)


def _price(row: Dict[str, Any]) -> Tuple[Optional[Any], Optional[str]]:
    for f in PRICE_FIELDS:
        if row.get(f) is not None:
            return row[f], f
    q = row.get("quote")
    if isinstance(q, dict) and q.get("american") is not None:
        return q["american"], "quote.american"
    return None, None


def check_row(row: Dict[str, Any], published_at: Optional[dt.datetime]) -> List[str]:
    """Violations for one row ([] = clean)."""
    if not isinstance(row, dict) or _is_projection(row):
        return []
    price, field = _price(row)
    if price is None:
        return ["pick with no sportsbook price (only " +
                ("fair_american" if row.get("fair_american") is not None else "no price") + ")"]
    try:
        int(price)
    except (TypeError, ValueError):
        return [f"{field} is not a price: {price!r}"]
    out = []
    q = row.get("quote") if isinstance(row.get("quote"), dict) else None
    obs = _parse((q or {}).get("observed_at") or row.get("odds_observed_at") or row.get("observed_at"))
    if q is not None and q.get("provenance") not in (None, "book_snapshot"):
        out.append(f"quote provenance {q.get('provenance')!r} is not a book snapshot")
    if obs is None:
        # A price with no observation time cannot be shown to be a live quote.
        if row.get("fair_american") is not None and price == row.get("fair_american"):
            out.append("price equals the model's fair price and has no observation time")
        else:
            out.append(f"{field} has no observation time (provenance unknown)")
    elif published_at is not None:
        age = (published_at - obs).total_seconds() / 60
        if age > MAX_QUOTE_AGE_MIN:
            out.append(f"quote {age:.0f} min old when published (> {MAX_QUOTE_AGE_MIN})")
        if age < -5:
            out.append("quote observed after the artifact was written")
    st = _parse((q or {}).get("scheduled_start") or row.get("commence_time") or row.get("start_time"))
    if st is not None and published_at is not None and st <= published_at:
        out.append("event had started when the pick was published")
    if q is not None and str(q.get("event_status") or "pre") != "pre":
        out.append(f"quote event_status {q.get('event_status')!r}")
    return out


def _load(name: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def check_artifacts() -> Tuple[int, List[str]]:
    n_rows, bad = 0, []
    for name, key in PICK_SURFACES + SINGLE_PICKS:
        d = _load(name)
        if not isinstance(d, dict):
            continue
        pub = _parse(d.get("generated_at"))
        v = d.get(key)
        rows = [v] if isinstance(v, dict) else (v if isinstance(v, list) else [])
        for i, r in enumerate(rows):
            if not isinstance(r, dict) or not r:
                continue
            n_rows += 1
            for msg in check_row(r, pub):
                label = r.get("label") or r.get("player_or_matchup") or r.get("matchup") or r.get("player") or "?"
                bad.append(f"{name}:{key}[{i}] {label} -- {msg}")
    return n_rows, bad


def self_test() -> List[str]:
    """Each case must produce (or not produce) a violation. Returns failures."""
    now = dt.datetime(2026, 11, 4, 22, 0, tzinfo=dt.timezone.utc)
    iso = lambda m: (now - dt.timedelta(minutes=m)).isoformat()
    later = (now + dt.timedelta(hours=2)).isoformat()
    good_q = {"american": -110, "provenance": "book_snapshot", "observed_at": iso(20),
              "scheduled_start": later, "event_status": "pre"}
    cases = [
        ("real -110 DK quote is a valid pick", {"book_american": -110, "quote": good_q}, False),
        ("fair price only", {"fair_american": -150}, True),
        ("no price at all", {"label": "x"}, True),
        ("projection without a price is fine", {"fair_american": -150, "actionable": False}, False),
        ("stale quote", {"book_american": -120, "quote": {**good_q, "observed_at": iso(400)}}, True),
        ("started event", {"book_american": -120, "quote": {**good_q, "scheduled_start": iso(10)}}, True),
        ("in-play quote", {"book_american": -120, "quote": {**good_q, "event_status": "in"}}, True),
        ("non-book provenance", {"book_american": -120, "quote": {**good_q, "provenance": "model"}}, True),
        ("book price, no timestamp", {"book_american": -120}, True),
        ("price == fair, no timestamp", {"book_american": -110, "fair_american": -110}, True),
        ("pregame alert with observed time", {"dk_american": 135, "odds_observed_at": iso(30)}, False),
        ("garbage price", {"book_american": "TBD", "quote": good_q}, True),
    ]
    fails = []
    for name, row, expect_bad in cases:
        got_bad = bool(check_row(row, now))
        if got_bad != expect_bad:
            fails.append(f"self-test '{name}': expected {'violation' if expect_bad else 'clean'}, "
                         f"got {check_row(row, now) or 'clean'}")
    return fails


def main() -> int:
    fails = self_test()
    for f in fails:
        print(f"  [FAIL] {f}")
    if not fails:
        print("  [PASS] self-test: 12 synthetic cases (real -110 accepted; fair-only, stale, "
              "started, in-play, non-book, untimestamped rejected)")
    n, bad = check_artifacts()
    for b in bad[:40]:
        print(f"  [FAIL] {b}")
    if len(bad) > 40:
        print(f"  ... {len(bad) - 40} more")
    if not bad:
        print(f"  [PASS] {n} published pick rows across {len(PICK_SURFACES) + len(SINGLE_PICKS)} "
              "surfaces carry a fresh pre-start sportsbook price")
    if fails or bad:
        print("PRICING GUARD FAILED")
        return 1
    print("PRICING GUARD PASSES.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
