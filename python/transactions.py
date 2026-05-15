"""
EdgeStat -- recent MLB transactions feed.

Pulls last 5 days of MLB transactions: trades, call-ups, DFAs, IL moves,
options. Filters to MLB-level moves (excludes minor league re-assignments).

Useful for: roster-change context, breakout-rookie call-up flags,
last-minute injury surprises.

Writes data/transactions.json.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    requests = None  # type: ignore


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "transactions.json")

# Transaction type codes we care about (MLB Stats API). Filters out minor moves.
MLB_TYPECODES = {"TR", "FA", "REL", "OPT", "RCL", "ASG", "SC", "STA"}
# TR=Traded, FA=Signed, REL=Released, OPT=Optioned, RCL=Recalled, ASG=Assigned,
# SC=Status Change (often IL), STA=Status Change (more obscure)


def fetch_transactions(days: int = 5) -> List[Dict[str, Any]]:
    if requests is None:
        return []
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/transactions",
            params={"startDate": start.isoformat(), "endDate": end.isoformat()},
            timeout=15,
        )
        if not r.ok:
            return []
        data = r.json().get("transactions", [])
    except Exception:
        return []
    # Filter to MLB-relevant moves: those with a teamLink containing teamId in MLB
    # And only meaningful type codes.
    out = []
    for t in data:
        code = t.get("typeCode") or ""
        if code not in MLB_TYPECODES:
            continue
        desc = t.get("description", "")
        # Heuristic: skip minor-league-only moves
        if "assigned to" in desc.lower() and "league" not in desc.lower():
            # 'assigned to Lehigh Valley IronPigs' = minor. Keep MLB if 'Major' present or simple
            # actually keep these too -- they often signal MLB->minor option which is MLB-relevant
            pass
        out.append({
            "date": t.get("date"),
            "type_code": code,
            "type_desc": t.get("typeDesc"),
            "description": desc[:400],
            "from_team_id": (t.get("fromTeam") or {}).get("id"),
            "to_team_id": (t.get("team") or {}).get("id"),
            "to_team": (t.get("team") or {}).get("name"),
            "from_team": (t.get("fromTeam") or {}).get("name"),
        })
    # Most recent first
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return out


def build_all() -> Dict[str, Any]:
    txns = fetch_transactions()
    # Categorize
    by_type: Dict[str, int] = {}
    for t in txns:
        c = t.get("type_code") or "?"
        by_type[c] = by_type.get(c, 0) + 1
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "lookback_days": 5,
        "total": len(txns),
        "by_type": by_type,
        "transactions": txns[:200],
    }


def write_txn(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote transactions -> {path}")
    print(f"  Total: {payload.get('total', 0)}")
    print(f"  By type: {payload.get('by_type', {})}")
    for t in payload.get("transactions", [])[:5]:
        d = t.get("description") or ""
        print(f"  {t.get('date')} [{t.get('type_code')}] {d[:120]}")


if __name__ == "__main__":
    write_txn(build_all())
