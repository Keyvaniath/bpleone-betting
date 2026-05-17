"""
EdgeStat -- KBO Play of the Day from kbo_props.
Includes ML, total OVER/UNDER, runline (-1.5/+1.5) candidates.
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "kbo_props.json")
OUT_PATH = os.path.join(DATA_DIR, "kbo_bestbet.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH)
    games = props.get("predictions") or []
    cands: List[Dict[str, Any]] = []
    for g in games:
        ph = g.get("p_home_win") or 0.5
        # ML sweet spot
        for side, prob, fair, team, opp in (
            ("HOME", ph, g.get("fair_home_american"), g.get("home_team"), g.get("away_team")),
            ("AWAY", 1 - ph, g.get("fair_away_american"), g.get("away_team"), g.get("home_team")),
        ):
            if 0.54 <= prob <= 0.72:
                sweet = 1.0 - abs(prob - 0.60) * 2.5
                cands.append({
                    "kind": "ML",
                    "side": side,
                    "team": team,
                    "opponent": opp,
                    "prob": prob,
                    "fair_american": fair,
                    "quality": round(sweet, 4),
                    "label": f"{team} ML vs {opp} (KBO)",
                    "bet_key": f"KBO|{team}|ML|{fair}",
                    "match_id": f"{g.get('home_team')}|{g.get('away_team')}",
                })
        # Total OVER/UNDER (any divergence from common 8.5 line)
        model_total = g.get("model_total") or 9
        if model_total >= 10:
            cands.append({
                "kind": "OVER",
                "team": f"{g.get('away_team')} @ {g.get('home_team')}",
                "opponent": None,
                "prob": 0.55,
                "fair_american": -120,
                "quality": 0.7,
                "label": f"OVER 8.5 (model {model_total} runs)",
                "bet_key": f"KBO|{g.get('home_team')}|OVER|-120",
                "match_id": f"{g.get('home_team')}|{g.get('away_team')}",
            })
        elif model_total <= 7:
            cands.append({
                "kind": "UNDER",
                "team": f"{g.get('away_team')} @ {g.get('home_team')}",
                "opponent": None,
                "prob": 0.55,
                "fair_american": -120,
                "quality": 0.7,
                "label": f"UNDER 8.5 (model {model_total} runs)",
                "bet_key": f"KBO|{g.get('home_team')}|UNDER|-120",
                "match_id": f"{g.get('home_team')}|{g.get('away_team')}",
            })

    if not cands:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no qualifying KBO bets",
            "top_bet": None,
            "runners_up": [],
        }
    else:
        cands.sort(key=lambda c: -c["quality"])
        for c in cands:
            c["confidence"] = "HIGH" if c["quality"] >= 0.92 else "MED" if c["quality"] >= 0.65 else "LOW"
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
        print(f"KBO POD: {b['label']} fair {b['fair_american']} -- P={b['prob']*100:.1f}% Q={b['quality']} ({b['confidence']})")
    else:
        print(f"KBO POD: {p.get('note')}")
