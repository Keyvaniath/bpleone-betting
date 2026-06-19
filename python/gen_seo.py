"""
EdgeStat -- SEO foundation generator (launch readiness, Tier 3).

Idempotent. Run from anywhere:
  * Writes robots.txt + sitemap.xml at the site root.
  * Injects a baseline <meta description> + Open Graph + Twitter + canonical +
    theme-color block into every page that doesn't already have a description.

Safe to re-run: pages that already carry a description are skipped untouched.
"""
from __future__ import annotations

import os
import re
import glob
import html
import datetime as dt

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = "https://betting.bpleone.com"

# Internal / non-indexable pages kept out of the sitemap (and robots Disallow).
NOINDEX = {
    "widget.html", "admin.html", "config.html", "model-control.html",
}

BRAND_DESC = ("EdgeStat — quantitative sports-betting analytics: model edges, calibrated "
              "probabilities, and an honest settled track record across MLB, NBA, NHL, golf, "
              "tennis, soccer and more. Informational only, 21+.")


def _title(htmltext: str) -> str:
    m = re.search(r"<title>(.*?)</title>", htmltext, re.I | re.S)
    return (m.group(1).strip() if m else "EdgeStat").replace("\n", " ")


def _desc_for(title: str) -> str:
    topic = re.sub(r"\s*[\|\-–]\s*EdgeStat.*$", "", title).strip()
    if not topic or topic.lower() == "edgestat":
        return BRAND_DESC
    return f"{topic} · {BRAND_DESC}"


def _seo_block(title: str, fname: str) -> str:
    desc = html.escape(_desc_for(title), quote=True)
    ot = html.escape(title, quote=True)
    url = f"{SITE}/{fname}"
    return (
        f'\n<meta name="description" content="{desc}">'
        f'\n<link rel="canonical" href="{url}">'
        f'\n<meta name="theme-color" content="#0d1017">'
        f'\n<meta property="og:type" content="website">'
        f'\n<meta property="og:site_name" content="EdgeStat">'
        f'\n<meta property="og:title" content="{ot}">'
        f'\n<meta property="og:description" content="{desc}">'
        f'\n<meta property="og:url" content="{url}">'
        f'\n<meta name="twitter:card" content="summary">'
        f'\n<meta name="twitter:title" content="{ot}">'
        f'\n<meta name="twitter:description" content="{desc}">'
    )


def inject_meta() -> int:
    n = 0
    for path in glob.glob(os.path.join(ROOT, "*.html")):
        fname = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            t = f.read()
        if re.search(r'name=["\']description["\']', t, re.I):
            continue  # already has SEO -> leave it
        block = _seo_block(_title(t), fname)
        # Insert after the viewport meta if present, else right after <head>.
        vp = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*>', t, re.I)
        if vp:
            t = t[:vp.end()] + block + t[vp.end():]
        else:
            t = re.sub(r"(<head[^>]*>)", r"\1" + block, t, count=1, flags=re.I)
        with open(path, "w", encoding="utf-8") as f:
            f.write(t)
        n += 1
    return n


def gen_robots() -> None:
    lines = ["User-agent: *", "Allow: /"]
    for p in sorted(NOINDEX):
        lines.append(f"Disallow: /{p}")
    lines += ["", f"Sitemap: {SITE}/sitemap.xml", ""]
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def gen_sitemap() -> int:
    today = dt.date.today().isoformat()
    pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.html")))
    pages = [p for p in pages if p not in NOINDEX]
    # index first, then alphabetical
    pages.sort(key=lambda p: (p != "index.html", p))
    urls = []
    for p in pages:
        loc = SITE + ("/" if p == "index.html" else "/" + p)
        pri = "1.0" if p == "index.html" else "0.6"
        urls.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod><priority>{pri}</priority></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return len(pages)


if __name__ == "__main__":
    injected = inject_meta()
    gen_robots()
    n_pages = gen_sitemap()
    print(f"[seo] injected meta into {injected} page(s); sitemap has {n_pages} urls; robots.txt written")
