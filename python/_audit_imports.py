"""
Fast import-only audit. Imports each Python module in python/ and reports
ImportErrors / SyntaxErrors. Does NOT call run() so it's fast (~10s for 200 modules).
"""
from __future__ import annotations
import os
import sys
import json
import traceback
import datetime as dt

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "data"))
sys.path.insert(0, HERE)

results = {"ok": [], "import_fail": []}
mods = sorted([f[:-3] for f in os.listdir(HERE)
                if f.endswith(".py") and not f.startswith("_") and f != "audit_imports.py"])

print(f"Import-auditing {len(mods)} modules...")
for name in mods:
    try:
        __import__(name)
        results["ok"].append(name)
    except Exception as e:
        results["import_fail"].append((name, type(e).__name__, str(e)[:200]))

print(f"\n=== IMPORT FAILURES ({len(results['import_fail'])}) ===")
for n, kind, e in results["import_fail"]:
    print(f"  {kind:15s} {n}: {e}")

print(f"\nSUMMARY: {len(results['ok'])} import-ok / {len(results['import_fail'])} import-fail")

OUT = os.path.join(DATA_DIR, "module_import_audit.json")
with open(OUT, "w") as f:
    json.dump({
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_total": len(mods),
        "n_ok": len(results["ok"]),
        "n_fail": len(results["import_fail"]),
        "failures": results["import_fail"],
    }, f, indent=2)
print(f"Wrote: {OUT}")
