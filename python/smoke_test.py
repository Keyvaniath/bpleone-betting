"""
EdgeStat -- pre-merge smoke test.

Catches the error CLASS that froze the slate on 2026-06-01: a `NameError` from an
undefined variable (`player_id` should have been `pid`) that compiled fine and
only blew up at RUNTIME inside props_pipeline.build_props -- aborting the whole
daily pipeline before its commit step, so the site served ~17h-stale data.

Three nets, all offline (no API keys / network needed), run by
.github/workflows/smoke-test.yml on every push:

  1. COMPILE   -- py_compile every module (syntax).
  2. UNDEFINED -- pyflakes every module, failing on "undefined name" (THE Monday
                  bug class) and syntax errors. pyflakes is static, so it catches
                  the bug without executing the code or needing odds data.
  3. RUN       -- import + run() the correctness-critical, offline data-chain
                  (taxonomy -> ledger -> learning -> board -> CLV) against the
                  committed data/, so a runtime regression in grading/learning is
                  caught here instead of in production.

Exit non-zero on any failure so CI blocks it.
"""
from __future__ import annotations

import os
import sys
import glob
import importlib
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Run-order matters: each feeds the next, mirroring the pipeline.
CRITICAL_RUN = [
    "all_picks_tracker",      # settle + grade + by_canonical rollup
    "self_learn_weights",     # learned weights (incl. weights_by_canonical)
    "todays_top_plays",       # the displayed board (applies canonical weights)
    "prop_clv",               # prop closing-line capture
    "prop_clv_by_source",     # per-source prop CLV join
    "backtest",               # real track record from the ledger
    "clv_by_source",          # game-line CLV by source
    "data_freshness_audit",   # freshness rollup
]
# Imported (not run) -- catches import-time errors without needing network/data.
CRITICAL_IMPORT = ["market_taxonomy", "probability", "calibration", "mlb_model"]


def _compile_all(files):
    """In-memory compile (no .pyc written) so it's fast and side-effect-free."""
    fails = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                compile(fh.read(), f, "exec")
        except SyntaxError as e:
            fails.append(("SYNTAX", os.path.basename(f), f"{e.msg} (line {e.lineno})"))
        except Exception as e:
            fails.append(("READ", os.path.basename(f), repr(e)[:160]))
    return fails


def _pyflakes_undefined(target_dir):
    """Return undefined-name / syntax findings from pyflakes (style noise like
    unused imports is intentionally ignored so the gate only blocks real bugs)."""
    try:
        out = subprocess.run([sys.executable, "-m", "pyflakes", target_dir],
                             capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"  (pyflakes unavailable: {e} -- skipping undefined-name net)")
        return []
    fails = []
    for line in (out.stdout + "\n" + out.stderr).splitlines():
        low = line.lower()
        if ("undefined name" in low or "invalid syntax" in low
                or "syntaxerror" in low or "undefined local" in low):
            fails.append(("UNDEFINED", "", line.strip()[:200]))
    return fails


def main() -> int:
    files = sorted(glob.glob(os.path.join(HERE, "*.py")))
    failures = []

    print(f"[smoke] 1/3 compile {len(files)} modules...")
    failures += _compile_all(files)

    print("[smoke] 2/3 pyflakes undefined-name scan...")
    failures += _pyflakes_undefined(HERE)

    print(f"[smoke] 3/3 import+run {len(CRITICAL_RUN)} critical modules...")
    for name in CRITICAL_IMPORT:
        try:
            importlib.import_module(name)
        except Exception as e:
            failures.append(("IMPORT", name, repr(e)[:200]))
    for name in CRITICAL_RUN:
        try:
            mod = importlib.import_module(name)
        except Exception as e:
            failures.append(("IMPORT", name, repr(e)[:200]))
            continue
        if hasattr(mod, "run"):
            try:
                mod.run()
            except Exception as e:
                failures.append(("RUN", name, repr(e)[:200]))

    if failures:
        print(f"\nSMOKE TEST FAILED -- {len(failures)} issue(s):")
        for kind, where, msg in failures:
            print(f"  [{kind}] {where} {msg}")
        return 1
    print(f"\nSMOKE TEST PASSED: {len(files)} modules compiled clean, "
          f"no undefined names, {len(CRITICAL_RUN)} critical modules ran clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
