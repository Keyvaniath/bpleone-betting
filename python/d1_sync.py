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
        req = Request(url, data=body, method="POST",
                      headers={"Content-Type": "application/json",
                               "User-Agent": "EdgeStat-Sync/1.0"})
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


def _normalize_pick(p: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a ledger pick to the D1 schema shape."""
    return {
        "pick_id": p.get("pick_id"),
        "source": p.get("source") or "unknown",
        "sport": p.get("sport") or "MLB",
        "player_or_matchup": p.get("player_or_matchup") or p.get("matchup"),
        "market": p.get("market"),
        "p_predicted": p.get("p_predicted") or p.get("prob"),
        "entry_odds": p.get("fair_american") or p.get("entry_odds"),
        "fair_odds": p.get("fair_american"),
        "edge_pct": p.get("edge_pct"),
        "tier": p.get("tier"),
        # Normalize outcome: UPPERCASE + map past-tense variants to canonical
        # WIN/LOSS/PUSH/PENDING/VOID (what the SQL filters expect)
        "outcome": _norm_outcome(p.get("result") or p.get("outcome") or "PENDING"),
        "date": p.get("date") or dt.datetime.utcnow().strftime("%Y-%m-%d"),
        "created_at": p.get("recorded_at") or p.get("created_at") or dt.datetime.utcnow().isoformat(timespec="seconds"),
        "metadata": {k: v for k, v in p.items() if k not in (
            "pick_id", "source", "sport", "player_or_matchup", "matchup",
            "market", "p_predicted", "prob", "entry_odds", "fair_odds",
            "fair_american", "edge_pct", "tier", "result", "outcome",
            "date", "recorded_at", "created_at"
        )},
    }


def run() -> Dict[str, Any]:
    worker_url = os.environ.get(WORKER_URL_ENV)
    if not worker_url:
        return {"status": "SKIP", "reason": f"{WORKER_URL_ENV} not set"}

    # Source picks (both fresh ledger + historical)
    ledger = _load(LEDGER)
    history = _load(HISTORY)

    all_picks = []
    # Today's picks (fresh from ledger)
    if isinstance(ledger.get("picks"), list):
        all_picks.extend(ledger["picks"])
    elif isinstance(ledger.get("by_pick_id"), dict):
        all_picks.extend(ledger["by_pick_id"].values())
    # Historical (older settled picks)
    if isinstance(history.get("picks"), list):
        all_picks.extend(history["picks"])
    elif isinstance(history, list):
        all_picks.extend(history)

    # Dedupe by pick_id and keep latest version (with outcome if available)
    by_id: Dict[str, Dict[str, Any]] = {}
    for p in all_picks:
        pid = p.get("pick_id")
        if not pid: continue
        existing = by_id.get(pid)
        # Prefer settled over pending
        if existing and (existing.get("result") or existing.get("outcome")) not in (None, "PENDING", "pending"):
            continue
        by_id[pid] = p

    picks = [_normalize_pick(p) for p in by_id.values() if p.get("pick_id")]
    if not picks:
        return {"status": "NO_PICKS", "n": 0}

    # Split into pending (insert) and settled (update)
    pending_insert = [p for p in picks if (p.get("outcome") or "").upper() == "PENDING"]
    settled_update = [
        {
            "pick_id": p["pick_id"],
            "outcome": (p["outcome"] or "").upper(),
            "payout_units": p.get("metadata", {}).get("payout_units"),
            "closing_odds": p.get("metadata", {}).get("closing_odds"),
            "settled_at": p.get("metadata", {}).get("settled_at"),
        }
        for p in picks
        if (p.get("outcome") or "").upper() in ("WIN", "LOSS", "PUSH", "VOID")
    ]

    # Bulk insert pending picks (batched to avoid huge payloads)
    insert_results = []
    BATCH = 200
    all_to_log = picks  # log every pick (insert is idempotent via ON CONFLICT)
    for i in range(0, len(all_to_log), BATCH):
        batch = all_to_log[i:i+BATCH]
        r = _post(f"{worker_url}/db/log-picks", {"picks": batch})
        if r: insert_results.append(r)

    # Settle outcomes
    settle_results = []
    if settled_update:
        for i in range(0, len(settled_update), BATCH):
            batch = settled_update[i:i+BATCH]
            r = _post(f"{worker_url}/db/settle-picks", {"settlements": batch})
            if r: settle_results.append(r)

    # Persist sync state
    state = {
        "last_sync": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_picks_synced": len(picks),
        "n_settled_synced": len(settled_update),
        "insert_results": insert_results,
        "settle_results": settle_results,
    }
    os.makedirs(os.path.dirname(SYNC_STATE), exist_ok=True)
    with open(SYNC_STATE, "w") as f: json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    o = run()
    print(f"[d1-sync] status={o.get('status', 'OK')}, picks={o.get('n_picks_synced', 0)}, "
          f"settled={o.get('n_settled_synced', 0)}")
