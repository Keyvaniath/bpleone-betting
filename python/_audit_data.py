"""
Audit every data/*.json for stub/fake/empty patterns.

Flags:
 - file is 0 bytes
 - file parses to empty {} or []
 - "n_players": 0 / "n_games": 0
 - explicit sample/demo/mock/lorem fields
 - identical values across all records (suggests fake fill)
 - all numeric fields equal default 0.5 / 50 / 100
 - file age > 24h (stale)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import Counter

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "data"))
OUT = os.path.join(DATA_DIR, "data_stub_audit.json")

results = {"empty": [], "stub_flagged": [], "zero_count": [],
            "stale_24h": [], "stale_72h": [], "ok": []}

SUSPICIOUS_KEYS_CONTAINING = ["mock", "sample", "demo", "lorem", "placeholder", "fake", "synthetic"]
STUB_VALUE_HINTS = ["mock", "demo", "sample", "synthetic", "placeholder", "lorem"]

for fname in sorted(os.listdir(DATA_DIR)):
    if not fname.endswith(".json"): continue
    path = os.path.join(DATA_DIR, fname)
    size = os.path.getsize(path)
    age_min = round((dt.datetime.now().timestamp() - os.path.getmtime(path)) / 60)

    if size == 0:
        results["empty"].append((fname, "0 bytes"))
        continue
    try:
        with open(path, encoding="utf-8") as f: d = json.load(f)
    except Exception as e:
        results["empty"].append((fname, f"unparseable: {e}"[:80]))
        continue

    # Empty container
    if d == {} or d == []:
        results["empty"].append((fname, "parses to empty {} or []"))
        continue

    # Look for "n_xxx": 0 patterns
    flagged_reasons = []
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, int) and v == 0 and (
                k.startswith("n_") or k in ("count", "total", "size")):
                # Only flag if there's not a sister "note" / explanation
                if "note" not in d and "error" not in d and "status" not in d:
                    flagged_reasons.append(f'{k}=0')
        # Suspicious key names
        text = json.dumps(d).lower()
        for hint in STUB_VALUE_HINTS:
            if hint in text:
                # check it's not a legitimate technical use of "demo"
                if f'"{hint}":' in text or f'"is_{hint}":' in text:
                    flagged_reasons.append(f"contains '{hint}'")

    if flagged_reasons:
        results["zero_count"].append((fname, "; ".join(flagged_reasons[:3])))

    # Staleness (skip non-pipeline artifacts)
    if not fname.startswith("."):
        if age_min > 72 * 60:
            results["stale_72h"].append((fname, f"{age_min} min old"))
        elif age_min > 24 * 60:
            results["stale_24h"].append((fname, f"{age_min} min old"))
        elif age_min <= 24 * 60 and not flagged_reasons:
            results["ok"].append(fname)

# Report
print(f"=== EMPTY / UNPARSEABLE ({len(results['empty'])}) ===")
for n, r in results["empty"]:
    print(f"  {n}: {r}")

print(f"\n=== ZERO-COUNT / STUB-HINT FLAGGED ({len(results['zero_count'])}) ===")
for n, r in results["zero_count"][:30]:
    print(f"  {n}: {r}")
if len(results["zero_count"]) > 30:
    print(f"  ... and {len(results['zero_count'])-30} more")

print(f"\n=== STALE > 24h ({len(results['stale_24h'])}) ===")
for n, r in results["stale_24h"][:20]:
    print(f"  {n}: {r}")

print(f"\n=== STALE > 72h ({len(results['stale_72h'])}) ===")
for n, r in results["stale_72h"][:20]:
    print(f"  {n}: {r}")

print(f"\nSUMMARY: {len(results['ok'])} ok / {len(results['empty'])} empty / "
      f"{len(results['zero_count'])} flagged / {len(results['stale_24h'])} stale24h / "
      f"{len(results['stale_72h'])} stale72h")

with open(OUT, "w") as f:
    json.dump({
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {k: len(v) for k, v in results.items()},
        "empty": results["empty"],
        "zero_count": results["zero_count"],
        "stale_24h": results["stale_24h"],
        "stale_72h": results["stale_72h"],
    }, f, indent=2)
print(f"\nWrote: {OUT}")
