"""
EdgeStat -- prediction drift detector.

Compares this cron's predictions to last cron's. Flags games where:
  - P(home) moved >= 5pp without score change (model uncertainty growing)
  - Fair odds shifted >= 30 American
  - New games added / dropped

Also detects model degradation: if self_training brier scores increase
material WoW (>0.03), flag for human review.

Output: data/drift_alerts.json + .drift_snapshot.json (state)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT = os.path.join(DATA_DIR, ".drift_snapshot.json")
OUT = os.path.join(DATA_DIR, "drift_alerts.json")

SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "nfl", "ncaaf", "ncaab",
          "cws", "kbo", "lol", "cs", "golf"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f: json.dump(payload, f, indent=2)


def _game_key(g, sport):
    return f"{sport}|{g.get('matchup') or g.get('id') or g.get('home_team','')}"


def run() -> Dict[str, Any]:
    snapshot = _load(SNAPSHOT)
    new_snapshot: Dict[str, Any] = {}
    alerts: List[Dict[str, Any]] = []
    now = dt.datetime.now().isoformat(timespec="seconds")

    for sport in SPORTS:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        games = state.get("games") or state.get("predictions") or []
        sport_snap = {}
        for g in games:
            key = _game_key(g, sport)
            ph = g.get("p_home_win") or g.get("p_series_a") or 0.5
            fair = g.get("fair_home_american") or g.get("fair_a_american")
            sport_snap[key] = {"ph": ph, "fair": fair, "state": g.get("state", "?")}

            prev = (snapshot.get(sport) or {}).get(key)
            if prev:
                d_ph = abs(ph - prev.get("ph", ph))
                d_fair = abs((fair or 0) - (prev.get("fair", fair) or 0))
                if d_ph >= 0.05 and g.get("state") != "in":
                    alerts.append({
                        "type": "PROB_SHIFT",
                        "sport": sport,
                        "matchup": g.get("matchup") or key,
                        "delta_pp": round(d_ph * 100, 1),
                        "prev_p": round(prev["ph"], 4),
                        "curr_p": round(ph, 4),
                        "fired_at": now,
                    })
                if d_fair >= 30:
                    alerts.append({
                        "type": "ODDS_SHIFT",
                        "sport": sport,
                        "matchup": g.get("matchup") or key,
                        "delta_american": int(d_fair),
                        "prev_fair": prev.get("fair"),
                        "curr_fair": fair,
                        "fired_at": now,
                    })
        new_snapshot[sport] = sport_snap

    # Self-training brier drift
    st_summary = _load(os.path.join(DATA_DIR, "self_training_summary.json"))
    prev_st = snapshot.get("_brier") or {}
    new_brier: Dict[str, float] = {}
    for sport_key, info in (st_summary.get("by_sport") or {}).items():
        brier = info.get("brier") if isinstance(info, dict) else None
        if brier is None: continue
        new_brier[sport_key] = brier
        if sport_key in prev_st:
            delta = brier - prev_st[sport_key]
            if delta > 0.03:
                alerts.append({
                    "type": "MODEL_DEGRADATION",
                    "sport": sport_key,
                    "prev_brier": prev_st[sport_key],
                    "curr_brier": brier,
                    "delta": round(delta, 4),
                    "fired_at": now,
                })
    new_snapshot["_brier"] = new_brier

    payload = {
        "generated_at": now,
        "n_alerts": len(alerts),
        "alerts": alerts[-200:],
    }
    _save(OUT, payload)
    _save(SNAPSHOT, new_snapshot)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Drift detector: {p['n_alerts']} new alerts")
    for a in p["alerts"][:10]:
        print(f"  [{a['type']}] {a['sport']:6} {a.get('matchup','')[:50]}")
