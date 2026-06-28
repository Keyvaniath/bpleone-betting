"""
Recent-picks digest -> data/recent_picks.json

accuracy.html / learning.html / training.html each downloaded the full 7.4MB
all_picks_ledger.json just to render a "recently settled" list of ~50 rows. This emits
a DROP-IN lighter version of the ledger: every top-level rollup field the ledger carries
(n_settled, hit_rate, net_units, roi_pct, by_sport, by_source, curated, ...) PLUS only
the last 200 settled picks (full objects) and the full settled date_range -- ~150KB vs
7.4MB. Pages repoint their fetch here, keep their summary reads unchanged, render recent
rows from the 200, and read counts/date-range from the carried summary fields.

Runs in the daily pipeline right after all_picks_tracker.py (which builds the ledger).
"""
import json
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "recent_picks.json")
KEEP = 200


def build():
    d = json.load(open(LEDGER, encoding="utf-8"))
    picks = d.get("picks") or []
    settled = [p for p in picks if p.get("settled")]
    settled.sort(key=lambda p: (p.get("date") or "",
                                p.get("recorded_at") or p.get("settled_at") or ""))
    sdates = sorted(p.get("date") for p in settled if p.get("date"))
    # Carry every top-level rollup field (everything except the heavy per-pick array)...
    out = {k: v for k, v in d.items() if k != "picks"}
    # ...then attach only the most recent settled picks + the FULL settled span.
    out["picks"] = settled[-KEEP:]
    out["recent_window"] = KEEP
    out["date_range"] = [sdates[0], sdates[-1]] if sdates else [None, None]
    out["digest_generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    return out


def write_artifact():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return payload


if __name__ == "__main__":
    p = write_artifact()
    sz = os.path.getsize(OUT) / 1024
    print(f"Wrote {OUT} ({sz:.0f} KB) | {len(p['picks'])} recent picks | "
          f"n_settled={p.get('n_settled')} | range {p.get('date_range')}")
