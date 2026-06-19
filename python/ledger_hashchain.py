"""
EdgeStat -- tamper-evident track-record fingerprint (Tier 3 #7).

Makes the public settled record verifiable: each run computes a deterministic
SHA-256 *fingerprint* of every settled pick (pick_id + outcome + payout), then
links it to the previous fingerprint in an append-only **hash chain**. Publishing
the chain head daily means a retroactive edit to ANY past settled result changes
the fingerprint and breaks the chain against the previously published head -- so
the track record can't be quietly rewritten.

Output: data/ledger_hashchain.json
  { generated_at, head, fingerprint, n_settled, n_records, history: [...] }
"""
from __future__ import annotations

import os
import json
import hashlib
import datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "ledger_hashchain.json")
MAX_RECORDS = 400
GENESIS = "0" * 64


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _fingerprint(picks: List[Dict[str, Any]]) -> tuple:
    """Deterministic hash of the settled record. Canonical line per pick:
    pick_id|result|payout_units, sorted by pick_id so order can't change it."""
    rows = []
    for p in picks:
        if not p.get("settled") or p.get("voided"):
            continue
        pid = str(p.get("pick_id") or "")
        if not pid:
            continue
        res = str(p.get("result") or p.get("outcome") or "")
        pay = p.get("payout_units")
        pay = "" if pay is None else f"{float(pay):.4f}"
        rows.append(f"{pid}|{res}|{pay}")
    rows.sort()
    return _sha("\n".join(rows)), len(rows)


def run() -> Dict[str, Any]:
    picks = (_load(LEDGER).get("picks") or [])
    fingerprint, n_settled = _fingerprint(picks)

    prev = _load(OUT)
    history: List[Dict[str, Any]] = prev.get("history") or []
    prev_head = history[-1]["head"] if history else GENESIS
    today = dt.date.today().isoformat()

    # Append a new chain record only when the record actually changed (a new
    # settled outcome) -- so the chain advances with real events, not empty runs.
    last_fp = history[-1]["fingerprint"] if history else None
    if fingerprint != last_fp:
        head = _sha(prev_head + fingerprint)
        history.append({
            "date": today,
            "n_settled": n_settled,
            "fingerprint": fingerprint,
            "prev_head": prev_head,
            "head": head,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        })
    history = history[-MAX_RECORDS:]
    head = history[-1]["head"] if history else GENESIS

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "head": head,
        "fingerprint": fingerprint,
        "n_settled": n_settled,
        "n_records": len(history),
        "algorithm": "sha256(prev_head + sha256(sorted pick_id|result|payout))",
        "note": ("Tamper-evident fingerprint of the public settled record. The head "
                 "changes if any past settled result is altered, so the track record "
                 "cannot be silently rewritten. Monthly immutable archives also live "
                 "in the Worker's R2 (/admin/snapshots)."),
        "history": history,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[ledger-hashchain] {p['n_settled']} settled · {p['n_records']} chain records")
    print(f"  head        {p['head']}")
    print(f"  fingerprint {p['fingerprint']}")
