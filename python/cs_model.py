"""
EdgeStat -- Counter-Strike (CS2) ELO win-probability model.

Mirrors lol_model but uses HLTV-style 1000-1800 ELO scale baked into
cs_pipeline.HLTV_TOP_TEAMS. Self-learning: updates ELO when match scores
become available (currently most data is upcoming).

Output: data/cs_props.json + data/cs_elo.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "cs_state.json")
ELO_PATH = os.path.join(DATA_DIR, "cs_elo.json")
OUT_PATH = os.path.join(DATA_DIR, "cs_props.json")

K_FACTOR = 20
DEFAULT_ELO = 1450


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


def _elo_winprob(elo_a: float, elo_b: float) -> float:
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def _series_win_prob(p_map: float, best_of: int) -> float:
    if best_of <= 1:
        return p_map
    target = (best_of + 1) // 2
    total = 0.0
    for opp_wins in range(target):
        c = math.comb(target - 1 + opp_wins, opp_wins)
        total += c * (p_map ** target) * ((1 - p_map) ** opp_wins)
    return min(0.999, max(0.001, total))


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    matches = state.get("matches") or []
    top_teams = state.get("top_teams") or []

    # Seed ELO from HLTV-style top teams (cs_pipeline maintains these)
    seed_elo = {t["name"]: t["rating"] for t in top_teams}
    elo_store = _load(ELO_PATH)
    elo: Dict[str, float] = dict(seed_elo)
    elo.update(elo_store.get("teams") or {})

    seen_ids = set(elo_store.get("processed_match_ids") or [])

    # Update from completed matches (rare for CS via Liquipedia; mostly upcoming)
    for m in matches:
        if not m.get("is_completed"):
            continue
        mid = m.get("id") or f"{m['team_a']}|{m['team_b']}|{m.get('start_time','')}"
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        a, b = m["team_a"], m["team_b"]
        if a not in elo: elo[a] = DEFAULT_ELO
        if b not in elo: elo[b] = DEFAULT_ELO
        sa = m.get("score_a") or 0
        sb = m.get("score_b") or 0
        if sa + sb == 0:
            continue
        actual_a = 1.0 if sa > sb else 0.0 if sb > sa else 0.5
        expected_a = _elo_winprob(elo[a], elo[b])
        margin = abs(sa - sb)
        margin_mult = 1.0 + math.log1p(margin) * 0.3
        delta = K_FACTOR * margin_mult * (actual_a - expected_a)
        elo[a] += delta
        elo[b] -= delta

    _save(ELO_PATH, {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(elo),
        "teams": elo,
        "processed_match_ids": list(seen_ids)[-2000:],
    })

    preds: List[Dict[str, Any]] = []
    for m in matches:
        if m.get("is_completed"):
            continue
        a, b = m["team_a"], m["team_b"]
        elo_a = elo.get(a, DEFAULT_ELO)
        elo_b = elo.get(b, DEFAULT_ELO)
        p_map_a = _elo_winprob(elo_a, elo_b)
        best_of = m.get("best_of") or 3
        p_series_a = _series_win_prob(p_map_a, best_of)
        preds.append({
            **m,
            "elo_a": round(elo_a, 1),
            "elo_b": round(elo_b, 1),
            "p_map_a": round(p_map_a, 4),
            "p_series_a": round(p_series_a, 4),
            "p_series_b": round(1 - p_series_a, 4),
            "fair_a_american": _american(p_series_a),
            "fair_b_american": _american(1 - p_series_a),
            "p_sweep_a": round(p_map_a ** ((best_of + 1) // 2), 4),
            "p_sweep_b": round((1 - p_map_a) ** ((best_of + 1) // 2), 4),
        })

    preds.sort(key=lambda p: (
        0 if p.get("is_in_progress") else 1,
        p.get("start_time", "") or "z"
    ))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_matches": len(preds),
        "n_teams_rated": len(elo),
        "predictions": preds,
    }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_matches']} CS predictions, {p['n_teams_rated']} teams rated")
    for m in p["predictions"][:8]:
        a_ams = m.get("fair_a_american") or 0
        b_ams = m.get("fair_b_american") or 0
        print(f"  {m['team_a']:18} ({a_ams:+5d}) vs {m['team_b']:18} ({b_ams:+5d}) BO{m.get('best_of',3)} -- P(A)={m['p_series_a']*100:5.1f}%")
