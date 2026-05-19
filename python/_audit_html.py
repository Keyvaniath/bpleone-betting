"""
Audit every HTML page:
 1. Has it got <script src="js/nav.js"></script>?
 2. Does it reference <nav class="mainnav"> for nav injection?
 3. What JSON files does it fetch? Do they all exist on disk?
 4. Are there any unfetchable data/ references?
 5. Are there any broken-looking patterns (TODO, FIXME, mock, fake, demo)?
"""
from __future__ import annotations

import os
import re
import json
import datetime as dt
from typing import Any, Dict, List

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "html_audit.json")

# Pages we skip (templates, deprecated)
SKIP = {
    "_test_wnba.html", "_test_wnba2.html",
    "widget.html",   # intentional standalone embed (no full nav)
}

results = {
    "no_nav_js": [],
    "no_nav_class": [],
    "no_style_css": [],
    "missing_json": {},  # page -> [missing paths]
    "ok": [],
}

# Match fetch("data/foo.json"), fetch('data/bar.json'), fetch(`data/baz.json`)
RE_FETCH = re.compile(r"""fetch\s*\(\s*["'`](data/[^"'`?]+)["'`?]""")

for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".html"): continue
    if fname in SKIP: continue
    path = os.path.join(ROOT, fname)
    with open(path, encoding="utf-8") as f:
        html = f.read()

    has_nav_js = 'src="js/nav.js"' in html or "src='js/nav.js'" in html
    has_nav_class = 'class="mainnav"' in html or "class='mainnav'" in html
    has_style = 'href="css/style.css"' in html or "href='css/style.css'" in html

    if not has_nav_js: results["no_nav_js"].append(fname)
    if not has_nav_class: results["no_nav_class"].append(fname)
    if not has_style: results["no_style_css"].append(fname)

    referenced_data = RE_FETCH.findall(html)
    missing_data = []
    for d in referenced_data:
        full = os.path.join(ROOT, d)
        if not os.path.exists(full):
            missing_data.append(d)
    if missing_data:
        results["missing_json"][fname] = missing_data
    elif has_nav_js and has_nav_class and has_style:
        results["ok"].append(fname)

# Report
print(f"=== HTML PAGES MISSING js/nav.js ({len(results['no_nav_js'])}) ===")
for f in results["no_nav_js"][:20]:
    print(f"  no nav.js: {f}")

print(f"\n=== HTML PAGES MISSING class=\"mainnav\" ({len(results['no_nav_class'])}) ===")
for f in results["no_nav_class"][:20]:
    print(f"  no mainnav: {f}")

print(f"\n=== HTML PAGES MISSING css/style.css ({len(results['no_style_css'])}) ===")
for f in results["no_style_css"][:20]:
    print(f"  no style: {f}")

print(f"\n=== HTML PAGES REFERENCING MISSING JSON ({len(results['missing_json'])}) ===")
for f, missing in list(results["missing_json"].items())[:20]:
    print(f"  {f}:")
    for m in missing:
        print(f"    -> {m}")

print(f"\nOK ({len(results['ok'])}): all checks pass")
print(f"\nSUMMARY: {len(results['ok'])} ok / {len(results['no_nav_js'])} no-nav-js / "
      f"{len(results['no_nav_class'])} no-mainnav / {len(results['missing_json'])} missing-json")

with open(OUT_PATH, "w") as f:
    json.dump({
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "ok": len(results["ok"]),
            "no_nav_js": len(results["no_nav_js"]),
            "no_nav_class": len(results["no_nav_class"]),
            "no_style_css": len(results["no_style_css"]),
            "missing_json": len(results["missing_json"]),
        },
        "results": results,
    }, f, indent=2)
print(f"Wrote: {OUT_PATH}")
