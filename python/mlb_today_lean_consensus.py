"""
EdgeStat -- MLB Today's Lean Consensus.

Per-game directional-lean consensus across all MLB context features. For each
of tonight's matchups, scans the following sources for that game's leans and
tallies them by market type (TOTAL, RUN_LINE, ML, F5, INNINGS_7_9, HR_PROPS, etc).

Then assigns a CONSENSUS direction:
  - 4+ agreeing leans (all OVER or all UNDER on same market) -> CONSENSUS_STRONG
  - 2-3 agreeing -> CONSENSUS_LEAN
  - 0-1 -> NO_CONSENSUS or MIXED

Source modules:
  - mlb_pitcher_edge_composite (pitcher matchup directional lean)
  - mlb_bullpen_fatigue_index (late-game over/under lean)
  - mlb_starter_pitch_count_alerts (outs UNDER bias on RED/EMERGENCY)
  - mlb_park_weather_hr_index (HR / total OVER/UNDER from environment)
  - mlb_team_total_edge (per-team direction)
  - mlb_lineup_quality_index (advantage label)

Output: data/mlb_today_lean_consensus.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_lean_consensus.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _classify(direction_counts: Dict[str, int]) -> str:
    """Return CONSENSUS_STRONG / CONSENSUS_LEAN / MIXED / NO_CONSENSUS."""
    if not direction_counts: return "NO_CONSENSUS"
    if len(direction_counts) > 1 and \
       max(direction_counts.values()) - min(direction_counts.values()) <= 1:
        return "MIXED"
    top_count = max(direction_counts.values())
    if top_count >= 4: return "CONSENSUS_STRONG"
    if top_count >= 2: return "CONSENSUS_LEAN"
    return "NO_CONSENSUS"


def run() -> Dict[str, Any]:
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    bp_fatigue = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    pitch_alerts = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    # Aggregate per matchup
    by_game: Dict[str, Dict[str, List[str]]] = {}

    def _add(matchup: str, market: str, direction: str, source: str):
        g = by_game.setdefault(matchup, {})
        leans = g.setdefault(market, [])
        leans.append(f"{direction}:{source}")

    # 1) Pitcher edge composite leans
    for r in (pitcher_edge.get("rows") or []):
        m = r.get("matchup")
        tier = r.get("tier")
        if not m: continue
        for lean in (r.get("directional_lean") or []):
            if "K_OVER" in lean or "OUTS_OVER" in lean or "QS_YES" in lean:
                _add(m, "PITCHER_PROPS", "OVER", f"pitcher_edge_{tier}")
            if "K_UNDER" in lean or "OPP_TT_OVER" in lean:
                if "OPP_TT_OVER" in lean:
                    _add(m, "TEAM_TOTAL_OPP", "OVER", f"pitcher_edge_{tier}")
                if "K_UNDER" in lean:
                    _add(m, "PITCHER_PROPS", "UNDER", f"pitcher_edge_{tier}")

    # 2) Bullpen fatigue
    for g in (bp_fatigue.get("games") or []):
        m = g.get("matchup")
        if not m: continue
        if (g.get("home_pen") or {}).get("tier") in ("GASSED", "TIRED"):
            _add(m, "INNINGS_7_9", "OVER", "bp_fatigue")
        if (g.get("away_pen") or {}).get("tier") in ("GASSED", "TIRED"):
            _add(m, "INNINGS_7_9", "OVER", "bp_fatigue")

    # 3) Pitch count
    for r in (pitch_alerts.get("rows") or []):
        m = r.get("matchup")
        if r.get("status") in ("RED", "EMERGENCY"):
            _add(m, "PITCHER_PROPS", "UNDER", f"pitch_count_{r.get('status')}")
            _add(m, "TOTAL", "OVER", f"pitch_count_{r.get('status')}")

    # 4) Park / weather HR env
    for g in (park_hr.get("games") or []):
        m = g.get("matchup")
        tier = g.get("tier")
        if tier == "HOMER_FRIENDLY":
            _add(m, "TOTAL", "OVER", "park_homer")
            _add(m, "HR_PROPS", "OVER", "park_homer")
        elif tier == "PITCHER_GRAVEYARD":
            _add(m, "TOTAL", "UNDER", "park_graveyard")
            _add(m, "HR_PROPS", "UNDER", "park_graveyard")

    # 5) Team total edges
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        direction = r.get("direction") or ""
        if direction.endswith("OVER"):
            _add(m, f"TEAM_TOTAL_{r.get('side')}", "OVER", "tt_model")
        elif direction.endswith("UNDER"):
            _add(m, f"TEAM_TOTAL_{r.get('side')}", "UNDER", "tt_model")

    # 6) Lineup quality (advantage)
    for g in (lineup_q.get("games") or []):
        m = g.get("matchup")
        adv = g.get("advantage")
        if adv == "HOME_STRONG":
            _add(m, "ML", "HOME", "lineup_adv")
            _add(m, "RUN_LINE", "HOME_FAV", "lineup_adv")
        elif adv == "AWAY_STRONG":
            _add(m, "ML", "AWAY", "lineup_adv")
            _add(m, "RUN_LINE", "AWAY_FAV", "lineup_adv")

    # Build consensus per game per market
    out_games: List[Dict[str, Any]] = []
    for matchup, markets in by_game.items():
        game_summary: Dict[str, Any] = {"matchup": matchup, "markets": []}
        for market, leans in markets.items():
            # Tally directions
            dir_counts: Dict[str, int] = {}
            for lean in leans:
                d = lean.split(":")[0]
                dir_counts[d] = dir_counts.get(d, 0) + 1
            consensus = _classify(dir_counts)
            game_summary["markets"].append({
                "market": market,
                "direction_counts": dir_counts,
                "consensus": consensus,
                "supporting_leans": leans,
            })
        out_games.append(game_summary)

    # Surface strong consensus signals
    strong_signals: List[Dict[str, Any]] = []
    for g in out_games:
        for mk in g["markets"]:
            if mk["consensus"] == "CONSENSUS_STRONG":
                strong_signals.append({
                    "matchup": g["matchup"],
                    "market": mk["market"],
                    "top_direction": max(mk["direction_counts"], key=mk["direction_counts"].get),
                    "agree_count": max(mk["direction_counts"].values()),
                    "leans": mk["supporting_leans"],
                })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games_with_leans": len(out_games),
        "n_strong_consensus_signals": len(strong_signals),
        "method_note": "Aggregates directional leans from 6 MLB context modules per "
                       "matchup. CONSENSUS_STRONG = 4+ agree, LEAN = 2-3, MIXED = "
                       "splits >= 2 directions within 1 vote.",
        "strong_consensus_signals": strong_signals,
        "by_game": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[lean-consensus] {o['n_games_with_leans']} games, "
          f"{o['n_strong_consensus_signals']} strong consensus -> {OUT}")
