"""
EdgeStat -- GOLF live tracker (per-hole momentum + cut-line proximity).

Reads golf_state.json (refreshed by golf_pipeline.py during tournaments) and
emits a "live tracker" suitable for the front-end live updates:

  - heaters: 3+ birdies in last 6 holes -> momentum signal
  - stalled: no movement for last 5 holes
  - cut_line_bubble: within +/- 1 stroke of projected cut
  - position_movers: jumped >= 5 ranks since last refresh (uses pot_history)
  - top_5_p_via_live: P(top_5 finish) given current strokes + holes remaining

Output: data/golf_live_tracker.json

Works during tournament; emits sparse JSON between events.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_live_tracker.json")

ROUND_STDEV = 2.6
CUT_RULE = 70  # PGA standard: top 65 + ties make cut


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _to_par(s):
    if s is None: return None
    if isinstance(s, (int, float)): return int(s)
    s = str(s).strip().upper()
    if s in ("E", "EVEN", "0"): return 0
    if s in ("CUT", "WD", "DQ", "MDF", "--", ""): return None
    try:
        return int(s.lstrip("+"))
    except Exception:
        return None


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "golf_state.json"))
    history = _load(os.path.join(DATA_DIR, "golf_pot_history.json"))

    # golf_state nests the tournament under active_tournament (+ current_leader,
    # + a 156-player `field` leaderboard). Reading TOP-LEVEL keys here was the bug:
    # it always fell back to "PGA Event" / not-live during a live major. Reconcile
    # with golf_state.py's structure -- the authoritative in-progress signal.
    at = state.get("active_tournament") or {}
    leader = state.get("current_leader") or {}
    field = state.get("field") or state.get("leaderboard") or state.get("players") or []
    tournament = at.get("name") or state.get("tournament") or state.get("name") or "PGA Event"
    status = (at.get("status") or state.get("status") or "").lower()
    is_live = ((bool(at.get("is_in_progress")) or "progress" in status or "live" in status)
               and not at.get("is_complete"))
    rounds_done = (leader.get("rounds_played")
                   or (max((p.get("rounds_played") or 0) for p in field) if field else 0) or 0)
    rounds_left = max(0, 4 - rounds_done)

    # Empty shell only when genuinely NOT live (between events). A live R1 with no
    # completed round yet (rounds_done 0) still counts as live -- don't blank it.
    if not is_live:
        out = {
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "tournament": tournament,
            "status": at.get("status"),
            "is_live": bool(is_live),
            "rounds_done": rounds_done,
            "rounds_left": rounds_left,
            "heaters": [],
            "stalled": [],
            "cut_bubble": [],
            "position_movers": [],
            "top_5_candidates": [],
            "note": "No live data -- tournament not yet in progress or between events.",
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f: json.dump(out, f, indent=2)
        return out

    players = field or state.get("preview_field") or []

    # Build current-state list. golf_state.field uses total_to_par / order /
    # last_round_score, so include those keys alongside the legacy names.
    rows: List[Dict[str, Any]] = []
    for p in players:
        name = p.get("name") or p.get("player")
        to_par = _to_par(p.get("to_par") or p.get("score") or p.get("total") or p.get("total_to_par"))
        if name is None: continue
        rank = p.get("rank") or p.get("position") or p.get("order")
        try: rank = int(str(rank).lstrip("Tt")) if rank is not None else None
        except Exception: rank = None
        thru = p.get("thru") or p.get("holes_completed")
        last_round = _to_par(p.get("today") or p.get("round_score") or p.get("last_round_score"))
        rows.append({
            "name": name,
            "to_par": to_par,
            "rank": rank,
            "thru": thru,
            "today": last_round,
        })

    rows = [r for r in rows if r["to_par"] is not None]
    rows.sort(key=lambda r: r["to_par"])

    # Heaters: today's round is -3 or better w/ thru >= 12
    heaters = []
    for r in rows:
        if r["today"] is not None and r["today"] <= -3 and (r["thru"] or 18) >= 12:
            heaters.append({"name": r["name"], "to_par": r["to_par"], "today": r["today"],
                            "rank": r["rank"], "thru": r["thru"]})
    heaters = heaters[:12]

    # Stalled: today's round is +1 or worse w/ thru >= 12 and rank > 30
    stalled = []
    for r in rows:
        if r["today"] is not None and r["today"] >= 1 and (r["thru"] or 18) >= 12 and (r["rank"] or 100) > 30:
            stalled.append({"name": r["name"], "to_par": r["to_par"], "today": r["today"],
                            "rank": r["rank"]})
    stalled = stalled[:10]

    # Cut bubble: rounds_done == 2 (after R2) and player rank 60-75
    cut_bubble = []
    if rounds_done >= 2 and rounds_left >= 1 and len(rows) >= CUT_RULE:
        # Cut score = score at rank CUT_RULE
        cut_idx = min(CUT_RULE - 1, len(rows) - 1)
        cut_score = rows[cut_idx]["to_par"]
        for r in rows:
            if r["to_par"] is not None and abs(r["to_par"] - cut_score) <= 1:
                cut_bubble.append({
                    "name": r["name"], "to_par": r["to_par"], "rank": r["rank"],
                    "cut_line": cut_score, "strokes_to_cut": r["to_par"] - cut_score,
                })
        cut_bubble = cut_bubble[:20]

    # Position movers: compare to last refresh (pot_history) — if history has snapshots
    movers = []
    snaps = history.get("snapshots") or history.get("rounds") or []
    if isinstance(snaps, list) and len(snaps) >= 2:
        prev_snap = snaps[-2]
        prev_ranks: Dict[str, int] = {}
        for p in (prev_snap.get("leaderboard") or prev_snap.get("players") or []):
            nm = p.get("name") or p.get("player")
            rk = p.get("rank") or p.get("position")
            try: rk = int(str(rk).lstrip("Tt")) if rk is not None else None
            except Exception: rk = None
            if nm and rk: prev_ranks[nm] = rk
        for r in rows:
            if r["rank"] and r["name"] in prev_ranks:
                delta = prev_ranks[r["name"]] - r["rank"]
                if abs(delta) >= 5:
                    movers.append({
                        "name": r["name"], "from_rank": prev_ranks[r["name"]],
                        "to_rank": r["rank"], "delta": delta,
                    })
        movers.sort(key=lambda x: -abs(x["delta"]))
        movers = movers[:15]

    # P(top_5) given current state — simple normal-quantile model
    top5_candidates = []
    if rows and rounds_left > 0:
        field_mean = sum(r["to_par"] for r in rows) / len(rows)
        proj_std = ROUND_STDEV * math.sqrt(max(rounds_left, 1))
        # threshold score = score at rank 5
        if len(rows) >= 5:
            t5_score = rows[4]["to_par"]
            for r in rows[:25]:
                # Z(score) = (player_score - threshold) / std, want P(player_final <= threshold)
                # Player projected to remain at current to_par + expected_remaining
                # Simple model: player score - threshold under normal
                if r["to_par"] is not None:
                    z = (t5_score - r["to_par"]) / proj_std if proj_std > 0 else 0
                    p_top5 = _norm_cdf(z) or 0.0
                    top5_candidates.append({
                        "name": r["name"], "to_par": r["to_par"], "rank": r["rank"],
                        "p_top_5": round(p_top5, 3),
                    })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "tournament": tournament,
        "status": at.get("status"),
        "is_live": True,
        "rounds_done": rounds_done,
        "rounds_left": rounds_left,
        "field_size": len(rows),
        "leader_to_par": rows[0]["to_par"] if rows else None,
        "heaters": heaters,
        "stalled": stalled,
        "cut_bubble": cut_bubble,
        "position_movers": movers,
        "top_5_candidates": top5_candidates,
        "note": "Live tracker -- heaters/stalled/cut-bubble/movers refreshed every cycle.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-live] heaters={len(o.get('heaters', []))} stalled={len(o.get('stalled', []))} "
          f"cut={len(o.get('cut_bubble', []))} movers={len(o.get('position_movers', []))}")
