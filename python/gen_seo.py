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
import sys
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


# (2026-11-16 audit) the flagship pages, ranked above the long tail
KEY_PAGES = {"board.html": "0.9", "picks.html": "0.9", "play-of-day.html": "0.9", "tonight.html": "0.8",
             "track-record.html": "0.8", "proof.html": "0.7", "methodology.html": "0.7",
             "nfl.html": "0.7", "nba.html": "0.7", "nhl.html": "0.7"}


def is_indexable(fname: str, htmltext: str) -> bool:
    """A page belongs in the sitemap unless it is internal (NOINDEX), a 404, or itself says noindex or
    redirects (the retired-board stubs do both). (2026-11-16 audit: the old sitemap listed 14 noindex
    redirect stubs and omitted The Board and Today's Picks, because it was generated once and never again.)"""
    head = htmltext[:8000]
    return not (fname in NOINDEX or fname == "404.html"
                or re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', head, re.I)
                or re.search(r'http-equiv=["\']refresh["\']', head, re.I))


def _lastmod(path: str) -> str:
    """The page's last commit date (what changed), else its file date."""
    try:
        import subprocess
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", os.path.basename(path)], cwd=ROOT,
                             capture_output=True, text=True, timeout=20).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


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
        if re.search(r'name=["\']description["\']', t, re.I) or not is_indexable(fname, t):
            continue  # already has SEO, or a redirect stub / internal page -> leave it
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


def sitemap_pages() -> list:
    out = []
    for path in glob.glob(os.path.join(ROOT, "*.html")):
        with open(path, encoding="utf-8", errors="replace") as f:
            if is_indexable(os.path.basename(path), f.read()):
                out.append(os.path.basename(path))
    # index first, then the flagship pages, then alphabetical
    return sorted(out, key=lambda p: (p != "index.html", -float(KEY_PAGES.get(p, "0.6")), p))


def gen_sitemap() -> int:
    pages = sitemap_pages()
    urls = []
    for p in pages:
        loc = SITE + ("/" if p == "index.html" else "/" + p)
        pri = "1.0" if p == "index.html" else KEY_PAGES.get(p, "0.6")
        urls.append(f"  <url><loc>{loc}</loc><lastmod>{_lastmod(os.path.join(ROOT, p))}</lastmod><priority>{pri}</priority></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return len(pages)


if __name__ == "__main__":
    if "--sitemap-only" in sys.argv:
        gen_robots()
        print(f"[seo] sitemap has {gen_sitemap()} urls; robots.txt written")
        sys.exit(0)
    injected = inject_meta()
    gen_robots()
    n_pages = gen_sitemap()
    print(f"[seo] injected meta into {injected} page(s); sitemap has {n_pages} urls; robots.txt written")
