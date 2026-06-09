"""
EdgeStat -- strategy simulator export: the settled ledger as a compact replay deck.

Powers strategy-sim.html: an interactive backtest where every row is a REAL pick the
model surfaced and a REAL outcome from the box score -- no synthetic data. The browser
replays the picks chronologically under user-chosen rules (flat vs fractional Kelly,
raw vs calibrated prob, curation toggles, prob floor, sport filter) and draws the
equity curve that strategy WOULD have produced.

Honesty contract (mirrored in the page banner):
  - This is an IN-SAMPLE historical replay. Choosing filters after seeing the results
    is hindsight; it demonstrates what the calibration layer learned, it does not
    promise forward returns.
  - Payouts replay the ledger's own convention: a win pays decimal(fair_american)-1
    (fallback 1.91), a loss -1, a push 0 -- so "flat 1u, no filters" reproduces the
    public track-record numbers exactly.
  - p_raw is the generator's untouched probability; p_cal is the isotonic-recalibrated
    honest probability (identity where a family lacks settled history).

Output: data/strategy_sim.json  (columnar: ~9 values per settled pick)
  { dates[], sources[{s,cur}], sports[], families[{f,neg,oc}],
    rows[[date_i, source_i, sport_i, family_i, p_raw, p_cal, fair, res, payout]] }
  res: 1=won 0=lost 2=push
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

import prob_calibration as pc
import recalibration as rc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "strategy_sim.json")

# Keep in sync with all_picks_tracker._CURATED_PREFIXES (the "Alpha" rollup).
CURATED_PREFIXES = ("lock_of_day", "top_25_board", "whale_", "consensus_hit",
                    "sharp_", "mlb_under_alert", "pod")


def _is_curated(src: str) -> bool:
    s = src or ""
    return any(s == pre or s.startswith(pre) for pre in CURATED_PREFIXES)


def _f3(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, 3) if 0.0 < x < 1.0 else None


def run() -> Dict[str, Any]:
    pc.reset_caches()
    rc.reset_caches()
    try:
        with open(LEDGER, encoding="utf-8") as f:
            picks = json.load(f).get("picks") or []
    except Exception:
        picks = []

    neg = pc.proven_negative_families()
    oc = pc.overconfident_families()

    settled = [p for p in picks if p.get("result") in ("won", "lost", "push")]
    settled.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))

    dates: List[str] = []
    d_idx: Dict[str, int] = {}
    sources: List[Dict[str, Any]] = []
    s_idx: Dict[str, int] = {}
    sports: List[str] = []
    sp_idx: Dict[str, int] = {}
    fams: List[Dict[str, Any]] = []
    f_idx: Dict[str, int] = {}
    rows: List[List[Any]] = []
    res_code = {"won": 1, "lost": 0, "push": 2}

    for p in settled:
        date = p.get("date") or "?"
        if date not in d_idx:
            d_idx[date] = len(dates)
            dates.append(date)
        src = p.get("source") or "?"
        if src not in s_idx:
            s_idx[src] = len(sources)
            sources.append({"s": src, "cur": 1 if _is_curated(src) else 0})
        sport = (p.get("sport") or "?").upper()
        if sport not in sp_idx:
            sp_idx[sport] = len(sports)
            sports.append(sport)
        fam = pc.canon_market_family(p.get("market"))
        if fam not in f_idx:
            f_idx[fam] = len(fams)
            fams.append({"f": fam, "neg": 1 if fam in neg else 0, "oc": 1 if fam in oc else 0})

        p_raw = _f3(p.get("p_predicted") if p.get("p_predicted") is not None else p.get("prob"))
        p_cal = _f3(p.get("p_calibrated"))
        if p_cal is None and p_raw is not None:
            p_cal = _f3(rc.recalibrate(p_raw, p.get("market")))
        fair = p.get("fair_american")
        fair = int(fair) if isinstance(fair, (int, float)) else None
        payout = p.get("payout_units")
        payout = round(float(payout), 4) if isinstance(payout, (int, float)) else 0.0

        rows.append([d_idx[date], s_idx[src], sp_idx[sport], f_idx[fam],
                     p_raw, p_cal, fair, res_code[p["result"]], payout])

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n": len(rows),
        "n_dates": len(dates),
        "schema": ["date_i", "source_i", "sport_i", "family_i",
                   "p_raw", "p_cal", "fair_american", "res(1w/0l/2push)", "payout_units"],
        "dates": dates,
        "sources": sources,
        "sports": sports,
        "families": fams,
        "rows": rows,
        "note": ("Every row is a real surfaced pick settled against the real box score "
                 "(the public ledger). Win pays decimal(fair)-1 (1.91 fallback), loss -1, "
                 "push 0 -- flat 1u with no filters reproduces the track-record exactly. "
                 "In-sample replay: filters are hindsight, not a forward guarantee."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, separators=(",", ":"))
    return result


if __name__ == "__main__":
    o = run()
    kb = os.path.getsize(OUT) // 1024
    net = round(sum(r[8] for r in o["rows"]), 2)
    w = sum(1 for r in o["rows"] if r[7] == 1)
    l = sum(1 for r in o["rows"] if r[7] == 0)
    print(f"[strategy-sim] {o['n']} settled picks exported ({kb} KB) -> {OUT}")
    print(f"    sanity: {w}-{l}, net {net:+}u flat (should match the ledger headline)")
    print(f"    {len(o['sources'])} sources, {len(o['families'])} families "
          f"({sum(1 for x in o['families'] if x['neg'])} proven-negative, "
          f"{sum(1 for x in o['families'] if x['oc'])} overconfident)")
