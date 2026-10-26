# crash_replay -- replay every CI module on a bad day (2026-10-26)

    python tools/crash_replay/harness.py . <sandbox_dir> base|offday|nulls
    python tools/crash_replay/report.py <parent_of_run_dirs>   # expects run_base/ run_offday/ run_nulls/

harness.py copies the repo to <sandbox_dir>, mutates data/ (offday = slate
lists emptied; nulls = numeric fields of each list's first record -> None),
then runs every `python X.py` in daily-pipeline / heartbeat / live-games /
training-loop with sockets denied and sleep no-op'd (site/sitecustomize.py).
Expected residue: outcomes.py + smoke_tests.py (they need the network).

scan_getnum.py [--fix]  finds `d.get(k, NUM)` feeding math / compares /
                        assignments and rewrites it None-safe.
verify_ast.py <repo>    proves a rewrite is purely mechanical (HEAD + rewrite
                        == working tree at the AST level) and lists files
                        with any other change.

crawl_site.py <repo> <outdir> https://betting.bpleone.com
                        renders every page headless (Chrome --dump-dom); lists
                        console errors + visible NaN/undefined/null leaks.
                        (sw.js CacheStorage errors there are a headless artifact.)
