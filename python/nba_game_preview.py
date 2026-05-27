"""
EdgeStat -- NBA per-game preview synthesizer.

For each NBA game, produces a unified preview combining:
  - Both team confluence scores
  - Top player ceiling/fade picks per side
  - Game total + half total + pace signals
  - Race-to-points favorite

Each game gets a tier:
  GAME_LOCK   = both teams TT alignment (one OVER, one UNDER) + 1+ TEAM_LOCK
  GAME_STRONG = at least 1 TEAM_LOCK or 2+ player LOCKs
  GAME_LEAN   = at least 1 TEAM_STRONG
  GAME_PASS   = no aligned signals

Output: data/nba_game_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_game_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    teams = _load(os.path.join(DATA_DIR, "nba_team_confluence_score.json"))
    players = _load(os.path.join(DATA_DIR, "nba_player_confluence_score.json"))
    game_total = _load(os.path.join(DATA_DIR, "nba_game_total_alts.json"))
    half = _load(os.path.join(DATA_DIR, "nba_half_total_props.json"))

    teams_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (teams.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        teams_by_matchup.setdefault(m, []).append(r)

    players_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (players.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        players_by_matchup.setdefault(m, []).append(r)

    gt_signals: Dict[str, str] = {}
    for r in (game_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            gt_signals[r.get("matchup", "")] = "OVER"
        elif "UNDER" in ec:
            gt_signals[r.get("matchup", "")] = "UNDER"

    half_over: Dict[str, bool] = {}
    for r in (half.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            half_over[r.get("matchup", "")] = True

    all_matchups = set(teams_by_matchup) | set(players_by_matchup)

    previews: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        team_rows = teams_by_matchup.get(matchup, [])
        player_rows = players_by_matchup.get(matchup, [])

        team_locks = [t for t in team_rows if "LOCK" in (t.get("tier") or "")]
        team_strong = [t for t in team_rows if "STRONG" in (t.get("tier") or "")]
        team_fades = [t for t in team_rows if "FADE" in (t.get("tier") or "")]
        player_locks = [p for p in player_rows if "LOCK" in (p.get("tier") or "")]
        player_strong = [p for p in player_rows if "STRONG" in (p.get("tier") or "")]
        player_fades = [p for p in player_rows if "FADE" in (p.get("tier") or "")]

        gt = gt_signals.get(matchup)
        half_o = half_over.get(matchup, False)

        # Both teams TT-aligned (one OVER, one UNDER) + 1+ TEAM_LOCK = GAME_LOCK
        sides_tt = {t.get("tt_direction") for t in team_rows}
        both_aligned = ("STRONG_OVER" in sides_tt or "LEAN_OVER" in sides_tt) and (
            "STRONG_UNDER" in sides_tt or "LEAN_UNDER" in sides_tt
        )

        if both_aligned and team_locks:
            tier = "GAME_LOCK"
        elif team_locks or len(player_locks) >= 2:
            tier = "GAME_STRONG"
        elif team_strong or player_locks or len(player_strong) >= 2:
            tier = "GAME_LEAN"
        else:
            tier = "GAME_PASS"

        angle: List[str] = []
        for t in team_locks:
            angle.append(f"{t.get('team')} team total OVER")
        for p in player_locks[:3]:
            angle.append(f"{p.get('player')} PTS OVER + PRA OVER")
        if gt == "OVER":
            angle.append(f"{matchup} GAME TOTAL OVER")
        if half_o:
            angle.append(f"{matchup} 1H OVER")
        for tf in team_fades:
            angle.append(f"FADE {tf.get('team')} team total UNDER")
        for pf in player_fades[:2]:
            angle.append(f"FADE {pf.get('player')} PTS UNDER")

        previews.append({
            "matchup": matchup,
            "tier": tier,
            "n_team_locks": len(team_locks),
            "n_team_strong": len(team_strong),
            "n_player_locks": len(player_locks),
            "n_player_strong": len(player_strong),
            "game_total_signal": gt,
            "half_total_over": half_o,
            "team_summary": [
                {"team": t.get("team"), "side": t.get("side"),
                 "tier": t.get("tier"), "tt": t.get("tt_direction"),
                 "score": t.get("composite_score")}
                for t in team_rows
            ],
            "top_player_picks": [
                {"player": p.get("player"), "tier": p.get("tier"),
                 "score": p.get("composite_score")}
                for p in (player_locks + player_strong)[:5]
            ],
            "recommended_angles": angle,
        })

    tier_order = {"GAME_LOCK": 4, "GAME_STRONG": 3, "GAME_LEAN": 2, "GAME_PASS": 1}
    previews.sort(key=lambda g: (-tier_order.get(g["tier"], 0),
                                  -(g.get("n_team_locks", 0)
                                    + g.get("n_player_locks", 0))))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(previews),
        "n_locks": sum(1 for g in previews if g["tier"] == "GAME_LOCK"),
        "n_strong": sum(1 for g in previews if g["tier"] == "GAME_STRONG"),
        "n_lean": sum(1 for g in previews if g["tier"] == "GAME_LEAN"),
        "n_pass": sum(1 for g in previews if g["tier"] == "GAME_PASS"),
        "method_note": "Per-game NBA preview. Tier from team_confluence + "
                       "player_confluence + game_total + half_total. GAME_LOCK = "
                       "both teams TT-aligned + TEAM_LOCK; STRONG = TEAM_LOCK or "
                       "2+ player LOCKs; LEAN = TEAM_STRONG or player LOCK.",
        "previews": previews,
        "locks_and_strong": [g for g in previews
                             if g["tier"] in ("GAME_LOCK", "GAME_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-game-preview] {o['n_games']} games "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN, {o['n_pass']} PASS) -> {OUT}")
