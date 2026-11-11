"""Every local file a page links to, loads or fetches must be SERVED (2026-11-11).

"Served" means: tracked in git, not excluded by _config.yml (or re-included by
its `include:` list), and with no path segment starting with "_" or "."
(Jekyll never publishes those). The 11/11 merge showed why this needs a check:
the *.md exclude would have hidden three Markdown files two pages fetch.

Scans every root *.html plus js/*.js and sw.js for
  href="..."  src="..."  fetch("...")  fetch('...')  fetch(`...`)
and reports references to local files that are not served. Template-literal
paths with ${...} and absolute URLs are skipped (they cannot be resolved
statically). Data files that only exist after a pipeline run are listed
separately as "generated" when a python module writes them.

Run from the repo root:  python tools/check_site_refs.py        (exit 1 on a dead reference)
"""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# not data-bet-src="NBA" (an attribute that merely ends in src) and not obj.fetch("x") (a method)
REF = re.compile(r"""(?:(?<![\w-])href\s*=\s*|(?<![\w-])src\s*=\s*|(?<![\w.])fetch\(\s*)(["'`])([^"'`]+)\1""")
SKIP_PREFIX = ("http:", "https:", "//", "mailto:", "tel:", "javascript:", "data:", "#", "sms:", "blob:", "about:")


def tracked() -> set:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    return {f for f in out.split("\n") if f}


def config_lists() -> tuple:
    cfg = open(os.path.join(ROOT, "_config.yml"), encoding="utf-8").read()

    def block(name):
        m = re.search(r"^%s:\n((?:\s+-\s+.*\n?)+)" % name, cfg, re.M)
        return [x.strip().strip('"') for x in re.findall(r"-\s+(.+)", m.group(1))] if m else []

    return block("exclude"), block("include")


def served(path: str, files: set, exclude: list, include: list) -> bool:
    if path not in files:
        return False
    base = os.path.basename(path)
    if any(fnmatch.fnmatch(base, i) or fnmatch.fnmatch(path, i) for i in include):
        return True
    if any(seg[:1] in ("_", ".", "#", "~") for seg in path.split("/")):
        return False
    for e in exclude:
        if e.endswith("/"):
            if path.startswith(e):
                return False
        elif fnmatch.fnmatch(path, e) or fnmatch.fnmatch(base, e) or path == e:
            return False
    return True


def main() -> int:
    files = tracked()
    exclude, include = config_lists()
    pages = sorted(f for f in files if "/" not in f and f.endswith(".html"))
    scripts = sorted(f for f in files if (f.startswith("js/") and f.endswith(".js")) or f == "sw.js")
    written = set()
    for f in files:
        if f.startswith("python/") and f.endswith(".py"):
            try:
                src = open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            written.update(re.findall(r"""["']([A-Za-z0-9_.\-]+\.(?:json|md|csv|txt))["']""", src))
    dead, generated, n = [], [], 0
    for f in pages + scripts:
        src = open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read()
        seen = set()
        for m in REF.finditer(src):
            raw = m.group(2).strip()
            if not raw or raw.startswith(SKIP_PREFIX) or "${" in raw or "{{" in raw or "+" in raw or " " in raw:
                continue
            path = raw.split("#", 1)[0].split("?", 1)[0]
            if not path or path.endswith("/"):
                continue
            path = os.path.normpath(path.lstrip("/")).replace("\\", "/")
            if path.startswith("..") or path in seen:
                continue
            seen.add(path)
            n += 1
            if served(path, files, exclude, include):
                continue
            # extensionless page links (/play-of-day) are served by GitHub Pages as the .html file
            if "." not in os.path.basename(path) and served(path + ".html", files, exclude, include):
                continue
            line = src.count("\n", 0, m.start()) + 1
            row = (f, line, raw, "tracked but not served" if path in files else "not in the repo")
            if path.startswith("data/") and path not in files and os.path.basename(path) in written:
                generated.append(row)
            else:
                dead.append(row)
    print(f"checked {n} local references in {len(pages)} pages and {len(scripts)} scripts")
    if generated:
        print(f"{len(generated)} reference(s) to data files a python module writes but that are not committed (page must tolerate a 404):")
        for r in generated[:60]:
            print("   %s:%d  %s" % r[:3])
    if dead:
        print(f"{len(dead)} DEAD reference(s):")
        for r in dead:
            print("   %s:%d  %s  (%s)" % r)
        return 1
    print("no dead references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
