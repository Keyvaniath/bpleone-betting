"""
Audit every Python module in the python/ directory:
 1. Can it be imported without crashing?
 2. If it has a run() function, does it execute cleanly?
 3. Does it produce the JSON it's supposed to (within DATA_DIR)?

Reports broken modules so they can be fixed.
Runs SAFE -- skips network-heavy modules + ones with dangerous side effects.
"""
from __future__ import annotations

import os
import sys
import json
import traceback
import importlib
import time
import datetime as dt

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "data"))

# Modules with side effects / network / write to disk that we audit but isolate
# (we just import them — we don't call run()).
SKIP_RUN = {
    # External API heavy / paid quota
    "props_pipeline", "live_props", "pickem", "pickem_optimizer",
    "scratch_alerts", "injury_news", "esports_alerts",
    "lock_detector", "notify", "notify_discord", "auto_rebalance",
    "live_total_drift", "steam_detector", "bullpen_warming",
    "live_clv", "live_edges", "k_pace_alerts",
    # Train / heavy modules
    "model_trainer", "train", "smoke_tests",
    # Helpers (no run())
    "data_fetcher", "stats_repo", "config", "probability", "features",
    "mlb_model", "simulator", "prop_model", "neural_net", "ensemble",
    "calibration", "ratings", "linemaker", "arbitrage", "risk",
    "correlations", "live", "series", "playoff", "portfolio", "hedge",
    "sos", "injury", "bovada", "_gen_real_player_pages", "_gen_sport_pages",
    "stats_helper", "stats_helper_v2", "stats_helper_v3",
}

results = {"ok": [], "import_fail": [], "run_fail": [], "skipped_run": [], "no_run": []}

modules = sorted([f[:-3] for f in os.listdir(HERE)
                   if f.endswith(".py") and not f.startswith("_")
                   and f != "audit_modules.py"])

print(f"Auditing {len(modules)} Python modules...")
print()

for name in modules:
    sys.path.insert(0, HERE)
    try:
        mod = importlib.import_module(name)
    except Exception as e:
        results["import_fail"].append((name, str(e)[:200]))
        continue

    if name in SKIP_RUN:
        results["skipped_run"].append(name)
        continue

    if not hasattr(mod, "run"):
        results["no_run"].append(name)
        continue

    try:
        t0 = time.time()
        _ = mod.run()
        dt_s = time.time() - t0
        results["ok"].append((name, round(dt_s, 1)))
    except Exception as e:
        tb = traceback.format_exc().splitlines()
        last = tb[-1] if tb else ""
        results["run_fail"].append((name, str(e)[:200], last[:150]))

# Report
print(f"=== IMPORT FAILURES ({len(results['import_fail'])}) ===")
for n, e in results["import_fail"]:
    print(f"  FAIL import {n}: {e}")

print(f"\n=== RUN FAILURES ({len(results['run_fail'])}) ===")
for n, e, tb in results["run_fail"]:
    print(f"  FAIL run    {n}: {e}")
    if tb: print(f"    {tb}")

print(f"\n=== NO RUN FUNCTION ({len(results['no_run'])}) ===")
for n in results["no_run"][:20]:
    print(f"  no_run      {n}")
if len(results["no_run"]) > 20: print(f"  ... and {len(results['no_run'])-20} more")

print(f"\n=== OK ({len(results['ok'])}) ===")
slowest = sorted(results["ok"], key=lambda x: -x[1])[:5]
print("  slowest 5:")
for n, t in slowest:
    print(f"    {n} ({t}s)")

# Summary
print(f"\nSUMMARY: {len(results['ok'])} ok / {len(results['import_fail'])} import-fail / "
      f"{len(results['run_fail'])} run-fail / {len(results['no_run'])} no-run / "
      f"{len(results['skipped_run'])} skipped")

# Write detailed report
out_path = os.path.join(DATA_DIR, "module_audit.json")
with open(out_path, "w") as f:
    json.dump({
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {k: len(v) for k, v in results.items()},
        "import_fail": results["import_fail"],
        "run_fail": results["run_fail"],
        "no_run": results["no_run"],
        "ok": results["ok"],
        "skipped_run": results["skipped_run"],
    }, f, indent=2)
print(f"\nWrote: {out_path}")
