"""
EdgeStat -- multi-sport POT/POD history rollup.

Aggregates every sport's track record into a single unified record:
  - pod_history.json (MLB)
  - golf_pot_history.json (PGA)
  - lol_pot_history.json (LoL esports)
  - cs_pot_history.json (CS esports)
  - kbo_pot_history.json (KBO)

Outputs combined hit rate, ROI, net units across the entire flagship-pick
portfolio. Powers the unified track record page.

Output: data/multi_sport_pot_rollup.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "multi_sport_pot_rollup.json")

SOURCES = [
    ("MLB",  "pod_history.json"),
    ("GOLF", "golf_pot_history.json"),
    ("LOL",  "lol_pot_history.json"),
    ("CS",   "cs_pot_history.json"),
    ("KBO",  "kbo_pot_history.json"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    by_sport: Dict[str, Any] = {}
    combined_settled = []
    combined_pending = []

    for sport, filename in SOURCES:
        d = _load(os.path.join(DATA_DIR, filename))
        hist = d.get("history") or []
        settled = [h for h in hist if h.get("settled")]
        pending = [h for h in hist if not h.get("settled")]
        combined_settled.extend([{**h, "sport": sport} for h in settled])
        combined_pending.extend([{**h, "sport": sport} for h in pending])

        wins = sum(1 for h in settled if h.get("outcome") == "WIN")
        net = sum(h.get("pl_units", 0) for h in settled)
        by_sport[sport] = {
            "total": len(hist),
            "settled": len(settled),
            "pending": len(pending),
            "wins": wins,
            "losses": len(settled) - wins,
            "hit_rate": round(wins / len(settled), 4) if settled else None,
            "net_units": round(net, 2),
            "roi_pct": round((net / len(settled)) * 100, 2) if settled else 0,
        }

    # Combined totals
    total_settled = len(combined_settled)
    total_wins = sum(1 for h in combined_settled if h.get("outcome") == "WIN")
    total_net = sum(h.get("pl_units", 0) for h in combined_settled)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_sports_tracked": len(by_sport),
        "by_sport": by_sport,
        "combined": {
            "total_picks": total_settled + len(combined_pending),
            "settled": total_settled,
            "pending": len(combined_pending),
            "wins": total_wins,
            "losses": total_settled - total_wins,
            "hit_rate": round(total_wins / total_settled, 4) if total_settled else None,
            "net_units": round(total_net, 2),
            "roi_pct": round((total_net / total_settled) * 100, 2) if total_settled else 0,
        },
        "recent_history": sorted(combined_settled + combined_pending,
                                  key=lambda h: h.get("date", ""), reverse=True)[:40],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    c = p["combined"]
    print(f"Multi-sport POT/POD rollup: {c['total_picks']} picks ({c['settled']} settled, {c['pending']} pending)")
    if c["settled"]:
        print(f"  Combined hit rate: {(c['hit_rate'] or 0)*100:.1f}%  Net: {c['net_units']:+.2f}u  ROI: {c['roi_pct']:+.2f}%")
    print(f"  By sport:")
    for sport, data in p["by_sport"].items():
        print(f"    {sport:5}: {data['settled']:3} settled, {data['pending']:3} pending, hit {((data.get('hit_rate') or 0)*100):4.1f}%")
