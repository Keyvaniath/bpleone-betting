"""
EdgeStat -- League of Legends Play of the Tournament + per-match best plays.

Picks the top 3-5 highest-quality LoL bets from upcoming + live matches.
Quality scored by:
  - Model probability in sweet spot (55-72% favorite or 28-45% underdog)
  - Top-tier league bias (LCK/LPL/LEC/LCS > regional)
  - Bo5 > Bo3 > Bo1 (more games = signal converges)
  - Sweep value flagged when |elo_diff| > 100

Output: data/lol_bestbet.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "lol_props.json")
OUT_PATH = os.path.join(DATA_DIR, "lol_bestbet.json")

TIER_1 = {"LCK", "LPL", "LEC", "LCS", "MSI", "Worlds", "First Stand"}
TIER_2 = {"PCS", "VCS", "CBLOL", "LLA", "LJL", "LCO", "EU Masters"}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f: json.dump(payload, f, indent=2)


def _score_match(m: Dict[str, Any]) -> Dict[str, Any]:
    p_a = m.get("p_series_a") or 0.5
    league = m.get("league", "")
    best_of = m.get("best_of") or 1

    # Tier multiplier
    tier_mult = 1.20 if league in TIER_1 else 1.05 if league in TIER_2 else 0.90
    # Bo-N multiplier
    bo_mult = 1.0 + (best_of - 1) * 0.10

    # Find playable side -- sweet spot is 55%-72% favorite OR 28%-45% dog
    candidates = []
    for side, prob, fair, team, opp in (
        ("A", p_a, m.get("fair_a_american"), m.get("team_a"), m.get("team_b")),
        ("B", 1 - p_a, m.get("fair_b_american"), m.get("team_b"), m.get("team_a")),
    ):
        if not team: continue
        if 0.52 <= prob <= 0.78:
            sweet = 1.0 - abs(prob - 0.60) * 2
            quality = sweet * tier_mult * bo_mult
            candidates.append({
                "kind": "ML",
                "side": side,
                "team": team,
                "opponent": opp,
                "prob": prob,
                "fair_american": fair,
                "quality": quality,
                "league": league,
                "best_of": best_of,
            })

    # Sweep candidate: if elo diff strong (>100) and Bo3+, suggest sweep
    elo_diff = abs((m.get("elo_a") or 0) - (m.get("elo_b") or 0))
    if elo_diff >= 100 and best_of >= 3:
        if (m.get("elo_a") or 0) > (m.get("elo_b") or 0):
            p_sweep = m.get("p_sweep_a") or 0
            fair = m.get("fair_sweep_a_american")
            team, opp = m.get("team_a"), m.get("team_b")
        else:
            p_sweep = m.get("p_sweep_b") or 0
            fair = None
            team, opp = m.get("team_b"), m.get("team_a")
        if 0.30 <= p_sweep <= 0.55:
            candidates.append({
                "kind": "SWEEP",
                "side": "sweep",
                "team": team,
                "opponent": opp,
                "prob": p_sweep,
                "fair_american": fair,
                "quality": (1.0 - abs(p_sweep - 0.40) * 2) * tier_mult * 1.2,
                "league": league,
                "best_of": best_of,
            })

    return candidates


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    matches = props.get("predictions") or []
    cands: List[Dict[str, Any]] = []
    for m in matches:
        for c in _score_match(m):
            cands.append({
                **c,
                "match_id": m.get("id"),
                "start_time": m.get("start_time"),
                "label": (
                    f"{c['team']} ML vs {c['opponent']} ({c['league']}, BO{c['best_of']})"
                    if c["kind"] == "ML"
                    else f"{c['team']} {c['best_of']//2+1}-0 SWEEP vs {c['opponent']} ({c['league']})"
                ),
                "bet_key": f"LOL|{c['team']}|{c['kind']}|{c['fair_american']}",
            })

    if not cands:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no qualifying matches",
            "top_bet": None,
            "runners_up": [],
        }
    else:
        cands.sort(key=lambda c: -c["quality"])
        def conf(q):
            if q >= 0.95: return "HIGH"
            if q >= 0.70: return "MED"
            return "LOW"
        for c in cands:
            c["confidence"] = conf(c["quality"])
            c["quality"] = round(c["quality"], 4)
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_candidates": len(cands),
            "top_bet": cands[0],
            "runners_up": cands[1:5],
        }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    if p.get("top_bet"):
        b = p["top_bet"]
        print(f"LoL POT: {b['kind']} {b['team']} ({b['fair_american']}) -- "
              f"P={b['prob']*100:.1f}% Q={b['quality']} ({b['confidence']})")
        for r in p.get("runners_up", []):
            print(f"  runner-up: {r['kind']} {r['team']} ({r['fair_american']}) P={r['prob']*100:.1f}%")
    else:
        print(f"LoL POT: {p.get('note')}")
