"""Load every root page in headless Edge and report runtime errors (2026-11-16).

check_site_refs.py proves every referenced file is served and check_inline_js.js proves every script
parses; neither runs the page. This does: each page is opened in a throwaway headless Edge profile
(never the user's own browser) and every console line the page logs from its own origin that looks
like a failure is reported: uncaught exceptions, failed resource loads (404/500), JSON parse errors.

Run with the local preview server up (LOCAL-HOSTS / preview :8790):
    python tools/site_sweep.py [base_url] [page ...]      exit 1 if any page logged an error

ESPN answers a "HeadlessEdg" user agent with 403, so a normal desktop Edge user agent is sent.
"""
import concurrent.futures as cf
import os
import re
import shutil
import subprocess
import sys
import tempfile

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BAD = re.compile(r"Uncaught|Failed to load resource|is not defined|is not a function|Cannot read prop|"
                 r"Unexpected token|SyntaxError|TypeError|ReferenceError|blocked by CORS", re.I)
IGNORE = re.compile(r"apple-mobile-web-app-capable|chrome-extension://|favicon\.ico", re.I)


def sweep(base: str, page: str):
    prof = tempfile.mkdtemp(prefix="sweep-")
    try:
        p = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                            f"--user-data-dir={prof}", f"--user-agent={UA}", "--enable-logging=stderr", "--v=0",
                            "--virtual-time-budget=8000", "--dump-dom", f"{base}/{page}"],
                           capture_output=True, timeout=60)
        err = p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return page, ["TIMEOUT: page did not settle in 60s"]
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    out = []
    for ln in err.splitlines():
        if "CONSOLE" not in ln or IGNORE.search(ln) or not BAD.search(ln):
            continue
        m = re.search(r'CONSOLE[^\]]*\] "(.*)", source: (\S+) \((\d+)\)', ln)
        out.append(f"{m.group(1)[:220]}  [{m.group(2).replace(base, '')}:{m.group(3)}]" if m else ln[-260:])
    return page, sorted(set(out))


def main():
    args = sys.argv[1:]
    base = args.pop(0).rstrip("/") if args and args[0].startswith("http") else "http://localhost:8790"
    pages = args or sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))
    bad = 0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for page, errs in ex.map(lambda pg: sweep(base, pg), pages):
            if errs:
                bad += 1
                print(f"\n{page}")
                for e in errs:
                    print("   ", e)
    print(f"\nswept {len(pages)} pages; {bad} with runtime errors")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
