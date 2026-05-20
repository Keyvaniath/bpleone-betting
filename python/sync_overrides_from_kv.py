"""
EdgeStat -- pull model_overrides from Cloudflare KV (via Worker) and write to
data/model_overrides.json so the pipeline picks them up.

Reads the URL from EDGESTAT_WORKER_URL env var (optional). If not set, this
module is a no-op (the dashboard's clipboard-copy flow still works).

Output: data/model_overrides.json (only updated if newer than local)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, Optional

try:
    from urllib.request import Request, urlopen
except Exception:
    Request = urlopen = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "model_overrides.json")
WORKER_URL_ENV = "EDGESTAT_WORKER_URL"


def _get_remote(url: str) -> Optional[Dict[str, Any]]:
    if not urlopen: return None
    try:
        req = Request(url, headers={"User-Agent": "EdgeStat-Sync/1.0"})
        with urlopen(req, timeout=8) as r:
            data = r.read().decode("utf-8")
            if not data or data == "{}": return None
            return json.loads(data)
    except Exception:
        return None


def run() -> Dict[str, Any]:
    worker_url = os.environ.get(WORKER_URL_ENV)
    if not worker_url:
        return {"status": "SKIP", "reason": f"{WORKER_URL_ENV} not set"}

    endpoint = worker_url.rstrip("/") + "/admin/get-overrides"
    remote = _get_remote(endpoint)
    if not remote:
        return {"status": "NO_DATA", "endpoint": endpoint}

    # Compare to existing local file
    local = {}
    if os.path.exists(OUT):
        try:
            with open(OUT) as f: local = json.load(f) or {}
        except Exception:
            local = {}

    # Use saved_at timestamp to decide
    r_t = remote.get("saved_at") or ""
    l_t = local.get("saved_at") or ""
    if r_t and l_t and r_t <= l_t:
        return {"status": "UP_TO_DATE", "local_saved_at": l_t}

    # Write remote
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(remote, f, indent=2)
    return {"status": "UPDATED", "saved_at": r_t, "version": remote.get("version", 0)}


if __name__ == "__main__":
    r = run()
    print(f"[sync-overrides] {r.get('status')}: {r}")
