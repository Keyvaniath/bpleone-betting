"""
EdgeStat -- Global pick-counts widget.

Sweeps EVERY *_props.json output and aggregates total strong-edge counts
by sport + category. Designed for the homepage header strip:
  'Tonight: 15 MLB games · 247 strong edges across 165 modules · 3 whales'

Output: data/global_pick_counts.json
  {
    "generated_at": "...",
    "n_modules": 165,
    "by_sport": { "MLB": 187, "NBA": 12, "NHL": 8, ... },
    "totals": { "strong": 247, "whales": 3, "locks": 0, "alpha_picks": 52 }
  }
"""
from __future__ import annotations

import os
import glob
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "global_pick_counts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _sport_of(filename: str) -> str:
    fn = filename.lower()
    if "mlb" in fn or "baseball" in fn: return "MLB"
    if "nba" in fn: return "NBA"
    if "wnba" in fn: return "WNBA"
    if "nhl" in fn: return "NHL"
    if "soccer" in fn or "epl" in fn or "ucl" in fn: return "SOCCER"
    if "tennis" in fn: return "TENNIS"
    if "ufc" in fn or "mma" in fn: return "UFC"
    if "golf" in fn: return "GOLF"
    if "f1" in fn: return "F1"
    return "OTHER"


def run() -> Dict[str, Any]:
    by_sport: Dict[str, int] = {}
    total_strong = 0
    files_scanned = 0

    # Scan all _props.json + related output files
    pattern = os.path.join(DATA_DIR, "*.json")
    for path in glob.glob(pattern):
        fn = os.path.basename(path)
        if not (fn.endswith("_props.json") or fn.endswith("_alt.json") or
                fn.endswith("_yn.json") or fn.endswith("_alerts.json")):
            continue
        d = _load(path)
        if not isinstance(d, dict): continue
        files_scanned += 1
        n_strong = int(d.get("n_strong_edges") or d.get("n_strong") or 0)
        sport = _sport_of(fn)
        by_sport[sport] = by_sport.get(sport, 0) + n_strong
        total_strong += n_strong

    # Pull aggregator counts
    whales = _load(os.path.join(DATA_DIR, "mlb_today_whales.json"))
    locks = _load(os.path.join(DATA_DIR, "mlb_today_locks.json"))
    scanner = _load(os.path.join(DATA_DIR, "cross_sport_alpha_scanner.json"))
    integrity = _load(os.path.join(DATA_DIR, "data_integrity_audit.json"))
    freshness = _load(os.path.join(DATA_DIR, "data_freshness_audit.json"))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "files_scanned": files_scanned,
        "by_sport": dict(sorted(by_sport.items(), key=lambda x: -x[1])),
        "totals": {
            "strong_edges_total": total_strong,
            "whales": whales.get("n_whales", 0),
            "locks": locks.get("n_locks", 0),
            "alpha_picks": scanner.get("n_pure_alpha_picks", 0),
            "confluence_triples": scanner.get("n_confluence_triples", 0),
        },
        "data_health": {
            "integrity_pct": (integrity.get("totals") or {}).get("real_pct"),
            "freshness_pct": freshness.get("freshness_pct"),
            "n_stale_files": freshness.get("n_stale_or_missing"),
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    t = o["totals"]
    print(f"[counts] {o['files_scanned']} files, {t['strong_edges_total']} strong, "
          f"{t['whales']} whales, {t['locks']} locks, {t['alpha_picks']} alpha")
    print(f"  Sport: {o['by_sport']}")
    print(f"  Health: integrity {o['data_health']['integrity_pct']}%, "
          f"freshness {o['data_health']['freshness_pct']}%")
