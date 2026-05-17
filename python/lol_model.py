"""
EdgeStat -- League of Legends win-probability model.

Inputs:
  - lol_state.json (Riot lolesports schedule + completed matches)
  - lol_elo.json (rolling team ELO ratings; updated from each completed match)

For each upcoming + live match, computes:
  - P(team A wins map / series) using single-map win-prob -> BO-N series formula
  - Fair American odds per side
  - Map handicap (-1.5 / +1.5 for BO3, -2.5 for BO5) projections
  - Total maps (over/under) projections

ELO update: K-factor 24 (esports has high variance match-to-match), updated
on each completed match. Cold-start league baselines:
  - LCK / LPL: 1550 (top regions)
  - LCS / LEC: 1500 (mid-tier)
  - Others: 1450 (developing/regional)

Output: data/lol_props.json + updates data/lol_elo.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "lol_state.json")
ELO_PATH = os.path.join(DATA_DIR, "lol_elo.json")
OUT_PATH = os.path.join(DATA_DIR, "lol_props.json")

K_FACTOR = 24
BASE_ELO = 1500
HOME_ADVANTAGE_ELO = 0    # esports = neutral venue; no HFA

# Region baselines applied at cold-start (first time we see a team)
REGION_BASELINES = {
    "LCK": 1580, "LPL": 1570, "LEC": 1520, "LCS": 1490,
    "MSI": 1550, "Worlds": 1560, "First Stand": 1530,
    "PCS": 1450, "VCS": 1440, "CBLOL": 1430, "LLA": 1410, "LJL": 1400,
    "LCO": 1380, "EU Masters": 1430, "NACL": 1380,
    "LCK Challengers": 1380, "EMEA Masters": 1420,
}


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f:
        json.dump(payload, f, indent=2)


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _baseline(league: str) -> int:
    return REGION_BASELINES.get(league, BASE_ELO)


def _series_win_prob(p_map: float, best_of: int) -> float:
    """Given P(team wins a single map), return P(team wins BO-N series).
    Uses binomial: a team needs ceil(N/2) wins."""
    if best_of <= 1:
        return p_map
    target = (best_of + 1) // 2    # 2 for BO3, 3 for BO5, 4 for BO7
    # Sum P(team wins exactly k maps, opponent < target) for k = target..best_of
    total = 0.0
    for opp_wins in range(target):
        # Series ends when team gets target wins; opp_wins is their final count
        # P = C(target-1+opp_wins, opp_wins) * p^target * (1-p)^opp_wins
        c = math.comb(target - 1 + opp_wins, opp_wins)
        total += c * (p_map ** target) * ((1 - p_map) ** opp_wins)
    return min(0.999, max(0.001, total))


def _elo_winprob(elo_a: float, elo_b: float) -> float:
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def _update_elo_from_completed(elo_table: Dict[str, float],
                                completed: List[Dict[str, Any]]) -> Dict[str, float]:
    """Walk completed matches in chronological order and update ELO."""
    # Sort by start_time ascending
    completed.sort(key=lambda m: m.get("start_time", ""))
    elo_table = dict(elo_table)
    for m in completed:
        a = m["team_a"]
        b = m["team_b"]
        if a is None or b is None:
            continue
        elo_a = elo_table.get(a, _baseline(m.get("league", "")))
        elo_b = elo_table.get(b, _baseline(m.get("league", "")))

        # Determine winner. Score on map-wins; use map-margin for K-weight.
        s_a = m.get("team_a_score") or 0
        s_b = m.get("team_b_score") or 0
        if s_a + s_b == 0:
            continue
        actual_a = 1.0 if s_a > s_b else 0.0 if s_b > s_a else 0.5

        expected_a = _elo_winprob(elo_a, elo_b)
        # Map margin scaling: 2-0 sweep gets more credit than 2-1 grind
        margin = abs(s_a - s_b)
        margin_mult = 1.0 + math.log1p(margin) * 0.4
        delta = K_FACTOR * margin_mult * (actual_a - expected_a)
        elo_table[a] = elo_a + delta
        elo_table[b] = elo_b - delta
    return elo_table


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    all_matches = state.get("all_matches") or []
    if not all_matches:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no matches in state",
            "matches": [],
        }
        _save(OUT_PATH, payload)
        return payload

    # Load existing ELO + incorporate freshly-completed matches
    elo_store = _load(ELO_PATH)
    elo_table: Dict[str, float] = elo_store.get("teams") or {}
    seen_ids: set = set(elo_store.get("processed_match_ids") or [])

    completed = [m for m in all_matches if m["is_completed"]
                  and str(m.get("id")) not in seen_ids]
    if completed:
        elo_table = _update_elo_from_completed(elo_table, completed)
        for m in completed:
            seen_ids.add(str(m.get("id")))

    # Persist ELO
    _save(ELO_PATH, {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(elo_table),
        "n_processed_matches": len(seen_ids),
        "teams": elo_table,
        "processed_match_ids": list(seen_ids)[-2000:],   # cap
    })

    # Build predictions for non-completed matches
    predictions: List[Dict[str, Any]] = []
    for m in all_matches:
        if m["is_completed"]:
            continue
        a, b = m["team_a"], m["team_b"]
        if not (a and b):
            continue
        league = m.get("league", "")
        elo_a = elo_table.get(a, _baseline(league))
        elo_b = elo_table.get(b, _baseline(league))
        p_map_a = _elo_winprob(elo_a, elo_b)
        best_of = m.get("best_of") or 1
        p_series_a = _series_win_prob(p_map_a, best_of)
        p_series_b = 1 - p_series_a

        # Map handicap (-1.5 / +1.5 for BO3, -2.5/+2.5 for BO5)
        handicap_target = (best_of + 1) // 2
        # For BO3 -1.5: team A wins 2-0; binomial = p^2
        # For BO5 -2.5: team A wins 3-0; binomial = p^3
        sweep_prob = p_map_a ** handicap_target

        predictions.append({
            **m,
            "elo_a": round(elo_a, 1),
            "elo_b": round(elo_b, 1),
            "p_map_a": round(p_map_a, 4),
            "p_series_a": round(p_series_a, 4),
            "p_series_b": round(p_series_b, 4),
            "fair_a_american": _american(p_series_a),
            "fair_b_american": _american(p_series_b),
            "p_sweep_a": round(sweep_prob, 4),
            "fair_sweep_a_american": _american(sweep_prob),
            "p_sweep_b": round((1 - p_map_a) ** handicap_target, 4),
        })

    predictions.sort(key=lambda p: (
        0 if p["is_in_progress"] else 1,
        p.get("start_time", "")
    ))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_matches": len(predictions),
        "n_teams_rated": len(elo_table),
        "predictions": predictions,
    }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_matches']} predictions, {p['n_teams_rated']} teams rated")
    for m in p["predictions"][:8]:
        ams = (m.get("fair_a_american") or 0)
        bms = (m.get("fair_b_american") or 0)
        print(f"  [{m['league']:20}] {m['team_a']:22} ({ams:+5d}) vs {m['team_b']:22} ({bms:+5d}) "
              f"BO{m['best_of']} -- P(A)={m['p_series_a']*100:5.1f}%")
