"""
EdgeStat -- golf head-to-head matchup probabilities.

Books offer dozens of golfer-vs-golfer matchups every tournament (e.g.
"Scottie Scheffler beats Rory McIlroy at the end of round 3"). We surface
ours from the same Monte Carlo state used by golf_winner_model.

For each pair (Top 30 by current position) we compute:
  - P(A finishes ahead of B)  -- standard 3-ball / 2-ball matchup
  - Fair American odds for either side
  - Implied edge vs 50/50 baseline (informational only -- we don't have
    book prices to compare yet)

Output: data/golf_h2h.json
"""
from __future__ import annotations

import os
import json
import random
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
OUT_PATH = os.path.join(DATA_DIR, "golf_h2h.json")

N_SIMS = 5000
ROUND_STD = 3.0
SKILL_PER_STROKE = 0.4
TOP_N_FOR_H2H = 30      # only compute matchups within top 30

# Reuse the elite skill prior table from golf_winner_model
try:
    from golf_winner_model import ELITE_PRIOR
except Exception:
    ELITE_PRIOR = {}


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _to_par(s) -> int:
    if s is None:
        return 0
    s = str(s).strip()
    if s in ("E", "EVEN", "Even", "even"):
        return 0
    try:
        return int(s.replace("+", ""))
    except Exception:
        return 0


def _amer(p: float) -> int:
    if p <= 0 or p >= 1:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    t = state.get("active_tournament") or {}
    field = [p for p in (state.get("field") or [])
             if not p.get("is_cut") and not p.get("is_withdrawn")]

    if not field or t.get("is_complete"):
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no active field" if not field else "tournament complete",
            "matchups": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    rounds_done = max((p.get("rounds_played") or 0) for p in field) or 0
    rounds_left = max(1, 4 - rounds_done)

    # Compute per-player simulated final totals (reuse one set of sims for all
    # H2H pairs -- ~150x faster than re-simming each pair).
    totals_now = [_to_par(p.get("total_to_par")) for p in field]
    median = sorted(totals_now)[len(totals_now) // 2]
    means = [(cur - median) * SKILL_PER_STROKE + ELITE_PRIOR.get(field[i]["name"], 0.0)
             for i, cur in enumerate(totals_now)]

    random.seed(42)
    # final_totals[sim][player_idx] = simulated final total
    final_totals = [[0] * len(field) for _ in range(N_SIMS)]
    for sim in range(N_SIMS):
        for i, cur in enumerate(totals_now):
            tot = cur
            for _ in range(rounds_left):
                tot += int(round(random.gauss(means[i], ROUND_STD)))
            final_totals[sim][i] = tot

    # Build matchups for top-N players (by current position)
    top_idx = list(range(min(TOP_N_FOR_H2H, len(field))))
    matchups: List[Dict[str, Any]] = []
    for i in range(len(top_idx)):
        for j in range(i + 1, len(top_idx)):
            a, b = top_idx[i], top_idx[j]
            a_wins = sum(1 for sim in range(N_SIMS)
                         if final_totals[sim][a] < final_totals[sim][b])
            ties = sum(1 for sim in range(N_SIMS)
                       if final_totals[sim][a] == final_totals[sim][b])
            # Treat ties as 50/50 (most book rules push or void)
            p_a = (a_wins + ties / 2) / N_SIMS
            p_b = 1 - p_a
            pa_name = field[a]["name"]
            pb_name = field[b]["name"]
            matchups.append({
                "player_a": pa_name,
                "player_b": pb_name,
                "a_pos": field[a].get("order"),
                "b_pos": field[b].get("order"),
                "a_total": field[a].get("total_to_par"),
                "b_total": field[b].get("total_to_par"),
                "p_a_beats_b": round(p_a, 4),
                "p_b_beats_a": round(p_b, 4),
                "fair_a_american": _amer(p_a) if 0 < p_a < 1 else None,
                "fair_b_american": _amer(p_b) if 0 < p_b < 1 else None,
            })

    # Sort: closest matchups first (most actionable for book comparison)
    matchups.sort(key=lambda m: abs(m["p_a_beats_b"] - 0.5))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": t.get("name"),
        "rounds_left": rounds_left,
        "n_matchups": len(matchups),
        "n_sims": N_SIMS,
        "matchups": matchups,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p.get('n_matchups',0)} H2H matchups")
    if p.get("matchups"):
        print("  Closest matchups (top 10):")
        for m in p["matchups"][:10]:
            print(f"    {m['player_a']:25} ({m['fair_a_american']:+5d}) vs "
                  f"{m['player_b']:25} ({m['fair_b_american']:+5d}) -- "
                  f"P(A) = {m['p_a_beats_b']*100:5.2f}%")
