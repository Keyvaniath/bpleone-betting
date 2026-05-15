"""
EdgeStat -- pitcher arsenal vs opposing lineup handedness leverage.

For each game, looks at:
  - Each starting pitcher's pitch arsenal (from Statcast)
  - The L/R composition of the opposing confirmed lineup
  - Whether the pitcher's WORST pitch (highest xwOBA-allowed) is one he
    leans on AND the opposing lineup is stacked with the hand that
    historically punishes that pitch type

Flag: HIGH LEVERAGE matchups for the OPPOSING offense / FADE the pitcher.

Pure heuristic since Statcast public leaderboards don't easily expose
per-pitch L/R splits -- we use:
  - Pitcher's xwOBA per pitch (overall) as 'pitch quality'
  - Lineup hand mix (count of L vs R confirmed starters)
  - Pitcher hand (L pitchers face fewer LHBs typically)

Writes data/pitch_matchup.json keyed by matchup.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "pitch_matchup.json")


def _hand_count(lineup: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count L / R / S (switch) batters in the lineup."""
    counts = {"L": 0, "R": 0, "S": 0, "?": 0}
    for b in lineup or []:
        pid = b.get("id")
        if not pid:
            counts["?"] += 1
            continue
        try:
            payload = sr._get(f"{sr.MLB_BASE}/people/{pid}",
                               f"bhand_{pid}")
        except Exception:
            payload = None
        hand = "?"
        if payload and payload.get("people"):
            hand = (payload["people"][0].get("batSide", {}) or {}).get("code", "?")
        counts[hand] = counts.get(hand, 0) + 1
    return counts


def project_pitch_matchup(pitcher_block: Dict[str, Any],
                          opposing_lineup: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score the matchup leverage. Returns leverage_score, narrative."""
    arsenal = pitcher_block.get("arsenal") or []
    hand_mix = _hand_count(opposing_lineup or [])
    pitcher_hand = pitcher_block.get("hand", "R")

    if not arsenal:
        return {
            "leverage_score": 0,
            "hand_mix": hand_mix,
            "narrative": ["no arsenal data"],
        }

    # Find worst pitch (highest xwOBA) and best pitch (lowest xwOBA)
    rated = [p for p in arsenal if p.get("xwoba") is not None and (p.get("usage_pct") or 0) > 5]
    if not rated:
        return {"leverage_score": 0, "hand_mix": hand_mix, "narrative": ["no rated arsenal"]}

    worst = max(rated, key=lambda p: p["xwoba"])
    best = min(rated, key=lambda p: p["xwoba"])
    avg_xwoba = sum(p["xwoba"] * (p.get("usage_pct", 0) / 100) for p in rated) / max(
        sum(p.get("usage_pct", 0) for p in rated) / 100, 0.01)

    narrative: List[str] = []
    leverage = 0

    # Worst pitch is high usage AND poor quality -> leverage spot
    if worst["xwoba"] > 0.380 and worst.get("usage_pct", 0) >= 20:
        leverage += 10
        narrative.append(f"Worst pitch ({worst['pitch']}, xwOBA {worst['xwoba']:.3f}) "
                          f"used {worst['usage_pct']:.0f}% of the time -- attackable.")

    # Pitcher is a heavy lefty + lineup is RHB-stacked (or vice versa)
    rhb = hand_mix.get("R", 0)
    lhb = hand_mix.get("L", 0)
    if pitcher_hand == "L" and rhb >= 6:
        leverage += 8
        narrative.append(f"LHP facing R-heavy lineup ({rhb}R / {lhb}L) -- platoon edge to offense.")
    elif pitcher_hand == "R" and lhb >= 5:
        leverage += 6
        narrative.append(f"RHP facing L-heavy lineup ({lhb}L / {rhb}R) -- platoon edge to offense.")

    # Overall arsenal quality
    if avg_xwoba > 0.340:
        leverage += 5
        narrative.append(f"Arsenal-weighted xwOBA-allowed is {avg_xwoba:.3f} (well above league .320 avg).")
    elif avg_xwoba < 0.290:
        leverage -= 5
        narrative.append(f"Elite stuff: arsenal-weighted xwOBA {avg_xwoba:.3f} -- fade the offense.")

    return {
        "leverage_score": leverage,
        "hand_mix": hand_mix,
        "pitcher_hand": pitcher_hand,
        "best_pitch": {"pitch": best["pitch"], "xwoba": best["xwoba"], "usage": best.get("usage_pct")},
        "worst_pitch": {"pitch": worst["pitch"], "xwoba": worst["xwoba"], "usage": worst.get("usage_pct")},
        "arsenal_xwoba_allowed": round(avg_xwoba, 3),
        "narrative": narrative,
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    out_games = []
    for g in m.get("games", []):
        L = g.get("lineups") or {}
        home_p = g.get("home_pitcher") or {}
        away_p = g.get("away_pitcher") or {}
        # Each pitcher faces the OPPOSING lineup
        home_proj = project_pitch_matchup(home_p, L.get("away") or [])
        away_proj = project_pitch_matchup(away_p, L.get("home") or [])
        out_games.append({
            "matchup": g.get("matchup"),
            "time": g.get("time"),
            "home_pitcher_vs_away_lineup": {
                "pitcher_name": home_p.get("name"),
                **home_proj,
            },
            "away_pitcher_vs_home_lineup": {
                "pitcher_name": away_p.get("name"),
                **away_proj,
            },
        })
    # Sort by max leverage score across both sides
    out_games.sort(key=lambda g: max(g["home_pitcher_vs_away_lineup"].get("leverage_score", 0),
                                       g["away_pitcher_vs_home_lineup"].get("leverage_score", 0)),
                   reverse=True)
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "games": out_games}


def write_pitch_matchup(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote pitch_matchup -> {path}")
    print(f"  Games scored: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        h = g["home_pitcher_vs_away_lineup"]
        a = g["away_pitcher_vs_home_lineup"]
        print(f"  {g['matchup']:14} | home SP score {h.get('leverage_score','?')} ({h.get('pitcher_name')}) | "
              f"away SP score {a.get('leverage_score','?')} ({a.get('pitcher_name')})")


if __name__ == "__main__":
    write_pitch_matchup(build_all())
