"""
EdgeStat -- Alpha Pick of the Day track record.

The Alpha Pick of the Day (alpha_pick_of_day.py) surfaces a morning digest: a #1
headline edge play + a 3-5-leg prop slip. This module gives that digest its OWN
verifiable record so the page and homepage band can say "Alpha slip: 14-6, +22%".

How it settles -- the honest way:
  Every leg the digest surfaces is ALSO an entry in the unified settled ledger
  (all_picks_ledger.json), which already grades every pick across every sport.
  So we don't re-settle anything: each morning we SNAPSHOT the day's slip +
  headline (once per slate date), then look each leg up in the ledger by
  (player/matchup, date, family) and inherit its result. Flat 1u per leg, no
  Kelly inflation -- tracking exactly what was called.

The forward record starts at launch (2026-06-17) and grows daily. For immediate
context we also surface the realized ROI of the curated prop pool the slip is
drawn from (ledger_summary by_sport), so the credibility isn't empty on day one.

Output: data/alpha_pod_record.json
"""
from __future__ import annotations

import os
import re
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "alpha_pod_record.json")
SRC = os.path.join(DATA_DIR, "alpha_pick_of_day.json")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
SUMMARY = os.path.join(DATA_DIR, "ledger_summary.json")
MAX_HISTORY = 365


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _amer_to_dec(a) -> Optional[float]:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return None
    return 1 + a / 100 if a >= 0 else 1 + 100 / abs(a)


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _ledger_index() -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Index ledger picks by (normalized player/matchup, date) for fast matching."""
    led = _load(LEDGER)
    idx: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for p in (led.get("picks") or []):
        key = (_norm(p.get("player_or_matchup")), (p.get("date") or "")[:10])
        idx.setdefault(key, []).append(p)
    return idx


def _settle_leg(leg: Dict[str, Any], idx: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> Tuple[str, Optional[float]]:
    """Match one snapshot leg to its ledger pick and inherit the result.
    Returns (result, payout_units_flat_1u). result in won/lost/push/void/pending."""
    name = leg.get("player_or_matchup") or leg.get("player")
    key = (_norm(name), leg.get("date") or "")
    cands = idx.get(key, [])
    if not cands:
        return "pending", None
    fam = _norm(leg.get("market_family"))
    mk = _norm(leg.get("market"))

    def score(p: Dict[str, Any]) -> int:
        s = 0
        src, pm = _norm(p.get("source")), _norm(p.get("market"))
        if fam and (fam in src or fam in pm):
            s += 3
        if mk and (mk in pm or pm in mk):
            s += 2
        if p.get("settled") and not p.get("voided"):
            s += 1
        return s

    best = max(cands, key=score)
    if best.get("voided"):
        return "void", 0.0
    if not best.get("settled"):
        return "pending", None
    res = best.get("result")
    if res == "won":
        dec = _amer_to_dec(leg.get("fair_american")) or 1.91
        return "won", round(dec - 1, 3)
    if res == "lost":
        return "lost", -1.0
    if res in ("push", "void"):
        return res, 0.0
    return "pending", None


def _snapshot_today(src: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build a history entry for today's digest (identity fields only, for matching)."""
    date = src.get("slate_date")
    if not date:
        return None
    a = src.get("alpha_pick") or {}
    headline = None
    if a.get("player_or_matchup"):
        headline = {
            "player_or_matchup": a.get("player_or_matchup"), "team": a.get("team"),
            "sport": a.get("sport"), "market": a.get("market"),
            "market_family": a.get("market_family"), "fair_american": a.get("fair_american"),
            "model_prob": a.get("model_prob"),
            "settled": False, "result": "pending", "payout_units": None,
        }
    slip = []
    for p in (src.get("props_of_day") or []):
        slip.append({
            "player_or_matchup": p.get("player"), "team": p.get("team"),
            "sport": p.get("sport"), "market": p.get("market"),
            "market_family": p.get("market_family"), "fair_american": p.get("fair_american"),
            "prob": p.get("prob"), "date": date,
            "settled": False, "result": "pending", "payout_units": None,
        })
    if headline:
        headline["date"] = date
    if not headline and not slip:
        return None
    return {"date": date, "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
            "headline": headline, "slip": slip}


def _agg(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [l for l in legs if l.get("settled")]
    wins = sum(1 for l in settled if l["result"] == "won")
    losses = sum(1 for l in settled if l["result"] == "lost")
    pushes = sum(1 for l in settled if l["result"] in ("push", "void"))
    decided = wins + losses
    net = round(sum((l.get("payout_units") or 0) for l in settled), 3)
    return {
        "n_settled": len(settled), "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(net / decided * 100, 2) if decided else None,
    }


def run() -> Dict[str, Any]:
    state = _load(OUT)
    history: List[Dict[str, Any]] = state.get("history") or []
    by_date = {h.get("date"): h for h in history}

    src = _load(SRC)
    n_added = 0
    snap_date = src.get("slate_date")
    if snap_date and snap_date not in by_date:
        entry = _snapshot_today(src)
        if entry:
            history.append(entry)
            by_date[snap_date] = entry
            n_added = 1

    # Settle every pending leg from the ledger.
    idx = _ledger_index()
    n_settled_run = 0
    for h in history:
        for leg in ([h.get("headline")] if h.get("headline") else []) + (h.get("slip") or []):
            if leg.get("settled"):
                continue
            res, pay = _settle_leg(leg, idx)
            if res != "pending":
                leg["settled"] = True
                leg["result"] = res
                leg["payout_units"] = pay
                leg["settled_at"] = dt.datetime.now().isoformat(timespec="seconds")
                n_settled_run += 1

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # Aggregate: the slip (all prop legs) is the headline record; the #1 play tracked too.
    all_slip = [leg for h in history for leg in (h.get("slip") or [])]
    all_head = [h["headline"] for h in history if h.get("headline")]
    today = dt.date.today()
    l30_slip = []
    for h in history:
        try:
            if (today - dt.date.fromisoformat(h.get("date"))).days <= 30:
                l30_slip.extend(h.get("slip") or [])
        except Exception:
            continue

    # Curated-prop context (immediate credibility while the forward record builds).
    summ = _load(SUMMARY)
    bysport = (summ.get("by_sport") or {}).get("MLB-PP") or {}
    context = None
    if bysport.get("settled"):
        context = {
            "label": "Curated MLB player-prop pool (all-time, the slip's source)",
            "settled": bysport.get("settled"), "wins": bysport.get("wins"),
            "losses": bysport.get("losses"),
            "hit_rate": bysport.get("hit_rate"), "roi_pct": bysport.get("roi_pct"),
            "net_units": bysport.get("net_units"),
        }

    slip_agg = _agg(all_slip)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "launch_date": history[0]["date"] if history else snap_date,
        "n_days_tracked": len(history),
        "stake_assumption": "1u flat per leg",
        "slip": slip_agg,
        "slip_last_30": _agg(l30_slip),
        "headline": _agg(all_head),
        "curated_context": context,
        "n_added_this_run": n_added,
        "n_settled_this_run": n_settled_run,
        "todays": by_date.get(snap_date),
        "history": history,
        "note": ("Forward track record of the Alpha Pick of the Day. Each morning's "
                 "slip + #1 play is snapshotted once and settled by matching into the "
                 "unified ledger -- flat 1u per leg, tracking exactly what was called. "
                 "Starts at launch and grows daily; curated_context shows the realized "
                 "ROI of the prop pool the slip is drawn from for day-one credibility."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    o = run()
    s = o["slip"]
    print(f"[alpha-record] {o['n_days_tracked']} day(s) tracked since {o['launch_date']} "
          f"(+{o['n_added_this_run']} today, +{o['n_settled_this_run']} legs settled this run)")
    if s["n_settled"]:
        print(f"  Slip legs: {s['wins']}-{s['losses']}-{s['pushes']} ({(s['hit_rate'] or 0)*100:.0f}%) "
              f"net {s['net_units']:+.2f}u ROI {s['roi_pct']:+.1f}%")
    else:
        print("  Slip legs: building (none settled yet)")
    c = o.get("curated_context")
    if c:
        print(f"  Context (curated PP pool): {c['wins']}-{c['losses']} ({(c['hit_rate'] or 0)*100:.0f}%) "
              f"ROI {c['roi_pct']:+.1f}% over {c['settled']} settled")
