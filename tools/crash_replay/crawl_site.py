"""Render every page of the live site headless; collect console errors and
visible-text leaks (NaN / undefined / null / [object Object] / Infinity)."""
import concurrent.futures as cf, glob, html, json, os, re, subprocess, sys

REPO, OUT, BASE = sys.argv[1], sys.argv[2], sys.argv[3]
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(REPO, "*.html")))
LEAK = re.compile(r"(?<![\w-])(NaN|undefined|\[object Object\]|-?Infinity)(?![\w-])|(?<![\w\"'-])null(?![\w\"'-])")


def text_of(dom):
    dom = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>", " ", dom)
    dom = re.sub(r"(?is)<!--.*?-->", " ", dom)
    dom = re.sub(r"(?s)<[^>]+>", " ", dom)
    return html.unescape(re.sub(r"\s+", " ", dom))


def run(pg, i):
    prof = os.path.join(OUT, "prof", pg)
    try:
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                            f"--user-data-dir={prof}", "--enable-logging=stderr", "--v=0",
                            "--virtual-time-budget=12000", "--window-size=1280,2000",
                            "--dump-dom", f"{BASE}/{pg}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        dom, err = r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return {"page": pg, "timeout": True}
    cons = []
    for l in err.splitlines():
        if "CONSOLE" in l and ("ERROR" in l or "Uncaught" in l or "Error" in l):
            m = re.search(r'CONSOLE[^\]]*\] "(.*)", source: (\S+) \((\d+)\)', l)
            cons.append(m.group(1)[:220] + " @ " + m.group(2).split("/")[-1] + ":" + m.group(3) if m else l[-220:])
    txt = text_of(dom)
    leaks = []
    for m in LEAK.finditer(txt):
        a = max(0, m.start() - 50); leaks.append(txt[a:m.end() + 40].strip())
    return {"page": pg, "console": cons, "leaks": leaks[:12], "n_leaks": len(leaks), "dom_bytes": len(dom)}


with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda a: run(*a), [(p, i) for i, p in enumerate(pages)]))
json.dump(res, open(os.path.join(OUT, "crawl.json"), "w", encoding="utf-8"), indent=1)
bad = [r for r in res if r.get("timeout") or r.get("console") or r.get("n_leaks")]
print(f"{len(res)} pages; {len(bad)} with issues")
