"""
EdgeStat -- PROP closing-line value (CLV) capture.

The track record's edge concentrates in player props, but CLV -- the #1 leading
indicator of real skill -- was only ever captured on game moneylines (clv.py),
so the prop edge that the whole record rests on was unconfirmed by the close.
This closes that gap: it snapshots props.json open->close and computes per-prop
CLV exactly the way clv.py does for game lines.

  CLV_pp = (no_vig_implied_close - no_vig_implied_open) * 100   [our bet side]

A positive average CLV means our prop picks consistently beat the closing line --
the market moved toward our side after we posted -- which confirms edge in weeks
rather than the months a win-rate sample needs.

Lifecycle (mirrors clv.py; driven by the Daily MLB Pipeline 6 AM / 6 PM crons):
  1. capture_prop_snapshots(): freeze history/{date}_props_open.json once per
     slate date (write-once, never clobbered) and refresh
     history/{date}_props_close.json every run (always-latest -> converges to the
     true closing line as the day's reruns pull it toward game time).
  2. compute_prop_clv_for_date(): no-vig implied(close) - implied(open) per prop,
     on OUR bet side. Same-line only -- a line move (over 1.5 -> over 2.5) is a
     different bet, so it is flagged and excluded from the averaged CLV, never
     fudged into a cross-line number.
  3. append to data/prop_clv_log.json (idempotent per date) and write the
     data/prop_clv.json rollup (overall + recommended-only + by-market).

Forward-looking by nature: CLV needs an open->close gap, so a prop first seen
this evening shows ~0 today and accrues as future mornings freeze a real open.
We never fabricate a close we did not observe.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
LOG_PATH = os.path.join(DATA_DIR, "prop_clv_log.json")
OUT_PATH = os.path.join(DATA_DIR, "prop_clv.json")

# Keep the log bounded (≈ a season of props).
MAX_LOG_RECORDS = 20000


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def implied_prob(price: Optional[float]) -> Optional[float]:
    """American odds -> raw implied probability (vig included)."""
    if price is None or not isinstance(price, (int, float)):
        return None
    if price >= 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


def _novig_side(over: Optional[float], under: Optional[float], side: str) -> Optional[float]:
    """No-vig implied probability of `side`. With both sides priced we strip the
    vig (the fair, two-way-normalized prob); with only one side priced we fall
    back to the raw implied prob so 1-sided books (Bovada yes/no) still measure."""
    io = implied_prob(over)
    iu = implied_prob(under)
    if side == "over":
        if io is None:
            return None
        if iu is None:
            return io
        return io / (io + iu)
    if side == "under":
        if iu is None:
            return None
        if io is None:
            return iu
        return iu / (io + iu)
    return None


def _pkey(player: str, market: str) -> str:
    return f"{(player or '').strip().lower()}|{(market or '').strip().lower()}"


def _is_play(play: Optional[str]) -> bool:
    """True when the row was a model-recommended play (not a SKIP/pass)."""
    return bool(play) and str(play).strip().upper() not in (
        "SKIP", "PASS", "NO PLAY", "NO_PLAY", "NONE", "")


def _bet_side(prop: Dict[str, Any]) -> Optional[str]:
    """The side we would bet: explicit play if given, else the +edge side."""
    play = (prop.get("play") or "").strip().upper()
    if play in ("OVER", "UNDER"):
        return play.lower()
    eo = prop.get("edge_over_pct")
    eu = prop.get("edge_under_pct")
    eo = eo if isinstance(eo, (int, float)) else -1e9
    eu = eu if isinstance(eu, (int, float)) else -1e9
    if eo <= -1e8 and eu <= -1e8:
        return None
    return "over" if eo >= eu else "under"


def _prop_snapshot(props_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten props.json into a minimal per-prop snapshot (line-only, no debug)."""
    book = props_doc.get("book")
    rows: List[Dict[str, Any]] = []
    for g in (props_doc.get("games") or []):
        matchup = g.get("matchup")
        commence = g.get("commence_time")
        for p in (g.get("props") or []):
            player = p.get("player")
            market = p.get("market")
            if not player or not market:
                continue
            rows.append({
                "key": _pkey(player, market),
                "player": player,
                "market": market,
                "line": p.get("line"),
                "over": p.get("dk_over"),
                "under": p.get("dk_under"),
                "side": _bet_side(p),
                "edge_pct": p.get("best_edge_pct"),
                "play": p.get("play"),
                "low_confidence": bool(p.get("low_confidence")),
                "matchup": matchup,
                "commence_time": commence,
                "book": book,
            })
    return {
        "captured_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "slate_date": (props_doc.get("generated_at") or "")[:10],
        "book": book,
        "props": rows,
    }


def capture_prop_snapshots(props_doc: Dict[str, Any]) -> Optional[str]:
    """Freeze an OPEN prop snapshot once per slate date (write-once) and refresh a
    CLOSE snapshot every run (always-latest). Returns the slate date or None.

    Identical contract to clv.capture_snapshots: the first lines we see for a
    slate are frozen as 'open' and never clobbered; 'close' converges toward the
    real closing line as the every-few-hours reruns re-capture before game time."""
    rows = props_doc.get("games") or []
    if not rows:
        return None
    date_iso = (props_doc.get("generated_at") or dt.date.today().isoformat())[:10]
    os.makedirs(HISTORY_DIR, exist_ok=True)
    payload = _prop_snapshot(props_doc)
    if not payload["props"]:
        return None
    open_path = os.path.join(HISTORY_DIR, f"{date_iso}_props_open.json")
    close_path = os.path.join(HISTORY_DIR, f"{date_iso}_props_close.json")
    if not os.path.exists(open_path):           # write-once open
        with open(open_path, "w") as f:
            json.dump(payload, f, indent=2)
    with open(close_path, "w") as f:            # always-latest close
        json.dump(payload, f, indent=2)
    return date_iso


def compute_prop_clv_for_date(date_iso: str) -> List[Dict[str, Any]]:
    """Per-prop CLV = no-vig implied(close) - implied(open) on our bet side.

    Joined open<->close by player|market. CLV is computed only when the line is
    unchanged (same bet); a line move is recorded with line_moved=True and a null
    clv_pct so it never contaminates the averaged number."""
    open_blob = _load(os.path.join(HISTORY_DIR, f"{date_iso}_props_open.json"))
    close_blob = (_load(os.path.join(HISTORY_DIR, f"{date_iso}_props_close.json"))
                  or _load(PROPS_PATH))
    if not open_blob.get("props") or not close_blob.get("props"):
        return []

    close_by_key: Dict[str, Dict[str, Any]] = {}
    for cp in close_blob["props"]:
        # Prefer the close row whose line matches an open line; first wins otherwise.
        close_by_key.setdefault(cp["key"], cp)

    out: List[Dict[str, Any]] = []
    for op in open_blob["props"]:
        side = op.get("side")
        if side not in ("over", "under"):
            continue
        cp = close_by_key.get(op["key"])
        if not cp:
            continue
        line_moved = op.get("line") != cp.get("line")
        no_open = _novig_side(op.get("over"), op.get("under"), side)
        no_close = _novig_side(cp.get("over"), cp.get("under"), side)
        rec = {
            "date": date_iso,
            "player": op.get("player"),
            "market": op.get("market"),
            "side": side,
            "line_open": op.get("line"),
            "line_close": cp.get("line"),
            "open_price": op.get(side),
            "close_price": cp.get(side),
            "open_novig_pct": round(no_open * 100, 2) if no_open is not None else None,
            "close_novig_pct": round(no_close * 100, 2) if no_close is not None else None,
            "edge_pct": op.get("edge_pct"),
            "play": op.get("play"),
            "is_play": _is_play(op.get("play")),
            "low_confidence": op.get("low_confidence"),
            "matchup": op.get("matchup"),
            "line_moved": bool(line_moved),
        }
        if (not line_moved) and no_open is not None and no_close is not None:
            rec["clv_pct"] = round((no_close - no_open) * 100, 2)
        else:
            rec["clv_pct"] = None
        out.append(rec)
    return out


def append_prop_clv_log(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Idempotent per-date append into prop_clv_log.json (replaces that date)."""
    log = _load(LOG_PATH) or {"records": [], "last_updated": None}
    if records:
        date = records[0]["date"]
        kept = [r for r in log.get("records", []) if r.get("date") != date]
        log["records"] = (kept + records)[-MAX_LOG_RECORDS:]
    log["last_updated"] = dt.datetime.now().isoformat(timespec="seconds")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
    return log


def _stats(clvs: List[float]) -> Dict[str, Any]:
    if not clvs:
        return {"n": 0, "avg_clv_pct": None, "positive_pct": None,
                "best": None, "worst": None}
    return {
        "n": len(clvs),
        "avg_clv_pct": round(sum(clvs) / len(clvs), 3),
        "positive_pct": round(sum(1 for c in clvs if c > 0) / len(clvs) * 100, 1),
        "best": round(max(clvs), 2),
        "worst": round(min(clvs), 2),
    }


def aggregate(log: Dict[str, Any]) -> Dict[str, Any]:
    records = log.get("records", [])
    scored = [r for r in records if r.get("clv_pct") is not None]
    clvs_all = [r["clv_pct"] for r in scored]
    clvs_play = [r["clv_pct"] for r in scored if r.get("is_play")]

    by_market: Dict[str, List[float]] = {}
    for r in scored:
        by_market.setdefault(r.get("market") or "?", []).append(r["clv_pct"])
    by_market_rows = [{"market": m, "n": len(v), "avg_clv_pct": round(sum(v) / len(v), 2)}
                      for m, v in by_market.items()]
    by_market_rows.sort(key=lambda x: -x["avg_clv_pct"])

    return {
        "overall": _stats(clvs_all),
        "recommended_plays": _stats(clvs_play),
        "by_market": by_market_rows,
        "n_records_total": len(records),
        "n_line_moves": sum(1 for r in records if r.get("line_moved")),
        "n_pending_clv": sum(1 for r in records if r.get("clv_pct") is None
                             and not r.get("line_moved")),
        # How many scored props actually have an open->close gap yet. 0 means
        # every capture is still same-snapshot (open==close) -> the UI should say
        # "accruing", not "0% beat close".
        "n_with_movement": sum(1 for c in clvs_all if c != 0),
    }


def run() -> Dict[str, Any]:
    """Capture open/close prop snapshots for the current slate, recompute its CLV,
    append to the log, and write the rollup. Idempotent -- safe every run."""
    props_doc = _load(PROPS_PATH)
    date_iso = capture_prop_snapshots(props_doc) or dt.date.today().isoformat()
    records = compute_prop_clv_for_date(date_iso)
    log = append_prop_clv_log(records)
    agg = aggregate(log)

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "headline_metric": "avg_clv_pct",
        "slate_date": date_iso,
        "n_props_this_slate": len(records),
        "overall_avg_clv_pct": agg["overall"]["avg_clv_pct"],
        "recommended_avg_clv_pct": agg["recommended_plays"]["avg_clv_pct"],
        "overall": agg["overall"],
        "recommended_plays": agg["recommended_plays"],
        "by_market": agg["by_market"],
        "n_records_total": agg["n_records_total"],
        "n_line_moves": agg["n_line_moves"],
        "n_pending_clv": agg["n_pending_clv"],
        "n_with_movement": agg["n_with_movement"],
        "coverage_note": ("Per-prop CLV = no-vig implied(close) - implied(open) on "
                          "our bet side, joined open->close by player|market for the "
                          "same line. Beating the close (+CLV) confirms the prop edge "
                          "before the win-rate sample is large. CLV is forward-looking: "
                          "it accrues from first capture as the evening run pulls the "
                          "close toward game time; same-day-first-seen props read ~0 "
                          "until a real open->close gap exists. Line moves are tracked "
                          "separately and excluded from the average (a moved line is a "
                          "different bet)."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    ov = o["overall"]
    rp = o["recommended_plays"]
    print(f"[prop-clv] slate {o['slate_date']}: {o['n_props_this_slate']} props captured")
    print(f"  overall:     avg CLV {ov['avg_clv_pct']}  (n={ov['n']}, "
          f"{ov['positive_pct']}% positive)" if ov["n"] else "  overall:     no scored CLV yet")
    print(f"  recommended: avg CLV {rp['avg_clv_pct']}  (n={rp['n']}, "
          f"{rp['positive_pct']}% positive)" if rp["n"] else "  recommended: no scored CLV yet")
    print(f"  log: {o['n_records_total']} records, {o['n_line_moves']} line moves, "
          f"{o['n_pending_clv']} awaiting a close")
