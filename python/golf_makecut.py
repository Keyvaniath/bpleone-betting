"""
EdgeStat -- PGA Tour make-cut + nationality + group-rank props.

For each player, computes:
  - P(makes cut) -- only meaningful between R1 and R3
  - P(finishes top American)
  - P(finishes top European / International)
  - Group rank (1st/2nd/3rd from a 3-player group)

Cut is typically Top 65 + ties after Round 2.

Output: data/golf_makecut.json
"""
from __future__ import annotations

import os
import json
import random
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
OUT_PATH = os.path.join(DATA_DIR, "golf_makecut.json")

N_SIMS = 5000
ROUND_STD = 3.0
SKILL_PER_STROKE = 0.4
CUT_RANK = 65        # standard PGA Tour cut line (top 65 + ties)

try:
    from golf_winner_model import ELITE_PRIOR
except Exception:
    ELITE_PRIOR = {}


# Common nationality buckets for top-X-nationality props
AMERICAN_FLAGS = {"USA", "United States"}
EUROPEAN_FLAGS = {
    "ENG", "England", "SCO", "Scotland", "WAL", "Wales", "IRE", "Ireland", "NIR",
    "Northern Ireland", "ESP", "Spain", "FRA", "France", "GER", "Germany",
    "ITA", "Italy", "SWE", "Sweden", "NOR", "Norway", "DEN", "Denmark",
    "NED", "Netherlands", "AUT", "Austria", "BEL", "Belgium", "FIN", "Finland",
}


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
             if not p.get("is_withdrawn")]

    if not field or t.get("is_complete"):
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": t.get("name"),
            "note": "no active field" if not field else "tournament complete",
            "players": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(payload, f, indent=2)
        return payload

    rounds_done = max((p.get("rounds_played") or 0) for p in field) or 0
    rounds_left = max(1, 4 - rounds_done)

    # Cut props only make sense before the cut. If we're already past R2, cut
    # has been made -- set p_makecut to 1 for non-cut players, 0 for cut.
    cut_in_play = rounds_done <= 1

    totals_now = [_to_par(p.get("total_to_par")) for p in field]
    median = sorted(totals_now)[len(totals_now) // 2]
    means = [(cur - median) * SKILL_PER_STROKE + ELITE_PRIOR.get(field[i]["name"], 0.0)
             for i, cur in enumerate(totals_now)]

    random.seed(43)
    makecut_counts = [0] * len(field)
    top_us_counts = [0] * len(field)
    top_eu_counts = [0] * len(field)

    # Index by nationality for nation-specific top counts
    is_us = [(p.get("country") in AMERICAN_FLAGS) for p in field]
    is_eu = [(p.get("country") in EUROPEAN_FLAGS) for p in field]

    for sim in range(N_SIMS):
        # Simulate R2 finish for cut prop
        if cut_in_play:
            r2_totals = []
            for i, cur in enumerate(totals_now):
                # Project to end of R2 (1 more round assuming we're mid-R1 or R1 done)
                rs_to_r2 = max(1, 2 - rounds_done)
                tot = cur
                for _ in range(rs_to_r2):
                    tot += int(round(random.gauss(means[i], ROUND_STD)))
                r2_totals.append((tot, i))
            r2_totals.sort()
            # Cut at rank CUT_RANK (1-indexed) -- everyone tied gets in
            if len(r2_totals) > CUT_RANK:
                cut_score = r2_totals[CUT_RANK - 1][0]
                for tot, idx in r2_totals:
                    if tot <= cut_score:
                        makecut_counts[idx] += 1

        # Full-tournament finish for nationality props
        finals = []
        for i, cur in enumerate(totals_now):
            tot = cur
            for _ in range(rounds_left):
                tot += int(round(random.gauss(means[i], ROUND_STD)))
            finals.append((tot, i))
        finals.sort()
        # Top American = lowest-scoring US player
        us_finals = [(t, i) for t, i in finals if is_us[i]]
        if us_finals:
            top_us_counts[us_finals[0][1]] += 1
        eu_finals = [(t, i) for t, i in finals if is_eu[i]]
        if eu_finals:
            top_eu_counts[eu_finals[0][1]] += 1

    players = []
    for i, p in enumerate(field):
        p_cut = (makecut_counts[i] / N_SIMS) if cut_in_play else (
            1.0 if (p.get("order") or 999) <= CUT_RANK else 0.0
        )
        p_top_us = top_us_counts[i] / N_SIMS
        p_top_eu = top_eu_counts[i] / N_SIMS
        players.append({
            "name": p["name"],
            "country": p.get("country"),
            "current_pos": p.get("order"),
            "current_total": p.get("total_to_par"),
            "p_makecut": round(p_cut, 4),
            "fair_makecut_american": _amer(p_cut) if 0 < p_cut < 1 else None,
            "p_top_american": round(p_top_us, 4) if is_us[i] else None,
            "fair_top_american": _amer(p_top_us) if is_us[i] and 0 < p_top_us < 1 else None,
            "p_top_european": round(p_top_eu, 4) if is_eu[i] else None,
            "fair_top_european": _amer(p_top_eu) if is_eu[i] and 0 < p_top_eu < 1 else None,
        })
    players.sort(key=lambda p: -(p["p_makecut"] or 0))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": t.get("name"),
        "rounds_left": rounds_left,
        "cut_in_play": cut_in_play,
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
    print(f"Wrote {OUT_PATH}: {p.get('n_players',0)} players")
    print(f"  Cut-in-play: {p.get('cut_in_play')}  rounds_left: {p.get('rounds_left')}")
    if p.get("players"):
        print("  Top 5 by P(makecut):")
        for pl in p["players"][:5]:
            ta = f"  topUS={pl['p_top_american']*100:.1f}%" if pl.get("p_top_american") else ""
            te = f"  topEU={pl['p_top_european']*100:.1f}%" if pl.get("p_top_european") else ""
            print(f"    {pl['name']:25} ({pl.get('country','--'):5}) "
                  f"P(cut) = {pl['p_makecut']*100:5.1f}%{ta}{te}")
