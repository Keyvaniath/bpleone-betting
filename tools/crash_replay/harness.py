"""Replay the CI python steps in a sandboxed copy of the repo under a data mutation.

usage: python harness.py REPO SANDBOX MODE [workflow ...]
MODE: base   -- data as-is (network blocked)          -> separates network crashes
      offday -- today's-slate style lists emptied     -> "nothing on the board" day
      nulls  -- numeric fields of the first record of every list set to None
Writes SANDBOX/results.jsonl (one line per command).
"""
import json, os, re, shutil, subprocess, sys, time

import yaml

REPO, SB, MODE = sys.argv[1], sys.argv[2], sys.argv[3]
WFS = sys.argv[4:] or ["daily-pipeline", "continuous-heartbeat", "live-games", "training-loop"]

PROTECT = re.compile(r"ledger|archive|history|selections|_log|receipts|backtest|calib|"
                     r"settled|_done|marker|registry|weights|seed|reprice|backfill|"
                     r"scorecard|snapshot|track|record|elo|ratings|_db|mapping|aliases|config", re.I)


def copy_repo():
    if os.path.exists(SB):
        shutil.rmtree(SB)
    shutil.copytree(REPO, SB, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))


def _empty_lists(o, depth=0):
    if isinstance(o, dict):
        return {k: ([] if isinstance(v, list) and depth <= 2 else _empty_lists(v, depth + 1)) for k, v in o.items()}
    return o


def _null_first(o):
    if isinstance(o, dict):
        return {k: _null_first(v) for k, v in o.items()}
    if isinstance(o, list):
        out = [_null_first(v) for v in o]
        if out and isinstance(out[0], dict):
            out[0] = {k: (None if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                      for k, v in out[0].items()}
        return out
    return o


def mutate():
    if MODE == "base":
        return 0
    n = 0
    dd = os.path.join(SB, "data")
    for dp, _, fn in os.walk(dd):
        for f in fn:
            if not f.endswith(".json") or PROTECT.search(f):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, encoding="utf-8") as fh:
                    o = json.load(fh)
            except Exception:
                continue
            o2 = _empty_lists(o) if MODE == "offday" else _null_first(o)
            if o2 != o:
                with open(p, "w", encoding="utf-8") as fh:
                    json.dump(o2, fh)
                n += 1
    return n


PY_RE = re.compile(r"(?:^|[\s;(])python3?\s+(-m\s+\S+|[\w./-]+\.py)([^|&;\n]*)")


def commands():
    out = []
    for wf in WFS:
        y = yaml.safe_load(open(os.path.join(REPO, ".github", "workflows", wf + ".yml"), encoding="utf-8"))
        for job in (y.get("jobs") or {}).values():
            jd = (job.get("defaults") or {}).get("run", {}).get("working-directory")
            for st in job.get("steps") or []:
                run = st.get("run")
                if not run:
                    continue
                wd = st.get("working-directory") or jd or "."
                for m in PY_RE.finditer(run):
                    script, args = m.group(1), m.group(2).strip()
                    if "$" in args or "<<" in run[m.start():m.end() + 3]:
                        args = re.sub(r"\S*\$\S*", "", args).strip()
                    out.append({"wf": wf, "step": st.get("name"), "wd": wd, "cmd": f"{script} {args}".strip()})
    return out


def main():
    copy_repo()
    n_mut = mutate()
    env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", NO_PROXY="",
               PYTHONIOENCODING="utf-8", PYTHONPATH=os.path.join(os.path.dirname(os.path.abspath(__file__)), "site"), PYTHONUTF8="1", GITHUB_ACTIONS="", CI="")
    for k in list(env):
        if any(s in k for s in ("SMTP", "WORKER_URL", "API_KEY", "TOKEN", "WEBHOOK")):
            env.pop(k)
    cmds = commands()
    seen = set()
    res_path = os.path.join(SB, "results.jsonl")
    with open(res_path, "w", encoding="utf-8") as out:
        out.write(json.dumps({"mode": MODE, "mutated_files": n_mut, "n_cmds": len(cmds)}) + "\n")
        for c in cmds:
            key = (c["wd"], c["cmd"])
            if key in seen:
                continue
            seen.add(key)
            t0 = time.time()
            try:
                r = subprocess.run("python " + c["cmd"], shell=True, cwd=os.path.join(SB, c["wd"]),
                                   env=env, capture_output=True, text=True, timeout=90,
                                   encoding="utf-8", errors="replace")
                rc, so, se = r.returncode, r.stdout, r.stderr
            except subprocess.TimeoutExpired as e:
                rc, so, se = "timeout", "", ""
            tb = ""
            if "Traceback" in (se or ""):
                tb = se[se.rfind("Traceback"):][-1500:]
            berr = [l for l in (se or "").splitlines() if l.startswith("[batch] ERROR")]
            c.update(batch_errors=berr, rc=rc, secs=round(time.time() - t0, 1), tb=tb,
                     tail=((se or "")[-400:] if rc not in (0,) and not tb else ""))
            out.write(json.dumps(c) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
