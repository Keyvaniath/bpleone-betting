"""
EdgeStat master audit -- one command, full health report.

Aggregates: import audit + HTML audit + data stub audit + data_health.

Output: data/audit_master.json + console summary.
Run every wakeup cycle to catch regressions fast.
"""
from __future__ import annotations

import os
import sys
import json
import time
import datetime as dt
import subprocess

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "data"))
OUT = os.path.join(DATA_DIR, "audit_master.json")

t0 = time.time()
results = {"phases": {}}


def _run(name, script):
    print(f"\n=== {name} ===")
    t = time.time()
    p = subprocess.run([sys.executable, os.path.join(HERE, script)],
                        capture_output=True, text=True, timeout=180,
                        cwd=HERE)
    dt_s = round(time.time() - t, 1)
    summary_line = ""
    for line in (p.stdout or "").splitlines():
        if "SUMMARY" in line.upper():
            summary_line = line.strip()
    if not summary_line and (p.stdout or "").splitlines():
        summary_line = (p.stdout or "").splitlines()[-1].strip()
    print(f"  done in {dt_s}s -- {summary_line}")
    results["phases"][name] = {
        "duration_s": dt_s,
        "exit_code": p.returncode,
        "summary": summary_line,
        "stderr_truncated": (p.stderr or "")[-300:],
    }


_run("imports", "_audit_imports.py")
_run("html",    "_audit_html.py")
_run("data",    "_audit_data.py")
_run("data_health", "data_health.py")

results["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
results["total_duration_s"] = round(time.time() - t0, 1)
# Load downstream JSONs for one-shot summary
for f in ("module_import_audit.json", "html_audit.json",
           "data_stub_audit.json", "data_health.json"):
    p = os.path.join(DATA_DIR, f)
    if os.path.exists(p):
        try:
            results.setdefault("artifacts", {})[f] = json.load(open(p))
        except Exception: pass

os.makedirs(DATA_DIR, exist_ok=True)
with open(OUT, "w") as f: json.dump(results, f, indent=2)

print(f"\n========== MASTER AUDIT (took {results['total_duration_s']}s) ==========")
for name, p in results["phases"].items():
    print(f"  {name:15s} exit={p['exit_code']} {p['summary']}")
print(f"\nWrote: {OUT}")
