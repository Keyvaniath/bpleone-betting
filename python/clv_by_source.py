"""
EdgeStat -- CLV by source (the headline credibility metric).

Closing Line Value is the #1 leading indicator of long-term skill: it shows up
in weeks, where win-rate needs months to be significant. This joins the
closing-line log (open vs close on game moneylines) to the settled-pick ledger
by matchup + side, then aggregates average CLV per source.

Coverage note: CLV capture currently covers game MONEYLINES (the lines we snapshot
open->close). Player props don't have closing-line capture yet, so prop-only
sources show "no CLV coverage" rather than a fake number. As prop closing-line
capture is added, this fills in automatically.

Output: data/clv_by_source.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "clv_by_source.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_matchup(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s*@\s*", "@", s)
    s = re.sub(r"\s*vs\.?\s*", "@", s)
    return s.strip()


def _side_of(market: str) -> str:
    m = (market or "").lower()
    if "home" in m: return "home"
    if "away" in m: return "away"
    return ""


def run() -> Dict[str, Any]:
    clv = _load(os.path.join(DATA_DIR, "clv_log.json"))
    ledger = _load(os.path.join(DATA_DIR, "all_picks_ledger.json"))

    # Index closing-line CLV by (matchup, side) for moneyline records.
    clv_idx: Dict[tuple, float] = {}
    for r in (clv.get("records") or []):
        if r.get("clv_pct") is None:
            continue
        mk = (r.get("market") or "").lower()
        side = "home" if "home" in mk else "away" if "away" in mk else ""
        if not side:
            continue
        key = (_norm_matchup(r.get("matchup")), side)
        # Keep the latest/any value for the key
        clv_idx[key] = float(r.get("clv_pct"))

    by_source: Dict[str, Dict[str, Any]] = {}
    matched = 0
    for p in (ledger.get("picks") or []):
        if not p.get("settled"):
            continue
        side = _side_of(p.get("market"))
        if not side:
            continue  # only game-ML picks are CLV-matchable today
        key = (_norm_matchup(p.get("player_or_matchup")), side)
        if key not in clv_idx:
            continue
        src = p.get("source") or "?"
        b = by_source.setdefault(src, {"n": 0, "sum_clv": 0.0})
        b["n"] += 1
        b["sum_clv"] += clv_idx[key]
        matched += 1

    rows: List[Dict[str, Any]] = []
    all_clv = []
    for src, b in by_source.items():
        if b["n"] <= 0:
            continue
        avg = b["sum_clv"] / b["n"]
        all_clv.append((avg, b["n"]))
        rows.append({
            "source": src,
            "n_clv": b["n"],
            "avg_clv_pct": round(avg, 2),
        })
    rows.sort(key=lambda r: -r["avg_clv_pct"])

    overall = round(sum(a * n for a, n in all_clv) / sum(n for _, n in all_clv), 2) if all_clv else None

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "headline_metric": "avg_clv_pct",
        "overall_avg_clv_pct": overall,
        "n_clv_matched": matched,
        "coverage_note": ("CLV covers game moneylines (open->close snapshots). Prop "
                          "sources show no CLV until prop closing-line capture is "
                          "added. Beating the close (+CLV) is the leading indicator "
                          "of real edge -- it confirms skill before the win-rate "
                          "sample is large."),
        "by_source": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[clv-by-source] overall avg CLV {o['overall_avg_clv_pct']}% "
          f"across {o['n_clv_matched']} matched picks, {len(o['by_source'])} sources")
    for r in o["by_source"][:10]:
        print(f"  {r['source']:24s} avg CLV {r['avg_clv_pct']:+.2f}% (n={r['n_clv']})")
