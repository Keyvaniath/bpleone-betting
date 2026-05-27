"""
EdgeStat -- NBA two-way game alignment alerts.

NBA counterpart to mlb_two_way_alignment. Surfaces games where:
  - Side A: NBA team explosion (5+ signals) AND player LOCK on same team
  - Side B: opp player FADE (3+ aligned UNDERs)

When this happens, you can simultaneously:
  - Bet Side A team total OVER + player PTS OVER + PRA OVER
  - Bet Side B player PTS UNDER + PRA UNDER
  - Bet game total OVER (Side A drives it)

Output: data/nba_two_way_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_two_way_alignment.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    team_explosion = _load(os.path.join(DATA_DIR, "nba_team_explosion_alerts.json"))
    player_ceiling = _load(os.path.join(DATA_DIR, "nba_player_ceiling_stack.json"))
    player_fade = _load(os.path.join(DATA_DIR, "nba_player_under_fade.json"))

    explosions_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (team_explosion.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        explosions_by_matchup.setdefault(m, []).append(a)

    ceilings_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (player_ceiling.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        ceilings_by_matchup.setdefault(m, []).append(a)

    fades_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (player_fade.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        fades_by_matchup.setdefault(m, []).append(a)

    all_matchups = (set(explosions_by_matchup) | set(ceilings_by_matchup)
                    | set(fades_by_matchup))

    alignments: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        explosions = explosions_by_matchup.get(matchup, [])
        ceilings = ceilings_by_matchup.get(matchup, [])
        fades = fades_by_matchup.get(matchup, [])

        # Filter explosions to those with 5+ signals
        strong_explosions = [e for e in explosions
                             if e.get("n_positive_signals", 0) >= 5]
        if not strong_explosions: continue

        for se in strong_explosions:
            side_a_team = (se.get("team") or "").upper()
            # Side A player ceilings on same team
            side_a_ceilings = [c for c in ceilings
                               if (c.get("team") or "").upper() == side_a_team
                               and c.get("n_aligned_overs", 0) >= 4]
            if not side_a_ceilings: continue

            # Side B fades (opposing team)
            side_b_fades = [f for f in fades
                            if (f.get("team") or "").upper() != side_a_team
                            and f.get("n_aligned_unders", 0) >= 3]
            if not side_b_fades: continue

            alignments.append({
                "matchup": matchup,
                "side_a_team": side_a_team,
                "side_a_explosion_signals": se.get("n_positive_signals"),
                "side_a_ceiling_player": side_a_ceilings[0].get("player"),
                "side_a_ceiling_signals": side_a_ceilings[0].get("n_aligned_overs"),
                "side_b_fade_player": side_b_fades[0].get("player"),
                "side_b_fade_signals": side_b_fades[0].get("n_aligned_unders"),
                "tier": "TWO_WAY_ALIGNMENT",
                "recommended_markets": [
                    f"{side_a_team} team total OVER",
                    f"{side_a_ceilings[0].get('player')} PTS OVER + PRA OVER",
                    f"{side_b_fades[0].get('player')} PTS UNDER + PRA UNDER",
                    f"{matchup} game total OVER",
                    f"{side_a_team} ML",
                ],
            })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "method_note": "NBA two-way game alignment: team explosion (5+ signals) "
                       "+ player LOCK on side A + opposing player FADE (3+ "
                       "aligned UNDERs) on side B. Highest-leverage NBA signal "
                       "supporting simultaneous OVER + UNDER markets.",
        "alignments": alignments,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-two-way] {o['n_alignments']} two-way alignments -> {OUT}")
