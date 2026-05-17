"""
EdgeStat -- daily prediction log (append-only learning record).

Each cron, captures every model prediction (across all sports) with a unique
key and timestamps. On subsequent runs, settles past entries when game
outcomes appear in historical_*.json. This builds the long-term track record
that drives self_train.py's calibration shifts.

Sport-by-sport state grows over time, becoming the system's
"experience memory". Key fields:
  - game_id, sport, matchup, prediction_date
  - pre_game_p_home_win (immutable snapshot)
  - fair_home_american, fair_away_american
  - settled: bool
  - actual_winner, actual_margin, actual_total
  - residual_p (predicted - actual), squared_error

Output: data/prediction_log.json (append-only, cap 10000 entries)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LOG_PATH = os.path.join(DATA_DIR, "prediction_log.json")

SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "ucl", "nfl", "ncaaf", "ncaab", "cws", "mlb", "kbo"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _key(sport: str, g: Dict[str, Any]) -> str:
    return f"{sport}|{g.get('id') or g.get('matchup','')}"


def run() -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    log = _load(LOG_PATH)
    entries = log.get("entries") or []
    by_key = {e["key"]: e for e in entries}

    # 1. Capture today's predictions (for any pre-game game)
    new_count = 0
    for sport in SPORTS:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        for g in (state.get("games") or []):
            if g.get("state") != "pre": continue
            key = _key(sport, g)
            if key in by_key: continue
            entry = {
                "key": key, "sport": sport,
                "captured_on": today,
                "matchup": g.get("matchup"),
                "home_team": g.get("home_team"),
                "away_team": g.get("away_team"),
                "pre_game_p_home_win": g.get("p_home_win"),
                "pre_game_p_home_raw": g.get("p_home_win_raw"),
                "calibration_shift_pp_applied": g.get("calibration_shift_pp"),
                "fair_home_american": g.get("fair_home_american"),
                "fair_away_american": g.get("fair_away_american"),
                "home_elo": g.get("home_elo"),
                "away_elo": g.get("away_elo"),
                "settled": False,
                "outcome": "PENDING",
            }
            by_key[key] = entry
            new_count += 1

    # 2. Settle entries from historicals
    settled_count = 0
    for sport in SPORTS:
        h = _load(os.path.join(DATA_DIR, f"historical_{sport}.json"))
        games = h.get("games") or []
        for g in games:
            # Find matching entry by sport + home + away
            for key, e in list(by_key.items()):
                if e.get("settled"): continue
                if e["sport"] != sport: continue
                if e.get("home_team") == g.get("home_team") and e.get("away_team") == g.get("away_team"):
                    p = e.get("pre_game_p_home_win") or 0.5
                    actual = 1 if g["home_score"] > g["away_score"] else 0 if g["away_score"] > g["home_score"] else 0.5
                    e["settled"] = True
                    e["outcome"] = "HOME_WIN" if actual == 1 else "AWAY_WIN" if actual == 0 else "TIE"
                    e["actual_margin"] = g["margin"]
                    e["actual_total"] = g["total"]
                    e["actual_winner"] = g.get("winner")
                    e["actual_home_score"] = g["home_score"]
                    e["actual_away_score"] = g["away_score"]
                    e["residual_p"] = round(p - actual, 4)
                    e["squared_error"] = round((p - actual) ** 2, 4)
                    settled_count += 1
                    break

    # Cap to last 10000 entries
    all_entries = list(by_key.values())
    all_entries.sort(key=lambda x: x.get("captured_on", ""), reverse=True)
    all_entries = all_entries[:10000]

    settled = [e for e in all_entries if e.get("settled")]
    pending = [e for e in all_entries if not e.get("settled")]

    # Compute aggregate metrics across settled
    if settled:
        total_brier = sum(e.get("squared_error", 0) for e in settled) / len(settled)
        correct = sum(1 for e in settled if (e.get("pre_game_p_home_win") or 0.5) >= 0.5
                       and e.get("outcome") == "HOME_WIN") + sum(
                   1 for e in settled if (e.get("pre_game_p_home_win") or 0.5) < 0.5
                       and e.get("outcome") == "AWAY_WIN")
        hit_rate = correct / len(settled)
    else:
        total_brier = None
        hit_rate = None

    by_sport: Dict[str, Dict[str, int]] = {}
    for e in all_entries:
        s = e["sport"]
        by_sport.setdefault(s, {"total": 0, "settled": 0, "pending": 0})
        by_sport[s]["total"] += 1
        if e.get("settled"): by_sport[s]["settled"] += 1
        else: by_sport[s]["pending"] += 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_total_predictions_tracked": len(all_entries),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_new_this_run": new_count,
        "n_settled_this_run": settled_count,
        "aggregate_hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
        "aggregate_brier": round(total_brier, 4) if total_brier is not None else None,
        "by_sport": by_sport,
        "entries": all_entries,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Prediction log: {p['n_total_predictions_tracked']} total "
          f"({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  New this run: {p['n_new_this_run']} | Settled this run: {p['n_settled_this_run']}")
    if p["aggregate_hit_rate"] is not None:
        print(f"  Aggregate hit rate: {p['aggregate_hit_rate']*100:.1f}% | Brier: {p['aggregate_brier']}")
    print(f"  By sport: {p['by_sport']}")
