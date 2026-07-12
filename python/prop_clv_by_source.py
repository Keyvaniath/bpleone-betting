"""
EdgeStat -- PROP closing-line value attributed BY SOURCE.

prop_clv.py measures CLV per prop (by market). This joins those per-prop CLV
records to the unified pick ledger so we can answer the question the whole track
record rests on: does each CURATED source (lock_of_day, top_25_board, whale_*,
sharp_*, ...) actually BEAT THE CLOSE on its props? CLV confirms edge in weeks
where win-rate needs months -- per source, it's the sharpest read on which feeds
carry real alpha.

This is the payoff of the canonical taxonomy: the ledger tags a pick K_OVER_4.5
/ 1_plus_hr while the prop-CLV log tags the same bet pitcher_strikeouts(4.5) /
batter_home_runs -- both now resolve to one mlb_<stat>_<line>_<side> key, so the
join is possible at all. Join key: (canonical_market, player, slate_date).

Output: data/prop_clv_by_source.json
"""
from __future__ import annotations

import os
import json
import collections
import datetime as dt
from typing import Any, Dict, List

try:
    from market_taxonomy import canonical_market, canonical_from_dk_line
except Exception:
    canonical_market = None
    canonical_from_dk_line = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
PROP_CLV_LOG = os.path.join(DATA_DIR, "prop_clv_log.json")
OUT = os.path.join(DATA_DIR, "prop_clv_by_source.json")

# Same curated set as all_picks_tracker -- the featured/recommended feeds.
_CURATED_PREFIXES = ("lock_of_day", "top_25_board", "whale_", "consensus_hit",
                     "sharp_", "mlb_under_alert", "pod")


def _is_curated(src: str) -> bool:
    s = src or ""
    return any(s == pre or s.startswith(pre) for pre in _CURATED_PREFIXES)


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _stats(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"n_clv": 0, "avg_clv_pct": None, "positive_pct": None}
    return {
        "n_clv": len(vals),
        "avg_clv_pct": round(sum(vals) / len(vals), 3),
        "positive_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
    }


def run() -> Dict[str, Any]:
    log = _load(PROP_CLV_LOG)
    ledger = _load(LEDGER)

    # Index every scored prop-CLV record by (canonical, player, date).
    clv_idx: Dict[tuple, float] = {}
    if canonical_from_dk_line is not None:
        for r in (log.get("records") or []):
            if r.get("clv_pct") is None:
                continue
            canon = canonical_from_dk_line(r.get("market"), r.get("line_open"), r.get("side"))
            if not canon:
                continue
            key = (canon, (r.get("player") or "").strip().lower(), r.get("date"))
            clv_idx[key] = r["clv_pct"]      # latest capture wins

    # Attribute each matchable ledger pick's prop CLV to its source.
    by_source: Dict[str, List[float]] = collections.defaultdict(list)
    by_canon: Dict[str, List[float]] = collections.defaultdict(list)
    matched = 0
    if canonical_market is not None and clv_idx:
        for p in (ledger.get("picks") or []):
            if p.get("voided"):
                continue  # duplicate-collapsed copies must not add CLV samples
            canon = canonical_market(p.get("market"))
            if not canon:
                continue
            key = (canon, (p.get("player_or_matchup") or "").strip().lower(), p.get("date"))
            clv = clv_idx.get(key)
            if clv is None:
                continue
            by_source[p.get("source") or "?"].append(clv)
            by_canon[canon].append(clv)
            matched += 1

    src_rows = [{"source": s, "curated": _is_curated(s), **_stats(v)}
                for s, v in by_source.items()]
    src_rows.sort(key=lambda r: (not r["curated"], -(r["n_clv"] or 0)))

    canon_rows = [{"canonical": c, **_stats(v)} for c, v in by_canon.items()]
    canon_rows.sort(key=lambda r: -(r["n_clv"] or 0))

    curated_vals = [v for s, vs in by_source.items() if _is_curated(s) for v in vs]
    all_vals = [v for vs in by_source.values() for v in vs]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "headline_metric": "avg_clv_pct",
        "n_clv_matched": matched,
        "n_prop_clv_records": len(log.get("records") or []),
        "curated": _stats(curated_vals),
        "overall": _stats(all_vals),
        "by_source": src_rows,
        "by_canonical": canon_rows,
        "coverage_note": ("Per-prop CLV joined to the pick ledger by canonical market "
                          "+ player + date (the taxonomy unification is what makes the "
                          "join possible). Covers the prop markets DraftKings posts that "
                          "we both surface and snapshot; it fills in as more slates "
                          "accrue an open->close gap. +CLV per source confirms that feed "
                          "is beating the close -- the leading indicator of real edge."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    cur = o["curated"]
    print(f"[prop-clv-by-source] matched {o['n_clv_matched']} ledger picks to prop CLV "
          f"(from {o['n_prop_clv_records']} records)")
    print(f"  CURATED: avg CLV {cur['avg_clv_pct']} (n={cur['n_clv']}, "
          f"{cur['positive_pct']}% beat close)" if cur["n_clv"] else "  CURATED: no matches yet")
    for r in o["by_source"][:12]:
        tag = "ALPHA" if r["curated"] else "     "
        print(f"  [{tag}] {r['source']:26s} avg CLV {r['avg_clv_pct']}  (n={r['n_clv']})")
