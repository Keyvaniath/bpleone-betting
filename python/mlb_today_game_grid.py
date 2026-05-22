"""
EdgeStat -- MLB Today's Game Grid.

Per-game one-row summary combining every context signal we have:
  - Park HR environment tier
  - Home/Away lineup quality (tier + score)
  - Starter form status (HEATING/COOLING/STEADY)
  - Starter pitch-count danger zone
  - Bullpen fatigue tier
  - Closer availability
  - Team total edge direction
  - 1st-inning signals
  - Stack quality top labels

Designed to be the single-glance "what should I know about each game tonight"
report. Both raw JSON output AND a per-game text summary string.

Output: data/mlb_today_game_grid.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_game_grid.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    form_tracker = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json"))
    pitch_alerts = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json"))
    bp_fatigue = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    closer_track = _load(os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    first_inn = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))
    stack = _load(os.path.join(DATA_DIR, "mlb_stack_builder.json"))

    # Index by matchup
    lq_idx = {g.get("matchup"): g for g in (lineup_q.get("games") or [])}
    park_idx = {g.get("matchup"): g for g in (park_hr.get("games") or [])}
    form_idx: Dict[str, Dict[str, Any]] = {}
    for r in (form_tracker.get("rows") or []):
        form_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r
    pitch_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitch_alerts.get("rows") or []):
        pitch_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r
    bp_idx = {g.get("matchup"): g for g in (bp_fatigue.get("games") or [])}
    closer_idx = {g.get("matchup"): g for g in (closer_track.get("games") or [])}
    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        tt_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r
    first_idx: Dict[str, Dict[str, Any]] = {}
    for r in (first_inn.get("rows") or []):
        first_idx[f"{r.get('matchup','')}|{r.get('side','')}"] = r
    stack_idx: Dict[str, List[Dict[str, Any]]] = {}
    for s in (stack.get("top_5_stacks") or []):
        stack_idx.setdefault(s.get("matchup", ""), []).append(s)

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        lq_game = lq_idx.get(matchup, {})
        park_game = park_idx.get(matchup, {})
        bp_game = bp_idx.get(matchup, {})
        closer_game = closer_idx.get(matchup, {})

        sides_summary: Dict[str, Any] = {}
        for side in ("home", "away"):
            opp_side = "AWAY" if side == "home" else "HOME"
            sp_side_key = side.upper()
            # Pitcher form + workload (this side's starter)
            form = form_idx.get(f"{matchup}|{sp_side_key}", {})
            pc = pitch_idx.get(f"{matchup}|{sp_side_key}", {})
            # Team total + first inning (this side's offense)
            tt = tt_idx.get(f"{matchup}|{sp_side_key}", {})
            fi = first_idx.get(f"{matchup}|{sp_side_key}", {})
            # Bullpen
            pen = bp_game.get(f"{side}_pen") or {}
            # Closer
            closer = closer_game.get(side) or {}
            # Lineup
            lineup_side = lq_game.get(side) or {}

            sides_summary[side] = {
                "team": lineup_side.get("team"),
                "lineup_tier": lineup_side.get("tier"),
                "lineup_score": lineup_side.get("score"),
                "starter_form": form.get("status"),
                "starter_pitch_count_status": pc.get("status"),
                "bullpen_tier": pen.get("tier"),
                "closer_status": closer.get("status"),
                "team_total_direction": tt.get("direction"),
                "first_inning_edge_class": fi.get("edge_class"),
            }

        # Aggregate signal counts for the game
        notable_signals: List[str] = []
        for side in ("home", "away"):
            s = sides_summary[side]
            team = s.get("team") or side.upper()
            if s.get("lineup_tier") == "elite":
                notable_signals.append(f"{team} ELITE_LINEUP")
            if s.get("starter_form") in ("HEATING_UP", "COOLING_DOWN"):
                notable_signals.append(f"{team} starter {s['starter_form']}")
            if s.get("starter_pitch_count_status") in ("RED", "EMERGENCY"):
                notable_signals.append(f"{team} starter {s['starter_pitch_count_status']} workload")
            if s.get("bullpen_tier") in ("GASSED", "TIRED"):
                notable_signals.append(f"{team} bullpen {s['bullpen_tier']}")
            if s.get("closer_status") in ("UNAVAILABLE", "LIMITED"):
                notable_signals.append(f"{team} closer {s['closer_status']}")
            if s.get("team_total_direction", "").startswith("STRONG"):
                notable_signals.append(f"{team} TT {s['team_total_direction']}")
            if s.get("first_inning_edge_class", "").startswith("STRONG"):
                notable_signals.append(f"{team} 1ST_INN {s['first_inning_edge_class']}")

        park_tier = park_game.get("tier") or "NEUTRAL"
        if park_tier in ("HOMER_FRIENDLY", "PITCHER_GRAVEYARD"):
            notable_signals.insert(0, f"PARK {park_tier}")

        stacks_for_game = stack_idx.get(matchup, [])
        elite_stack_count = sum(1 for s in stacks_for_game if s.get("stack_score", 0) >= 70)

        out_games.append({
            "matchup": matchup,
            "park": park_game.get("park"),
            "park_tier": park_tier,
            "park_index": park_game.get("composite_index"),
            "home": sides_summary["home"],
            "away": sides_summary["away"],
            "elite_stack_count": elite_stack_count,
            "notable_signals": notable_signals,
            "n_signals": len(notable_signals),
        })

    # Sort by n_signals desc (most-actionable games first)
    out_games.sort(key=lambda g: -g["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "method_note": "Per-game grid combining park, lineup, starter form, pitch-count, "
                       "bullpen, closer, team_total, first_inning, stack signals into a "
                       "single one-row summary. Sorted by total signal count desc.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[grid] {o['n_games']} games, "
          f"top game signals: {(o['games'] or [{}])[0].get('n_signals',0)} -> {OUT}")
