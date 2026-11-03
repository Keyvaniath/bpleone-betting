"""
EdgeStat -- the pricing contract (2026-11-03, P0 odds integrity).

Every ACTIONABLE recommendation must carry a genuine sportsbook quote. This
module is the one place that decides what counts as one, and the one place for
the price math. It FAILS CLOSED: a candidate with a missing, stale, synthetic,
mismatched or post-start quote is not actionable -- it may be shown as a
labelled projection, never ranked, published or graded as a bet.

Provenance values (a quote's `provenance`):
  book_snapshot  a sportsbook price read from a timestamped snapshot
                 (data/espn_odds.json: DraftKings via ESPN). The ONLY actionable kind.
  reconstructed  a historical book price recovered from git-history snapshots
                 (ml_reprice seeds). Valid for grading history, never for a live pick.
  model_fair     the model's own fair price (1/p). Not a market quote.
  venue_breakeven PrizePicks' per-leg break-even (-136). Not a sportsbook quote.
  synthetic      a placeholder (-110 filled in when a price was missing).

-110 is a legitimate real price: the NUMBER is never rejected, only a quote
whose provenance is not book_snapshot.

Math (binary market, no push):
  decimal = 1 + A/100 (A > 0), 1 + 100/|A| (A < 0); |A| < 100 is invalid.
  EV per unit = p_win * decimal - 1  (= p_win*(decimal-1) - p_loss).
  no-vig: only from the two opposing prices of ONE matched market snapshot.
  minimum acceptable price for an EV hurdle h: decimal_min = (1 + h) / p --
  a model-derived threshold, not an observed quote.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from typing import Any, Dict, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

ACTIONABLE_PROVENANCE = "book_snapshot"
MAX_QUOTE_AGE_MIN = 180        # a snapshot older than this is stale for a live pick
START_CUTOFF_MIN = 5           # no new pick within 5 min of the scheduled start

# Rejection reasons (stable codes -- the candidate funnel counts these)
R_NO_QUOTE = "no_quote"                 # no sportsbook quote exists for this market
R_UNSUPPORTED = "unsupported_market"    # we have no sportsbook source for this market type (all props)
R_LINE_MISMATCH = "line_mismatch"       # the book's line differs from the candidate's
R_STALE = "stale_quote"
R_STARTED = "event_started"
R_INVALID = "invalid_price"
R_NOT_BOOK = "non_book_provenance"


# ------------------------------------------------------------------ math ----
def american_to_decimal(a) -> Optional[float]:
    """Exact conversion; None for missing or invalid (|A| < 100, non-numeric)."""
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if a != a or abs(a) < 100:          # NaN, 0, and |A| < 100 are not American odds
        return None
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def decimal_to_american(d: float) -> Optional[int]:
    if d is None or d <= 1:
        return None
    return int(round((d - 1) * 100)) if d >= 2 else -int(round(100 / (d - 1)))


def implied_prob(a) -> Optional[float]:
    d = american_to_decimal(a)
    return 1 / d if d else None


def ev_binary(p_win: float, decimal: float) -> Optional[float]:
    """Expected net return per unit, binary outcome with no push."""
    if p_win is None or decimal is None or not (0 <= p_win <= 1) or decimal <= 1:
        return None
    return p_win * decimal - 1


def no_vig_two_way(a_side, a_other) -> Optional[float]:
    """No-vig probability of `a_side` by proportional normalisation of ONE
    market's two opposing prices. Both must be valid."""
    p1, p2 = implied_prob(a_side), implied_prob(a_other)
    if p1 is None or p2 is None:
        return None
    return p1 / (p1 + p2)


def min_acceptable_american(p_win: float, ev_hurdle: float = 0.0) -> Optional[int]:
    """The worst price at which the model still clears `ev_hurdle`. A
    model-derived threshold -- never an observed quote."""
    if not p_win or p_win <= 0 or p_win >= 1:
        return None
    return decimal_to_american((1 + ev_hurdle) / p_win)


# ---------------------------------------------------------------- quotes ----
def _parse_ts(s) -> Optional[dt.datetime]:
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)   # espn_odds writes naive UTC


_SNAPSHOT: Optional[Dict[str, Any]] = None


def load_snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """The DraftKings board (espn_odds.json). Cached per process."""
    global _SNAPSHOT
    if path is not None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if _SNAPSHOT is None:
        try:
            with open(os.path.join(DATA_DIR, "espn_odds.json"), encoding="utf-8") as f:
                _SNAPSHOT = json.load(f)
        except Exception:
            _SNAPSHOT = {}
    return _SNAPSHOT


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().upper())


def _ml_side(market: str, matchup: str) -> Optional[str]:
    m = str(market or "").lower()
    if "ml_home" in m or m in ("home ml", "home_ml", "team_ml_home"):
        return "home"
    if "ml_away" in m or m in ("away ml", "away_ml", "team_ml_away"):
        return "away"
    t = re.fullmatch(r"([a-z]{2,4})_ml", m)
    if t and "@" in str(matchup or ""):
        away, home = [x.strip().lower() for x in str(matchup).split("@", 1)]
        team = t.group(1)
        if home.startswith(team) or team.startswith(home):
            return "home"
        if away.startswith(team) or team.startswith(away):
            return "away"
    return None


def _total(market: str) -> Optional[Tuple[str, float]]:
    m = re.fullmatch(r"(?:total_)?(over|under)[_ ](\d+(?:\.\d+)?)", str(market or "").lower())
    return (m.group(1), float(m.group(2))) if m else None


def find_quote(sport: str, matchup: str, market: str, snapshot: Optional[Dict[str, Any]] = None
               ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(quote, None) for a game moneyline / total DraftKings posted, else
    (None, reason). The quote carries everything the data contract needs."""
    snap = snapshot if snapshot is not None else load_snapshot()
    side = _ml_side(market, matchup)
    tot = _total(market)
    if side is None and tot is None:
        return None, R_UNSUPPORTED
    g = next((x for x in (snap.get("games") or [])
              if _norm(x.get("matchup")) == _norm(matchup)
              and (not sport or _norm(x.get("sport")) == _norm(sport))), None)
    if g is None:
        return None, R_NO_QUOTE
    m = g.get("market") or {}
    if side:
        price, opp = (m.get("ml_home"), m.get("ml_away")) if side == "home" else (m.get("ml_away"), m.get("ml_home"))
        line, sel = None, side
    else:
        ou, ln = tot
        if m.get("total") is None:
            return None, R_NO_QUOTE
        if float(m["total"]) != ln:
            return None, R_LINE_MISMATCH
        price, opp = (m.get("over_price"), m.get("under_price")) if ou == "over" else (m.get("under_price"), m.get("over_price"))
        line, sel = ln, ou
    if american_to_decimal(price) is None:
        return None, R_INVALID if price is not None else R_NO_QUOTE
    return {
        "provenance": ACTIONABLE_PROVENANCE,
        "book": str(m.get("book") or g.get("provider") or "draftkings").lower(),
        "provider": "espn-scoreboard",
        "american": int(price), "decimal": round(american_to_decimal(price), 4),
        "opposing_american": opp,
        "no_vig_prob": (round(no_vig_two_way(price, opp), 4) if no_vig_two_way(price, opp) is not None else None),
        "selection": sel, "line": line,
        "event_id": g.get("event_id"), "sport": g.get("sport"), "matchup": g.get("matchup"),
        "scheduled_start": g.get("commence_time"), "event_status": g.get("status"),
        "observed_at": snap.get("generated_at"),
        "snapshot_id": f"espn_odds@{snap.get('generated_at')}#{g.get('event_id')}",
    }, None


def actionable(quote: Optional[Dict[str, Any]], now: Optional[dt.datetime] = None,
               max_age_min: int = MAX_QUOTE_AGE_MIN) -> Tuple[bool, Optional[str]]:
    """May this quote back a live recommendation? Fail closed on anything off."""
    if not quote:
        return False, R_NO_QUOTE
    if quote.get("provenance") != ACTIONABLE_PROVENANCE:
        return False, R_NOT_BOOK
    if american_to_decimal(quote.get("american")) is None:
        return False, R_INVALID
    now = now or dt.datetime.now(dt.timezone.utc)
    obs = _parse_ts(quote.get("observed_at"))
    if obs is None or (now - obs).total_seconds() / 60 > max_age_min:
        return False, R_STALE
    if str(quote.get("event_status") or "pre") != "pre":
        return False, R_STARTED
    st = _parse_ts(quote.get("scheduled_start"))
    if st is not None and (st - now).total_seconds() / 60 < START_CUTOFF_MIN:
        return False, R_STARTED
    return True, None


def price_candidate(sport, matchup, market, p_model, ev_hurdle: float = 0.0,
                    snapshot: Optional[Dict[str, Any]] = None, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """Everything a candidate needs from pricing, in one fail-closed call:
    {actionable, reason, quote, ev, min_acceptable_american, edge_vs_no_vig}."""
    q, why = find_quote(sport, matchup, market, snapshot)
    ok, why2 = actionable(q, now) if q else (False, why)
    out = {"actionable": ok, "reason": None if ok else (why2 or why), "quote": q,
           "ev": None, "min_acceptable_american": min_acceptable_american(p_model, ev_hurdle) if p_model else None,
           "edge_vs_no_vig": None}
    if q and p_model is not None:
        out["ev"] = round(ev_binary(p_model, q["decimal"]), 4) if ev_binary(p_model, q["decimal"]) is not None else None
        if q.get("no_vig_prob") is not None:
            out["edge_vs_no_vig"] = round(p_model - q["no_vig_prob"], 4)
    return out
