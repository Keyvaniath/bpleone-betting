"""
EdgeStat -- golf winner / top-N probability model.

For each player on the active tournament leaderboard, computes:
  - P(win outright)
  - P(top 5)
  - P(top 10)
  - P(top 20)
  - Fair American odds for each

Model: simulated finish via Monte Carlo using a per-player remaining-rounds
expected-score distribution. For each remaining round:
  - leader/contender baseline scoring std ~ 3 strokes per round
  - Use current `total_to_par` as starting position
  - Sample N players' remaining scores from normal(per_player_mean, 3)
  - Tally P(rank=1) / P(rank<=5) / etc. from 5000 simulations

If tournament is COMPLETE: P = 1 for actual winner, 0 for everyone else.

Output: data/golf_props.json
"""
from __future__ import annotations

import os
import json
import random
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
OUT_PATH = os.path.join(DATA_DIR, "golf_props.json")

N_SIMS = 5000
ROUND_STD = 3.0          # std dev of a single round score per player
# Heuristic: better players (lower current total) get slight skill boost
SKILL_PER_STROKE = 0.4   # extra strokes-better-than-field per stroke under par


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _to_par_to_int(s) -> int:
    """Convert ESPN's '-6', '+2', 'E' to int."""
    if s is None: return 0
    s = str(s).strip()
    if s in ("E", "EVEN", "Even", "even"): return 0
    try:
        return int(s.replace("+", ""))
    except Exception:
        return 0


def _american_from_p(p: float) -> int:
    if p <= 0 or p >= 1: return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _decimal_from_p(p: float) -> float:
    return 1 / p if p > 0 else 0


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    t = state.get("active_tournament") or {}
    field = [p for p in (state.get("field") or [])
             if not p.get("is_cut") and not p.get("is_withdrawn")]

    if not field:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no active field",
            "players": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # If tournament complete -> winner gets P=1, rest 0
    if t.get("is_complete"):
        winner = field[0]
        players = [{
            "name": p["name"],
            "p_win": 1.0 if p == winner else 0.0,
            "p_top5": 1.0 if (p.get("order") or 999) <= 5 else 0.0,
            "p_top10": 1.0 if (p.get("order") or 999) <= 10 else 0.0,
            "p_top20": 1.0 if (p.get("order") or 999) <= 20 else 0.0,
            "current_pos": p.get("order"),
            "current_total": p.get("total_to_par"),
        } for p in field]
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "is_complete": True,
            "n_players": len(field),
            "players": players,
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    # Active tournament: simulate remaining rounds
    rounds_done = max((p.get("rounds_played") or 0) for p in field) or 0
    rounds_left = max(0, 4 - rounds_done)
    if rounds_left == 0:
        rounds_left = 1   # in case all played 4 but final not declared

    # Each player's mean-per-remaining-round = league avg (par) - skill_boost
    # where skill is approx. relative to field median current_total
    totals = [(_to_par_to_int(p.get("total_to_par"))) for p in field]
    median_total = sorted(totals)[len(totals) // 2]

    player_means = []
    for p in field:
        cur = _to_par_to_int(p.get("total_to_par"))
        # Lower than median = better -> means lower expected score per round
        skill = (cur - median_total) * SKILL_PER_STROKE
        player_means.append({
            "name": p["name"],
            "starting_total": cur,
            "mean_per_round": 0 + skill,    # 0 = par; negative = better
        })

    random.seed(42)
    win_counts = [0] * len(field)
    top5_counts = [0] * len(field)
    top10_counts = [0] * len(field)
    top20_counts = [0] * len(field)

    for sim in range(N_SIMS):
        final_totals = []
        for i, p in enumerate(player_means):
            tot = p["starting_total"]
            for _ in range(rounds_left):
                tot += int(round(random.gauss(p["mean_per_round"], ROUND_STD)))
            final_totals.append((tot, i))
        final_totals.sort()
        winner_idx = final_totals[0][1]
        win_counts[winner_idx] += 1
        top5_idxs = {idx for _, idx in final_totals[:5]}
        top10_idxs = {idx for _, idx in final_totals[:10]}
        top20_idxs = {idx for _, idx in final_totals[:20]}
        for i in top5_idxs:  top5_counts[i] += 1
        for i in top10_idxs: top10_counts[i] += 1
        for i in top20_idxs: top20_counts[i] += 1

    players = []
    for i, p in enumerate(field):
        p_win = win_counts[i] / N_SIMS
        p_top5 = top5_counts[i] / N_SIMS
        p_top10 = top10_counts[i] / N_SIMS
        p_top20 = top20_counts[i] / N_SIMS
        players.append({
            "name": p["name"],
            "country": p.get("country"),
            "current_pos": p.get("order"),
            "current_total": p.get("total_to_par"),
            "rounds_played": p.get("rounds_played"),
            "thru": p.get("thru"),
            "p_win": round(p_win, 4),
            "p_top5": round(p_top5, 4),
            "p_top10": round(p_top10, 4),
            "p_top20": round(p_top20, 4),
            "fair_win_american": _american_from_p(p_win) if p_win > 0 else None,
            "fair_top5_american": _american_from_p(p_top5) if p_top5 > 0 else None,
            "fair_top10_american": _american_from_p(p_top10) if p_top10 > 0 else None,
            "fair_top20_american": _american_from_p(p_top20) if p_top20 > 0 else None,
        })
    players.sort(key=lambda p: -p["p_win"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": t.get("name"),
        "rounds_left": rounds_left,
        "is_complete": False,
        "n_players": len(players),
        "n_sims": N_SIMS,
        "players": players,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p.get('n_players',0)} players, tournament: {p.get('tournament')}")
    if p.get("players"):
        print(f"  Rounds left: {p.get('rounds_left')}")
        print(f"  Top 5 win-probability:")
        for pl in p["players"][:5]:
            print(f"    {pl['name']:25} pos#{pl.get('current_pos'):3} ({pl.get('current_total')}) "
                  f"P(win)={pl['p_win']*100:5.2f}%  fair {pl['fair_win_american']:+d}  "
                  f"P(top10)={pl['p_top10']*100:.1f}%")
