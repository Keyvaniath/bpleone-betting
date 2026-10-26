"""
EdgeStat -- D1 sync.

Push picks from all_picks_ledger.json -> Cloudflare D1 via Worker.
Runs in continuous-heartbeat.yml every 5 min. The D1 table is the
permanent edge-stored history that survives repo commits and serves
the /backtest replayer.

Endpoints used:
  POST {WORKER}/db/log-picks       -- bulk-insert (idempotent)
  POST {WORKER}/db/settle-picks    -- update outcomes for settled picks
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except Exception:
    Request = urlopen = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
WORKER_URL_ENV = "EDGESTAT_WORKER_URL"
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
HISTORY = os.path.join(DATA_DIR, "all_picks_history.json")
SYNC_STATE = os.path.join(DATA_DIR, ".d1_sync_state.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _post(url: str, payload: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
    if not urlopen: return None
    try:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "EdgeStat-Sync/1.0"}
        if os.environ.get("EDGESTAT_SYNC_TOKEN"):   # Worker write auth (SYNC_TOKEN)
            headers["X-EdgeStat-Sync"] = os.environ["EDGESTAT_SYNC_TOKEN"]
        req = Request(url, data=body, method="POST", headers=headers)
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8", errors="ignore")[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


_OUTCOME_MAP = {
    "WON": "WIN", "W": "WIN", "HIT": "WIN", "TRUE": "WIN", "YES": "WIN", "1": "WIN",
    "LOST": "LOSS", "L": "LOSS", "MISS": "LOSS", "FALSE": "LOSS", "NO": "LOSS", "0": "LOSS",
    "PUSHED": "PUSH", "TIE": "PUSH",
    "VOIDED": "VOID", "CANCELLED": "VOID",
}


def _norm_outcome(s: Any) -> str:
    """Map any outcome string to canonical WIN/LOSS/PUSH/VOID/PENDING."""
    if s is None: return "PENDING"
    s = str(s).upper().strip()
    if not s: return "PENDING"
    return _OUTCOME_MAP.get(s, s)


def _get_model_version() -> Optional[str]:
    """Load current model version stamp from data/model_version.json."""
    p = os.path.join(DATA_DIR, "model_version.json")
    if not os.path.exists(p): return None
    try:
        with open(p) as f: return (json.load(f) or {}).get("version")
    except Exception:
        return None


def _normalize_pick(p: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a ledger pick to the D1 schema shape."""
    return {
        "pick_id": p.get("pick_id"),
        "source": p.get("source") or "unknown",
        "sport": p.get("sport") or "MLB",
        "player_or_matchup": p.get("player_or_matchup") or p.get("matchup"),
        "market": p.get("market"),
        "p_predicted": p.get("p_predicted") or p.get("prob"),
        # The REAL book price first (2026-10-26): fair_american is the model's own
        # line -- for a placeholder-priced pick it is the fake -110.
        "entry_odds": p.get("book_american") or p.get("fair_american") or p.get("entry_odds"),
        "fair_odds": p.get("fair_american"),
        "edge_pct": p.get("edge_pct"),
        "tier": p.get("tier"),
        # Normalize outcome: UPPERCASE + map past-tense variants to canonical
        # WIN/LOSS/PUSH/PENDING/VOID (what the SQL filters expect)
        "outcome": "VOID" if p.get("voided") else _norm_outcome(p.get("result") or p.get("outcome") or "PENDING"),
        "date": p.get("date") or dt.datetime.utcnow().strftime("%Y-%m-%d"),
        "created_at": p.get("recorded_at") or p.get("created_at") or dt.datetime.utcnow().isoformat(timespec="seconds"),
        "model_version": _get_model_version(),
        "metadata": {k: v for k, v in p.items() if k not in (
            "pick_id", "source", "sport", "player_or_matchup", "matchup",
            "market", "p_predicted", "prob", "entry_odds", "fair_odds",
            "fair_american", "edge_pct", "tier", "result", "outcome",
            "date", "recorded_at", "created_at"
        )},
    }


# Time-boxed, incremental (2026-10-26). The old run re-sent the WHOLE ledger
# (15k picks = ~150 serial requests) every heartbeat inside a 1-minute step
# budget: it never finished, the settle pass (which ran after every insert)
# never ran, and D1 froze at the 6/28 sync. Now only picks whose outcome /
# payout / price changed since their last successful sync are sent, insert +
# settle per chunk, progress is saved after every chunk, and the run stops
# itself well inside the step timeout -- a backlog drains over several runs
# instead of restarting from zero each time.
DIGEST = os.path.join(DATA_DIR, ".d1_sync_digest.json")
BUDGET_S = 30.0          # worst chunk = 2 x 12s requests, inside the 1-min step
CHUNK = 100
STALL_RED_H = 24          # exit nonzero (red heartbeat) only after a day with no progress


def _sig(p: Dict[str, Any]) -> str:
    import hashlib
    m = p.get("metadata") or {}
    raw = json.dumps([p.get("outcome"), m.get("payout_units"), p.get("entry_odds"),
                      m.get("closing_odds")], default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _key(pid: str) -> str:
    import hashlib
    return hashlib.sha1(pid.encode("utf-8")).hexdigest()[:12]


def _ok(r: Optional[Dict[str, Any]]) -> bool:
    return bool(r) and bool(r.get("ok")) and not r.get("error") and not r.get("http_error")


def run() -> Dict[str, Any]:
    import time
    t0 = time.monotonic()
    worker_url = os.environ.get(WORKER_URL_ENV)
    if not worker_url:
        return {"status": "SKIP", "reason": f"{WORKER_URL_ENV} not set"}

    ledger = _load(LEDGER)
    history = _load(HISTORY)
    all_picks = []
    if isinstance(ledger.get("picks"), list):
        all_picks.extend(ledger["picks"])
    elif isinstance(ledger.get("by_pick_id"), dict):
        all_picks.extend(ledger["by_pick_id"].values())
    if isinstance(history.get("picks"), list):
        all_picks.extend(history["picks"])
    elif isinstance(history, list):
        all_picks.extend(history)

    # Dedupe by pick_id and keep latest version (settled beats pending)
    by_id: Dict[str, Dict[str, Any]] = {}
    for p in all_picks:
        pid = p.get("pick_id")
        if not pid: continue
        existing = by_id.get(pid)
        if existing and (existing.get("result") or existing.get("outcome")) not in (None, "PENDING", "pending"):
            continue
        by_id[pid] = p

    picks = [_normalize_pick(p) for p in by_id.values() if p.get("pick_id")]
    if not picks:
        return {"status": "NO_PICKS", "n": 0}

    digest = _load(DIGEST) or {}
    prev = _load(SYNC_STATE)
    todo = [p for p in picks if digest.get(_key(p["pick_id"])) != _sig(p)]
    # Settled first: outcomes are what the replayer reads.
    todo.sort(key=lambda p: (p["outcome"] == "PENDING", str(p.get("date") or "")))

    n_ins = n_set = n_done = 0
    errors: List[Any] = []
    for i in range(0, len(todo), CHUNK):
        if time.monotonic() - t0 > BUDGET_S:
            break
        chunk = todo[i:i + CHUNK]
        r = _post(f"{worker_url}/db/log-picks", {"picks": chunk}, timeout=12.0)
        if not _ok(r):
            errors.append(r); break
        n_ins += int(r.get("inserted") or 0)
        sets = [{"pick_id": p["pick_id"], "outcome": p["outcome"],
                 "payout_units": (p.get("metadata") or {}).get("payout_units"),
                 "closing_odds": (p.get("metadata") or {}).get("closing_odds"),
                 "settled_at": (p.get("metadata") or {}).get("settled_at")}
                for p in chunk if p["outcome"] in ("WIN", "LOSS", "PUSH", "VOID")]
        if sets:
            r2 = _post(f"{worker_url}/db/settle-picks", {"settlements": sets}, timeout=12.0)
            if not _ok(r2):
                errors.append(r2); break
            n_set += int(r2.get("updated") or 0)
        for p in chunk:
            digest[_key(p["pick_id"])] = _sig(p)
        n_done += len(chunk)
        with open(DIGEST, "w") as f: json.dump(digest, f, separators=(",", ":"), sort_keys=True)

    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    backlog = len(todo) - n_done
    last_progress = now if (n_done or not todo) else (prev.get("last_progress") or prev.get("last_sync"))
    state = {
        "last_run": now,
        "last_progress": last_progress,
        "last_sync": now if not backlog else prev.get("last_sync"),
        "n_picks_total": len(picks),
        "n_sent_this_run": n_done,
        "n_inserted_this_run": n_ins,
        "n_settled_this_run": n_set,
        "backlog": backlog,
        "secs": round(time.monotonic() - t0, 1),
        "errors": errors[:3],
        "note": ("Incremental: only picks whose outcome/payout/price changed are sent. The "
                 "Worker's settle only updates rows still PENDING in D1, so a correction to an "
                 "already-settled D1 row (re-price, late void) is sent but not applied there."),
    }
    os.makedirs(os.path.dirname(SYNC_STATE), exist_ok=True)
    with open(SYNC_STATE, "w") as f: json.dump(state, f, indent=2)
    return state


def _stalled(o: Dict[str, Any]) -> bool:
    lp = o.get("last_progress")
    if not o.get("backlog") or not lp:
        return False
    try:
        age = dt.datetime.utcnow() - dt.datetime.fromisoformat(lp)
    except ValueError:
        return False
    return age.total_seconds() > STALL_RED_H * 3600


if __name__ == "__main__":
    import sys
    o = run()
    print(f"[d1-sync] status={o.get('status', 'OK')} sent={o.get('n_sent_this_run', 0)} "
          f"settled={o.get('n_settled_this_run', 0)} backlog={o.get('backlog', 0)} "
          f"secs={o.get('secs')} errors={len(o.get('errors') or [])}")
    if _stalled(o):
        print(f"[d1-sync] NO PROGRESS since {o.get('last_progress')} -- Worker/D1 unreachable?")
        sys.exit(1)
