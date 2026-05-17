"""
EdgeStat -- Counter-Strike Play of the Day. Picks top 3 plays from upcoming CS matches.
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "cs_props.json")
OUT_PATH = os.path.join(DATA_DIR, "cs_bestbet.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    matches = props.get("predictions") or []
    cands: List[Dict[str, Any]] = []
    for m in matches:
        p_a = m.get("p_series_a") or 0.5
        best_of = m.get("best_of") or 3
        for side, prob, fair, team, opp in (
            ("A", p_a, m.get("fair_a_american"), m.get("team_a"), m.get("team_b")),
            ("B", 1 - p_a, m.get("fair_b_american"), m.get("team_b"), m.get("team_a")),
        ):
            if not team: continue
            if 0.52 <= prob <= 0.78:
                sweet = 1.0 - abs(prob - 0.60) * 2
                bo_mult = 1.0 + (best_of - 1) * 0.08
                cands.append({
                    "kind": "ML",
                    "team": team,
                    "opponent": opp,
                    "prob": prob,
                    "fair_american": fair,
                    "quality": round(sweet * bo_mult, 4),
                    "best_of": best_of,
                    "tournament": m.get("tournament"),
                    "label": f"{team} ML vs {opp} (BO{best_of})",
                    "bet_key": f"CS|{team}|ML|{fair}",
                    "match_id": m.get("id") or f"{m.get('team_a')}|{m.get('team_b')}",
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
        for c in cands:
            c["confidence"] = "HIGH" if c["quality"] >= 0.95 else "MED" if c["quality"] >= 0.70 else "LOW"
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_candidates": len(cands),
            "top_bet": cands[0],
            "runners_up": cands[1:5],
        }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    if p.get("top_bet"):
        b = p["top_bet"]
        print(f"CS POD: {b['team']} ML ({b['fair_american']}) -- P={b['prob']*100:.1f}% Q={b['quality']} ({b['confidence']})")
