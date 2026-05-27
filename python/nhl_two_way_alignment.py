"""
EdgeStat -- NHL two-way game alignment alerts.

NHL counterpart to MLB/NBA two-way alignment. Surfaces games where:
  - Side A: goalie LOCK (DOMINANCE_ELITE) on home/away
  - Side B: opposing team explosion (5+ signals) + skater LOCK

When both sides align, you can simultaneously:
  - Bet Side A goalie saves OVER + 30+ saves YES + win YES + shutout LIVE
  - Bet Side B opp team total UNDER + 4+ goals NO (capped by goalie)
  - Bet Side B opp skater SOG OVER + anytime goal YES (small sample
    leak through dominance)

Output: data/nhl_two_way_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_two_way_alignment.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    goalie_dom = _load(os.path.join(DATA_DIR, "nhl_goalie_dominance_alerts.json"))
    team_expl = _load(os.path.join(DATA_DIR, "nhl_team_explosion_alerts.json"))
    skater_ceil = _load(os.path.join(DATA_DIR, "nhl_skater_ceiling_stack.json"))

    goalies_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (goalie_dom.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        goalies_by_matchup.setdefault(m, []).append(a)

    explosions_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (team_expl.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        explosions_by_matchup.setdefault(m, []).append(a)

    skater_ceils_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (skater_ceil.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        skater_ceils_by_matchup.setdefault(m, []).append(a)

    all_matchups = (set(goalies_by_matchup) | set(explosions_by_matchup)
                    | set(skater_ceils_by_matchup))

    alignments: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        goalies = goalies_by_matchup.get(matchup, [])
        explosions = explosions_by_matchup.get(matchup, [])
        skater_ceils = skater_ceils_by_matchup.get(matchup, [])

        elite_goalies = [g for g in goalies if g.get("tier") == "DOMINANCE_ELITE"
                         or g.get("n_positive_signals", 0) >= 5]
        if not elite_goalies: continue

        for eg in elite_goalies:
            goalie_team = (eg.get("team") or "").upper()
            # Side B = NOT goalie_team
            side_b_explosions = [e for e in explosions
                                 if (e.get("team") or "").upper() != goalie_team
                                 and e.get("n_positive_signals", 0) >= 5]
            if not side_b_explosions: continue

            for sb in side_b_explosions:
                opp_team = (sb.get("team") or "").upper()
                # Opposing-team skater LOCK
                opp_skaters = [s for s in skater_ceils
                               if (s.get("team") or "").upper() == opp_team
                               and s.get("n_aligned_overs", 0) >= 4]

                alignments.append({
                    "matchup": matchup,
                    "side_a_goalie": eg.get("goalie"),
                    "side_a_goalie_team": goalie_team,
                    "side_a_signals": eg.get("n_positive_signals"),
                    "side_b_team": opp_team,
                    "side_b_explosion_signals": sb.get("n_positive_signals"),
                    "side_b_top_skater": (opp_skaters[0].get("player")
                                          if opp_skaters else None),
                    "tier": "TWO_WAY_ALIGNMENT",
                    "recommended_markets": [
                        f"{eg.get('goalie')} saves OVER + 30+ saves YES + win YES",
                        f"{eg.get('goalie')} shutout LIVE",
                        f"{opp_team} team total UNDER + 4+ goals NO",
                        (f"{opp_skaters[0].get('player')} SOG OVER + anytime goal YES"
                         if opp_skaters else ""),
                        f"{matchup} game total UNDER (goalie suppresses)",
                    ],
                })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "method_note": "NHL two-way: goalie ELITE on side A + opp team explosion "
                       "(5+ signals) on side B. Goalie LOCK suppresses opp scoring "
                       "(saves OVER, opp TT UNDER), but opp skater LOCK still hits "
                       "SOG / anytime goal at high volume.",
        "alignments": alignments,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-two-way] {o['n_alignments']} two-way alignments -> {OUT}")
