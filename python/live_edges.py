"""
EdgeStat -- live edge alerts.

Joins live_state.json (model's live win-probability from gumbo feed +
base-out RE24) with live_clv.json (Bovada's CURRENT live moneyline) and
flags games where model and book diverge by >= EDGE_THRESHOLD.

This is THE live-betting use case: when Brandon's watching a game and
the book has Yankees -180 live but the model says Yankees should be
-220, the +40 cents of value on the home ML is a live bet.

Output: data/live_edges.json
  {
    "polled_at": "...",
    "alerts": [
      {"matchup": "PHI @ PIT", "side": "HOME",
       "model_p_home_win": 0.62, "book_implied_p_home_win": 0.55,
       "edge_pct": 12.7, "live_state": "Top 5, 2 outs, 3-2",
       "current_ml": -135, "fair_ml": -163,
       "recommend": "live bet home -135 to fair -163 (+1.5u 0.25-Kelly)"}
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LIVE_STATE_PATH = os.path.join(DATA_DIR, "live_state.json")
LIVE_CLV_PATH = os.path.join(DATA_DIR, "live_clv.json")
OUT_PATH = os.path.join(DATA_DIR, "live_edges.json")

try:
    import config as _cfg
    EDGE_THRESHOLD = _cfg.get("live_edges.edge_threshold_pp") / 100.0
except Exception:
    EDGE_THRESHOLD = 0.05    # 5 percentage points -- real live-bet edge


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _implied(ml: Optional[int]) -> Optional[float]:
    if ml is None:
        return None
    return (100.0 / (ml + 100)) if ml >= 0 else ((-ml) / (-ml + 100))


def _fair_ml(prob: float) -> int:
    """Convert win probability to fair American moneyline."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return int(round(-prob / (1 - prob) * 100))
    return int(round((1 - prob) / prob * 100))


def _kelly_units(edge_pct: float, prob: float, bankroll_units: float = 100.0,
                  kelly_fraction: float = 0.25) -> float:
    """Quarter-Kelly stake in units. Cap at 1.5u to be conservative."""
    if prob <= 0 or prob >= 1:
        return 0.0
    decimal_odds = 1.0 / prob if prob > 0 else 0  # what we WOULD need at fair
    # Use the edge directly: fraction = edge / (decimal_odds - 1)
    if decimal_odds <= 1:
        return 0.0
    f = (edge_pct / 100.0) / (decimal_odds - 1)
    return round(min(1.5, max(0.0, f * kelly_fraction * bankroll_units / 100.0 * 4)), 2)


def _match_key(matchup: str) -> str:
    return matchup.replace(" ", "_").replace("@", "at").replace("__", "_")


def run() -> Dict[str, Any]:
    live_state = _load(LIVE_STATE_PATH)
    live_clv = _load(LIVE_CLV_PATH)
    games_state = live_state.get("games") or []
    games_clv = live_clv.get("games") or {}

    # Index live_clv games by matchup string so we can join
    clv_by_matchup: Dict[str, Dict[str, Any]] = {}
    for k, g in games_clv.items():
        mu = g.get("matchup")
        if mu:
            clv_by_matchup[mu] = g

    alerts = []
    for g in games_state:
        # live_state schema: {home, away, p_home_win, state, ...}
        # Need to derive matchup as "AWAY_CODE @ HOME_CODE" -- live_state uses
        # full names. Use the index pattern.
        home_name = g.get("home") or ""
        away_name = g.get("away") or ""
        # Try to find a matching CLV entry by partial team name match
        clv = None
        for mu, cg in clv_by_matchup.items():
            if " @ " in mu:
                away_code, home_code = mu.split(" @ ", 1)
                if (home_code.strip() in home_name) or (away_code.strip() in away_name):
                    # Heuristic: any code substring match counts. Better than nothing.
                    clv = cg
                    break
        if not clv:
            continue
        snaps = clv.get("snapshots") or []
        if not snaps:
            continue
        last = snaps[-1]
        if last.get("state") != "live":
            continue
        book_ml = last.get("home_ml")
        book_implied = _implied(book_ml)
        model_p = g.get("p_home_win")
        if book_implied is None or model_p is None:
            continue
        edge = model_p - book_implied  # positive = model thinks home is better than book
        if abs(edge) < EDGE_THRESHOLD:
            continue
        side = "HOME" if edge > 0 else "AWAY"
        prob_side = model_p if side == "HOME" else (1 - model_p)
        edge_pct = abs(edge) * 100
        # Fair ML on the bet side
        fair = _fair_ml(prob_side)
        # Recommended Kelly stake
        stake = _kelly_units(edge_pct, prob_side)
        # State summary
        s = g.get("state") or {}
        live_state_str = f"{s.get('inning_state','')} {s.get('inning','')}, {s.get('outs',0)}o"
        alerts.append({
            "matchup": clv.get("matchup"),
            "side": side,
            "model_p_home_win": round(model_p, 4),
            "book_implied_p_home_win": round(book_implied, 4),
            "edge_pp": round(edge * 100, 2),
            "edge_pct": round(edge_pct, 2),
            "live_state": live_state_str.strip(),
            "score": f"{g.get('home_runs', 0)}-{g.get('away_runs', 0)} {home_name} vs {away_name}",
            "current_ml": book_ml,
            "fair_ml": fair,
            "recommend_stake_units": stake,
        })

    alerts.sort(key=lambda a: a["edge_pct"], reverse=True)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "edge_threshold_pp": EDGE_THRESHOLD * 100,
        "n_alerts": len(alerts),
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Live edge alerts: {p['n_alerts']}")
    for a in p["alerts"][:5]:
        print(f"  {a['matchup']:15} {a['side']:5} edge={a['edge_pct']:.1f}pp  "
              f"book {a['current_ml']} vs fair {a['fair_ml']}  stake {a['recommend_stake_units']}u  "
              f"@ {a['live_state']}")
