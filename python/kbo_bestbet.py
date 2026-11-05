"""
EdgeStat -- KBO model projection board (formerly "Play of the Day") from kbo_props.

(2026-11-03) NOT A PICK: ML rows are chosen by a 54-72% model-probability
band with no sportsbook price behind them, from an unvalidated Poisson/ELO
model on seed ratings. Field names (top_bet / runners_up) are kept for
consumers, but every row carries is_pick=False + not_a_pick_reason,
confidence is "UNVALIDATED", and bet_key no longer embeds the fair price.
The OVER/UNDER 8.5 branch was deleted: it hard-coded prob 0.55 and fair -120
against an assumed 8.5 line -- invented numbers, not model output or a book
line.
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "kbo_props.json")
OUT_PATH = os.path.join(DATA_DIR, "kbo_bestbet.json")
NOT_A_PICK_REASON = "no sportsbook price; model unvalidated"   # (2026-11-03)


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
                    "bet_key": f"KBO|{team}|ML|model_projection",
                    "is_pick": False,
                    "not_a_pick_reason": NOT_A_PICK_REASON,
                    "match_id": f"{g.get('home_team')}|{g.get('away_team')}",
                    "game_id": g.get("game_id"),
                    "game_date": g.get("game_date"),
                    "home_team": g.get("home_team"),
                    "away_team": g.get("away_team"),
                })
        # (2026-11-03) OVER/UNDER 8.5 branch deleted: prob 0.55 / fair -120 /
        # the 8.5 line were all hard-coded constants, not model or book data.

    if not cands:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "no KBO games to project",
            "top_bet": None,
            "runners_up": [],
        }
    else:
        cands.sort(key=lambda c: -c["quality"])
        # (2026-11-03) HIGH/MED/LOW removed: a band score is not a confidence
        for c in cands:
            c["confidence"] = "UNVALIDATED"
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "label": "model projection -- unvalidated, no sportsbook price, not a recommendation",
            "is_pick": False,
            "not_a_pick_reason": NOT_A_PICK_REASON,
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
        print(f"KBO model projection (NOT a pick: {b['not_a_pick_reason']}): {b['label']} -- model P={b['prob']*100:.1f}%")
    else:
        print(f"KBO projection: {p.get('note')}")
