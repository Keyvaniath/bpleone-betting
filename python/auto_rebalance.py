"""
EdgeStat -- auto-rebalance trigger when lineups churn.

If lineup_churn.json shows a scratched player AND any of our best_bets
or portfolio picks are on that player, we need to:
  1. Mark those bets STALE in a delta file
  2. Find replacement bets from the next-rank candidates (auto-substitute)
  3. Persist the rebalance event for the audit log

Output: data/rebalance_events.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHURN_PATH = os.path.join(DATA_DIR, "lineup_churn.json")
BB_PATH = os.path.join(DATA_DIR, "best_bets.json")
PORT_PATH = os.path.join(DATA_DIR, "portfolio.json")
OUT_PATH = os.path.join(DATA_DIR, "rebalance_events.json")
HIST_PATH = os.path.join(DATA_DIR, ".rebalance_history.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    churn = _load(CHURN_PATH)
    bb = _load(BB_PATH).get("bets") or []
    port = _load(PORT_PATH).get("picks") or []
    hist = _load(HIST_PATH).get("events") or []

    removed_ids = {r["id"] for r in (churn.get("removed") or [])}
    if not removed_ids:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_affected_picks": 0,
            "rebalanced": [],
            "note": "no lineup churn -- nothing to rebalance",
        }
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # Picks affected
    affected_port = [p for p in port if p.get("player_id") in removed_ids]
    affected_bb = [b for b in bb if b.get("player_id") in removed_ids]

    # Find replacement candidates from best_bets (next candidates not yet picked)
    port_ids = {p.get("player_id") for p in port}
    affected_player_ids = removed_ids
    candidates = [b for b in bb if b.get("player_id") not in port_ids
                                   and b.get("player_id") not in affected_player_ids
                                   and b.get("source") in ("DK", "PP", "NRFI")]
    candidates.sort(key=lambda b: -(b.get("quality_score") or 0))

    rebalanced = []
    cand_idx = 0
    for affected in affected_port:
        if cand_idx >= len(candidates):
            break
        replacement = candidates[cand_idx]
        cand_idx += 1
        rebalanced.append({
            "removed_player_id": affected.get("player_id"),
            "removed_label": affected.get("label"),
            "removed_stake": affected.get("stake"),
            "replacement_label": replacement.get("label"),
            "replacement_player_id": replacement.get("player_id"),
            "replacement_quality": replacement.get("quality_score"),
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
        })

    event = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_affected_picks": len(affected_port),
        "n_affected_best_bets": len(affected_bb),
        "rebalanced": rebalanced,
        "still_unfilled": max(0, len(affected_port) - len(rebalanced)),
    }
    hist.append(event)
    with open(HIST_PATH, "w") as f:
        json.dump({"events": hist[-30:]}, f)
    with open(OUT_PATH, "w") as f:
        json.dump(event, f, indent=2)
    return event


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    if p.get("n_affected_picks"):
        print(f"  Affected picks: {p['n_affected_picks']}, rebalanced: {len(p['rebalanced'])}")
        for r in p["rebalanced"]:
            print(f"    {r['removed_label']} -> {r['replacement_label']}")
    else:
        print("  No rebalance needed -- no lineup churn affecting picks.")
