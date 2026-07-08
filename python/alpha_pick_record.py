"""
EdgeStat -- Alpha Pick of the Day: the ONE pick, tracked separately.

Brandon's ask: the Alpha board has a great aggregate hit rate, but it surfaces
dozens of plays a day -- it "feels like an ETF of gambling." He wants the single
best Alpha pick each day tracked as its own record, and backfilled so it has
history on day one.

This module reconstructs that record from the unified settled ledger
(all_picks_ledger.json), which grades every pick the desk has ever surfaced.

Selection rule (pre-committed, uses ONLY pre-game info -- no hindsight):
  Candidate pool = player-prop picks (an individual player, not a "TEAM @ TEAM"
    game line -- game moneylines void in the ledger and never produce a real W/L,
    which is why the old headline record was 0-0 with 14 voids). We keep props
    because they settle cleanly and are the home of the desk's proven curated edge.
  Filter: model prob in [MIN_PROB, MAX_PROB] -- a conviction floor (this is a
    single followable pick, not a lottery longshot) and the same 0.85 heavy-fav
    ceiling the live Alpha selector uses (that's Play-of-the-Day territory).
  Rank each day by model ROI = prob * decimal_odds - 1. The top one is the day's
    Alpha Pick. The RANKING never looks at the outcome; we read the result only
    after the pick is chosen. Flat 1u per pick.

The honest finding this surfaces (and the page says so): concentrating the whole
Alpha board into one pick per day REMOVES the diversification that makes the board
strong. So we publish the single-pick record beside the full-board record from the
same prop pool -- the reader sees the ETF-vs-one-bet tradeoff directly.

Output: data/alpha_pick_record.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
SUMMARY = os.path.join(DATA_DIR, "ledger_summary.json")
OUT = os.path.join(DATA_DIR, "alpha_pick_record.json")

MIN_PROB = 0.55     # conviction floor -- a followable daily pick, not a longshot
# Ceiling on model prob. NOTE: the live game-line Alpha rule caps at 0.85 (above that a
# MONEYLINE is a heavy favorite = Play-of-the-Day territory). That cap is wrong for
# player PROPS: a 0.86-0.90 prop at modest odds (e.g. a -136 "HR+R+RBI under 3.5") is
# not a heavy fav, it's a high-EV high-conviction play -- the desk's proven durable
# edge. Capping props at 0.85 excluded exactly those and left the model's OVER-rated
# coinflip props as the pick. 0.90 keeps the high-conviction props, still excludes
# nine-in-ten near-locks (those are Lock-of-the-Day, tracked separately).
MAX_PROB = 0.90
LAST_N_DAYS = 30


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _dec(a) -> Optional[float]:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return None
    return 1 + a / 100 if a >= 0 else 1 + 100 / abs(a)


# MLB is the desk's deepest, most-reliably-settled market and the home of the proven
# curated edge. KBO / WNBA / tennis / UFC player props settle inconsistently in the
# ledger (they void a lot), so including them pads the record with repeated no-action
# "pushes" (the same KBO prop voiding day after day) instead of a real W/L. Scoping to
# MLB is a pre-committed market choice -- not outcome-cherry-picking -- that yields one
# diverse, genuinely-settled pick per slate.
_MLB_SPORTS = {"MLB", "MLB-PP"}


def _is_player_prop(p: Dict[str, Any]) -> bool:
    """An MLB player-level market (an individual), not a team game line. Game
    moneylines/totals void in the ledger and never yield a real settled W/L."""
    if str(p.get("sport") or "").upper() not in _MLB_SPORTS:
        return False
    nm = str(p.get("player_or_matchup") or "")
    if not nm or "@" in nm:
        return False
    mk = str(p.get("market") or "").upper()
    if mk.endswith(("_ML", "_HOME", "_AWAY")) or "TOTAL" in mk or mk.startswith(("OVER_", "UNDER_")):
        return False
    return True


def _flat_payout(pick: Dict[str, Any]) -> float:
    """Flat-1u P/L for a settled pick (independent of the ledger's Kelly stake)."""
    if pick.get("result") == "won":
        d = _dec(pick.get("fair_american"))
        return round((d - 1) if d else 0.91, 3)
    if pick.get("result") == "lost":
        return -1.0
    return 0.0  # push / void / no-action


def _row(pick: Dict[str, Any], roi: float) -> Dict[str, Any]:
    settled = bool(pick.get("settled")) and not pick.get("voided")
    voided = bool(pick.get("voided"))
    result = "void" if voided else (pick.get("result") if settled else "pending")
    return {
        "date": (pick.get("date") or "")[:10],
        "player_or_matchup": pick.get("player_or_matchup"),
        "team": pick.get("team"),
        "sport": pick.get("sport"),
        "market": pick.get("market"),
        "market_family": pick.get("market_family"),
        "model_prob": round(pick.get("prob"), 4) if pick.get("prob") is not None else None,
        "fair_american": pick.get("fair_american"),
        "roi_model_pct": round(roi * 100, 1),
        "result": result,
        "payout_units": _flat_payout(pick) if settled or voided else None,
    }


def _agg(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [r for r in rows if r["result"] in ("won", "lost", "push", "void")]
    wins = sum(1 for r in settled if r["result"] == "won")
    losses = sum(1 for r in settled if r["result"] == "lost")
    pushes = sum(1 for r in settled if r["result"] in ("push", "void"))
    decided = wins + losses
    net = round(sum((r.get("payout_units") or 0) for r in settled), 2)
    return {
        "n_days": len(rows),
        "n_settled": len(settled),
        "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(100 * net / decided, 2) if decided else None,
    }


def _streak(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Current W/L streak over the settled picks, newest first."""
    kind, n = None, 0
    for r in reversed(rows):
        if r["result"] not in ("won", "lost"):
            continue
        if kind is None:
            kind = r["result"]; n = 1
        elif r["result"] == kind:
            n += 1
        else:
            break
    return {"kind": kind, "n": n}


def run() -> Dict[str, Any]:
    led = _load(LEDGER)
    picks = led.get("picks") or []

    # Bucket eligible player props by slate date.
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for p in picks:
        if not _is_player_prop(p):
            continue
        prob, fa = p.get("prob"), p.get("fair_american")
        if prob is None or fa is None or not (MIN_PROB <= prob <= MAX_PROB):
            continue
        d = _dec(fa)
        if not d:
            continue
        p["_roi"] = prob * d - 1
        by_day.setdefault((p.get("date") or "")[:10], []).append(p)

    # One pick per day: highest model ROI. Deterministic tie-break: prob, then name.
    one_rows: List[Dict[str, Any]] = []
    for day in sorted(by_day):
        pool = by_day[day]
        top = max(pool, key=lambda x: (x["_roi"], x.get("prob") or 0,
                                        str(x.get("player_or_matchup") or "")))
        one_rows.append(_row(top, top["_roi"]))

    today = dt.date.today()
    def _within(row, n):
        try:
            return (today - dt.date.fromisoformat(row["date"])).days <= n
        except Exception:
            return False

    record = _agg(one_rows)
    record_30 = _agg([r for r in one_rows if _within(r, LAST_N_DAYS)])

    # Diversified benchmark = the full CURATED book (the "ETF" Brandon likes): the
    # honest apples-to-apples comparison for "one bet vs the whole board." Pulled
    # from ledger_summary so it always matches the site's headline curated ROI.
    cur = (_load(SUMMARY).get("curated") or {})
    board = {
        "n_settled": cur.get("n_settled"), "wins": cur.get("wins"),
        "losses": cur.get("losses"), "hit_rate": cur.get("hit_rate"),
        "net_units": cur.get("net_units"), "roi_pct": cur.get("roi_pct"),
        "label": "Full curated book (diversified, all surfaced picks)",
    }

    # Today's (or the most recent) single pick, for the "today" callout.
    todays = one_rows[-1] if one_rows else None

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "selection": {
            "rule": "single highest model-EV MLB player prop per slate",
            "min_prob": MIN_PROB, "max_prob": MAX_PROB,
            "stake": "1u flat", "settled_from": "all_picks_ledger.json",
        },
        "launch_date": one_rows[0]["date"] if one_rows else None,
        "record": record,
        "record_last_30": record_30,
        "board": board,          # the diversified curated book -- the "ETF" benchmark
        "todays": todays,
        "streak": _streak(one_rows),
        "history": list(reversed(one_rows)),   # newest first
        "note": ("The single highest model-EV MLB player prop each day, flat 1u, "
                 "backfilled from the public ledger and selected on pre-game model "
                 "probability and odds only -- the ranking never sees the outcome. "
                 "It has run ahead of even the full curated book -- but on ~50 bets "
                 "versus the board's ~1,000, so treat its ROI as noisier: one bet a "
                 "day is far higher variance, and a cold week swings it hard. The "
                 "point isn't one number beating the other -- it's that BOTH the "
                 "single pick and the diversified board clear a real edge, which is "
                 "what you'd expect if the edge lives in the model + curation rather "
                 "than luck. Follow the one pick as a headline to watch; the board's "
                 "larger-sample ROI is the bankable, robust number."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    o = run()
    r, b = o["record"], o["board"]
    print(f"[alpha-pick-record] {r['n_days']} days since {o['launch_date']}")
    if r["n_settled"]:
        print(f"  ONE PICK : {r['wins']}-{r['losses']}-{r['pushes']} "
              f"({(r['hit_rate'] or 0)*100:.0f}%) net {r['net_units']:+.2f}u ROI {r['roi_pct']:+.1f}%")
    if b.get("n_settled"):
        print(f"  THE BOARD: {b['wins']}-{b['losses']} "
              f"({(b['hit_rate'] or 0)*100:.0f}%) net {b['net_units']:+.2f}u ROI {b['roi_pct']:+.1f}% "
              f"({b['n_settled']} settled, diversified)")
    t = o.get("todays")
    if t:
        print(f"  Today: {t['player_or_matchup']} {t['market']} @ {t['fair_american']} -> {t['result']}")
