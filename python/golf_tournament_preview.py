"""
EdgeStat -- Golf tournament preview synthesizer.

For each tournament, produces a unified preview combining:
  - Top golfer confluence picks (LOCK, STRONG)
  - Dominance alerts
  - Leader probability + top finish + make cut signals
  - Hot/cold player heat

Tournament-level metrics:
  - n_locks: golfer LOCKs in this tournament
  - n_strong: golfer STRONGs
  - top contenders: 5 highest composite scores
  - recommended placements (winner, top-5, top-10, miss cut fades)

Output: data/golf_tournament_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_tournament_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "golf_player_confluence_score.json"))
    dom = _load(os.path.join(DATA_DIR, "golf_player_dominance.json"))
    top_finish = _load(os.path.join(DATA_DIR, "golf_top_finish_props.json"))
    leaderboard = _load(os.path.join(DATA_DIR, "golf_leaderboard_probability.json"))
    rounds = _load(os.path.join(DATA_DIR, "golf_round_score_props.json"))

    # Group players by tournament
    players_by_tournament: Dict[str, List[Dict[str, Any]]] = {}
    for r in (conf.get("rows") or []):
        if not isinstance(r, dict): continue
        t = r.get("tournament") or "?"
        players_by_tournament.setdefault(t, []).append(r)

    # Top 3 leaderboard p_leader per tournament
    leader_pick: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (leaderboard.get(k) or []):
            if not isinstance(r, dict): continue
            t = r.get("tournament", "?")
            p_lead = r.get("p_leader") or r.get("p_top1") or 0
            existing = leader_pick.get(t)
            if not existing or p_lead > existing.get("p_leader", 0):
                leader_pick[t] = {"player": r.get("player"), "p_leader": p_lead}

    # Top contenders by composite_score per tournament
    rounds_by_player: Dict[str, str] = {}
    for r in (rounds.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:  # UNDER on round score = lower scores = positive
            rounds_by_player[r.get("player", "")] = "UNDER"
        elif "OVER" in ec:
            rounds_by_player[r.get("player", "")] = "OVER"

    previews: List[Dict[str, Any]] = []
    for tournament, players in players_by_tournament.items():
        if not tournament: continue

        # Sort by composite score
        players.sort(key=lambda p: -(p.get("composite_score") or 0))

        locks = [p for p in players if "LOCK" in (p.get("tier") or "")]
        strong = [p for p in players if "STRONG" in (p.get("tier") or "")]
        fades = [p for p in players if "FADE" in (p.get("tier") or "")]

        contenders = players[:5]

        if locks:
            tier = "TOURNAMENT_LOCK"
        elif len(strong) >= 3:
            tier = "TOURNAMENT_STRONG"
        elif len(strong) >= 1:
            tier = "TOURNAMENT_LEAN"
        else:
            tier = "TOURNAMENT_PASS"

        lead = leader_pick.get(tournament, {})

        angle: List[str] = []
        if locks:
            angle.append(f"{locks[0].get('player')} top 5 finish + make cut LOCK")
        for s in strong[:3]:
            angle.append(f"{s.get('player')} top 10 finish")
        if lead.get("player"):
            angle.append(f"{lead.get('player')} outright winner (p={round(lead.get('p_leader', 0), 3)})")
        for f in fades[:3]:
            angle.append(f"FADE {f.get('player')} miss cut YES")

        previews.append({
            "tournament": tournament,
            "tier": tier,
            "n_locks": len(locks),
            "n_strong": len(strong),
            "n_fades": len(fades),
            "n_players_total": len(players),
            "top_contender": contenders[0].get("player") if contenders else None,
            "leader_pick": lead.get("player"),
            "leader_pick_p": round(lead.get("p_leader", 0), 3),
            "top_5_contenders": [
                {"player": p.get("player"), "tier": p.get("tier"),
                 "score": p.get("composite_score")}
                for p in contenders
            ],
            "recommended_angles": angle,
        })

    tier_order = {"TOURNAMENT_LOCK": 4, "TOURNAMENT_STRONG": 3,
                  "TOURNAMENT_LEAN": 2, "TOURNAMENT_PASS": 1}
    previews.sort(key=lambda p: -tier_order.get(p["tier"], 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_tournaments": len(previews),
        "n_locks": sum(1 for p in previews if p["tier"] == "TOURNAMENT_LOCK"),
        "n_strong": sum(1 for p in previews if p["tier"] == "TOURNAMENT_STRONG"),
        "method_note": "Per-tournament golf preview. Combines confluence_score + "
                       "leaderboard prob + round_score signals. TOURNAMENT_LOCK = "
                       "1+ player LOCK; STRONG = 3+ STRONGs; LEAN = 1+ STRONG.",
        "previews": previews,
        "locks_and_strong": [p for p in previews
                             if p["tier"] in ("TOURNAMENT_LOCK", "TOURNAMENT_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-preview] {o['n_tournaments']} tournaments "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG) -> {OUT}")
