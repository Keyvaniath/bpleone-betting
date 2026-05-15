"""
EdgeStat -- Sleeper Picks integration scaffold.

Sleeper's player-prop board ("Picks", formerly "Lines") is auth-gated. Their
public `https://api.sleeper.com/picks/mlb` endpoint returns an SPA HTML shell
instead of JSON; the actual lines are loaded client-side after a Bearer token
authenticates against their GraphQL.

When Brandon hands over a Sleeper token from his account:

  export SLEEPER_TOKEN=eyJ0eXAi...

This module pulls today's MLB lines, normalizes them into the same shape as
pickem.py's PrizePicks output, runs our model at Sleeper's line, and writes
data/sleeper.json side-by-side with data/pickem.json.

For now: writes an empty payload with a 'needs_auth' warning so the UI knows
to render the 'connect Sleeper account' prompt.

Auth flow Brandon will need (one-time):
  1. Log in to https://sleeper.com on web in incognito
  2. Open devtools -> Network -> filter 'graphql'
  3. Copy any request's `authorization: Bearer ...` header value
  4. Save to GitHub repo secret SLEEPER_TOKEN
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sleeper.json")


# Sleeper GraphQL endpoint (discovered via devtools; subject to change).
GQL_ENDPOINT = "https://sleeper.com/graphql"

# Known stat type mappings -- adjust once we have a sample auth response.
STAT_MAP = {
    "pitcher_strikeouts": "pitcher_strikeouts",
    "hits": "batter_hits",
    "total_bases": "batter_total_bases",
    "home_runs": "batter_home_runs",
}

QUERY_PROJECTIONS = """
query Projections($sport: String!) {
  projections(sport: $sport) {
    id
    player_id
    player_name
    team
    stat_type
    line
    over_payout
    under_payout
    start_time
    status
  }
}
""".strip()


def fetch_projections(token: str) -> List[Dict[str, Any]]:
    """Pull today's MLB picks from Sleeper. Returns [] on auth failure / unknown shape."""
    if not token or requests is None:
        return []
    try:
        r = requests.post(
            GQL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "edgestat/1.0",
            },
            json={"query": QUERY_PROJECTIONS, "variables": {"sport": "mlb"}},
            timeout=15,
        )
        if not r.ok:
            return []
        body = r.json()
        return (body.get("data") or {}).get("projections") or []
    except Exception:
        return []


def build_payload() -> Dict[str, Any]:
    token = os.environ.get("SLEEPER_TOKEN", "")
    if not token:
        return {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "book": "sleeper",
            "warning": "needs_auth",
            "instructions": ("Set SLEEPER_TOKEN env / repo secret to enable. "
                             "See python/sleeper.py docstring for how to capture it."),
            "props": [],
        }

    projections = fetch_projections(token)
    # Try to match each Sleeper projection to a DK prop in our existing props.json.
    dk_path = os.path.join(os.path.dirname(__file__), "..", "data", "props.json")
    dk_props: List[Dict[str, Any]] = []
    if os.path.exists(dk_path):
        try:
            with open(dk_path) as f:
                dk_props = json.load(f).get("top_edges", [])
        except Exception:
            pass
    try:
        from props_pipeline import resolve_player_id
    except Exception:
        resolve_player_id = lambda name: None  # noqa

    # Build a (mlb_pid, market) -> DK prop index
    dk_index: Dict[Any, Dict[str, Any]] = {}
    for r in dk_props:
        if r.get("player_id") and r.get("market"):
            dk_index[(r["player_id"], r["market"])] = r

    out = []
    for p in projections:
        market = STAT_MAP.get((p.get("stat_type") or "").lower())
        if not market:
            continue
        pid = resolve_player_id(p.get("player_name") or "")
        if not pid:
            continue
        dk = dk_index.get((pid, market))
        out.append({
            "player": p.get("player_name"),
            "team": p.get("team"),
            "player_id": pid,
            "market": market,
            "sleeper_line": p.get("line"),
            "dk_line": dk.get("line") if dk else None,
            "delta": (p.get("line", 0) - dk.get("line", 0)) if dk and p.get("line") is not None else None,
            "over_payout": p.get("over_payout"),
            "under_payout": p.get("under_payout"),
        })

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "book": "sleeper",
        "raw_projections": len(projections),
        "matched_to_dk": sum(1 for p in out if p.get("dk_line") is not None),
        "props": out,
    }


def write_payload(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    if payload.get("warning") == "needs_auth":
        print(f"Wrote sleeper -> {path} (needs_auth, no token set)")
    else:
        print(f"Wrote sleeper -> {path}")
        print(f"  Raw projections: {payload.get('raw_projections', 0)}")
        print(f"  Matched to DK: {payload.get('matched_to_dk', 0)}")


if __name__ == "__main__":
    write_payload(build_payload())
