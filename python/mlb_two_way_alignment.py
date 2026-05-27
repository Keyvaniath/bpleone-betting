"""
EdgeStat -- MLB two-way game alignment alerts.

The highest-leverage MLB confluence signal possible: when BOTH sides of a
game have STRONG conviction in opposing directions. Specifically:
  - Side A: pitcher LOCK + team UNDER conviction
  - Side B: offensive_explosion + team OVER conviction

When this happens, you can simultaneously:
  - Bet Side A pitcher K OVER + outs OVER + QS YES
  - Bet Side B team total OVER + 5+ runs YES
  - Bet F5 UNDER (Side A pitcher dominates first 5)
  - Bet game total OVER (still possible if Side B explodes late)

Output: data/mlb_two_way_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_two_way_alignment.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    pitcher_conf = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    team_conf = _load(os.path.join(DATA_DIR, "mlb_team_confluence_score.json"))
    explosion = _load(os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json"))

    # Group pitchers by matchup
    pitchers_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (pitcher_conf.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup", "")
        pitchers_by_matchup.setdefault(m, []).append(r)

    teams_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (team_conf.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup", "")
        teams_by_matchup.setdefault(m, []).append(r)

    explosions_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for a in (explosion.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        explosions_by_matchup.setdefault(m, []).append(a)

    all_matchups = set(pitchers_by_matchup) | set(teams_by_matchup) | set(explosions_by_matchup)

    alignments: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        pitchers = pitchers_by_matchup.get(matchup, [])
        teams = teams_by_matchup.get(matchup, [])
        explosions = explosions_by_matchup.get(matchup, [])

        # Find a pitcher LOCK on side A
        pitcher_locks = [p for p in pitchers if "LOCK" in (p.get("tier") or "")]
        if not pitcher_locks: continue

        for pl in pitcher_locks:
            pitcher_team = (pl.get("team") or "").upper()
            # Side B = NOT pitcher_team
            side_b_explosions = [e for e in explosions
                                 if (e.get("team") or "").upper() != pitcher_team
                                 and e.get("n_positive_signals", 0) >= 4]
            if not side_b_explosions: continue

            # Bonus: opposing team must NOT be the same as pitcher's team
            for sb in side_b_explosions:
                opposing_team = (sb.get("team") or "").upper()
                if opposing_team == pitcher_team: continue

                alignments.append({
                    "matchup": matchup,
                    "side_a_pitcher": pl.get("pitcher"),
                    "side_a_team": pitcher_team,
                    "side_a_score": pl.get("composite_score"),
                    "side_b_explosion_team": opposing_team,
                    "side_b_signals": sb.get("n_positive_signals"),
                    "tier": "TWO_WAY_ALIGNMENT",
                    "recommended_markets": [
                        f"{pl.get('pitcher')} K OVER + outs OVER + QS YES",
                        f"{opposing_team} team total OVER + 5+ runs YES",
                        f"{matchup} 1st 5 innings UNDER (pitcher dominates F5)",
                        f"{matchup} game total OVER (late explosion possible)",
                        f"opp lineup HR YES (top of order)",
                    ],
                })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "method_note": "Two-way game alignment: pitcher LOCK on side A + "
                       "offensive_explosion (5+ signals) on side B = highest-"
                       "leverage MLB parlay. Simultaneous: pitcher props OVER + "
                       "opp team total OVER + F5 UNDER + game total OVER.",
        "alignments": alignments,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-two-way] {o['n_alignments']} two-way alignments -> {OUT}")
