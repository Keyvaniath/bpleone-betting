"""
EdgeStat -- MLB per-game preview synthesizer.

For each MLB game, produces a unified preview combining:
  - Both starting pitcher confluence scores (HOME + AWAY)
  - Both team confluence scores (HOME + AWAY)
  - Game-script alerts
  - Matchup confluence
  - Best recommended angle (TT OVER, TT UNDER, ML, run line, first 5, etc.)

Each game gets a tier:
  GAME_LOCK    = matchup_confluence ELITE AND game_script ELITE
  GAME_STRONG  = at least 2 of (matchup_conf STRONG, game_script STRONG,
                                  pitcher LOCK, team LOCK)
  GAME_LEAN    = at least 1 of the above
  GAME_PASS    = no aligned signals

Output: data/mlb_game_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    pitchers = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    teams = _load(os.path.join(DATA_DIR, "mlb_team_confluence_score.json"))
    script = _load(os.path.join(DATA_DIR, "mlb_game_script_alerts.json"))
    matchup_conf = _load(os.path.join(DATA_DIR, "mlb_matchup_confluence_alerts.json"))

    # Build matchup-keyed indexes
    pitchers_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (pitchers.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        pitchers_by_matchup.setdefault(m, []).append(r)

    teams_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (teams.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        teams_by_matchup.setdefault(m, []).append(r)

    script_by_matchup: Dict[str, Dict[str, Any]] = {}
    for a in (script.get("alerts") or []):
        if not isinstance(a, dict): continue
        m = a.get("matchup", "")
        if m: script_by_matchup[m] = a

    matchup_conf_by_m: Dict[str, Dict[str, Any]] = {}
    for c in (matchup_conf.get("confluences") or []):
        if not isinstance(c, dict): continue
        m = c.get("matchup", "")
        if m: matchup_conf_by_m[m] = c

    all_matchups = (set(pitchers_by_matchup) | set(teams_by_matchup)
                    | set(script_by_matchup) | set(matchup_conf_by_m))

    previews: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        pitcher_rows = pitchers_by_matchup.get(matchup, [])
        team_rows = teams_by_matchup.get(matchup, [])
        s = script_by_matchup.get(matchup, {})
        c = matchup_conf_by_m.get(matchup, {})

        pitcher_locks = [p for p in pitcher_rows if "LOCK" in (p.get("tier") or "")]
        pitcher_strong = [p for p in pitcher_rows if "STRONG" in (p.get("tier") or "")]
        pitcher_fades = [p for p in pitcher_rows if "FADE" in (p.get("tier") or "")]
        team_locks = [t for t in team_rows if "LOCK" in (t.get("tier") or "")]
        team_strong = [t for t in team_rows if "STRONG" in (t.get("tier") or "")]

        # Tier logic
        conf_tier = c.get("tier") or ""
        script_tier = s.get("tier") or ""

        n_signals_strong = sum([
            "ELITE" in conf_tier or "STRONG" in conf_tier,
            "ELITE" in script_tier or "STRONG" in script_tier,
            len(pitcher_locks) > 0 or len(team_locks) > 0,
            len(pitcher_strong) > 0 or len(team_strong) > 0,
        ])

        if "ELITE" in conf_tier and "ELITE" in script_tier:
            tier = "GAME_LOCK"
        elif n_signals_strong >= 2:
            tier = "GAME_STRONG"
        elif n_signals_strong >= 1:
            tier = "GAME_LEAN"
        else:
            tier = "GAME_PASS"

        # Best recommended angle
        angle: List[str] = []
        if c:
            angle.append(f"FADE {c.get('fade_pitcher','?')} K UNDER + outs UNDER")
            if c.get("explosion_team"):
                angle.append(f"{c.get('explosion_team')} team total OVER")
        if "OVER" in (script.get("signals", {}) if isinstance(script, dict) else {}).get("GAME_TOTAL_OVER", ""):
            angle.append(f"{matchup} GAME TOTAL OVER")
        if pitcher_locks:
            angle.append(f"{pitcher_locks[0].get('pitcher')} K OVER + outs OVER + QS YES")
        if team_locks:
            angle.append(f"{team_locks[0].get('team')} team total OVER")
        if pitcher_fades and not c:
            for pf in pitcher_fades:
                angle.append(f"FADE {pf.get('pitcher')} K UNDER + 4+ER YES")

        previews.append({
            "matchup": matchup,
            "tier": tier,
            "matchup_confluence_tier": conf_tier or None,
            "game_script_tier": script_tier or None,
            "n_pitcher_locks": len(pitcher_locks),
            "n_pitcher_strong": len(pitcher_strong),
            "n_pitcher_fades": len(pitcher_fades),
            "n_team_locks": len(team_locks),
            "n_team_strong": len(team_strong),
            "pitcher_summary": [
                {"pitcher": p.get("pitcher"), "tier": p.get("tier"),
                 "score": p.get("composite_score")}
                for p in pitcher_rows
            ],
            "team_summary": [
                {"team": t.get("team"), "side": t.get("side"),
                 "tier": t.get("tier"), "score": t.get("composite_score")}
                for t in team_rows
            ],
            "fade_pitcher": c.get("fade_pitcher"),
            "explosion_team": c.get("explosion_team"),
            "recommended_angles": angle,
        })

    # Sort by tier strength
    tier_order = {"GAME_LOCK": 4, "GAME_STRONG": 3, "GAME_LEAN": 2, "GAME_PASS": 1}
    previews.sort(key=lambda g: (-tier_order.get(g["tier"], 0),
                                  -(g.get("n_pitcher_locks", 0)
                                    + g.get("n_team_locks", 0))))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(previews),
        "n_locks": sum(1 for g in previews if g["tier"] == "GAME_LOCK"),
        "n_strong": sum(1 for g in previews if g["tier"] == "GAME_STRONG"),
        "n_lean": sum(1 for g in previews if g["tier"] == "GAME_LEAN"),
        "n_pass": sum(1 for g in previews if g["tier"] == "GAME_PASS"),
        "method_note": "Per-game MLB preview. Tier from matchup_confluence + "
                       "game_script + pitcher_confluence + team_confluence. "
                       "GAME_LOCK = matchup_conf ELITE AND game_script ELITE; "
                       "GAME_STRONG = 2+ aligned positive signals; "
                       "GAME_LEAN = 1 positive signal.",
        "previews": previews,
        "locks_and_strong": [g for g in previews
                             if g["tier"] in ("GAME_LOCK", "GAME_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-game-preview] {o['n_games']} games "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN, {o['n_pass']} PASS) -> {OUT}")
