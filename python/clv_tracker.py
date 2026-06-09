"""
EdgeStat -- Closing Line Value (CLV) from the free odds history.

CLV is the single metric sharp bettors live by: did the market move TOWARD your
side by the time the line closed? If you consistently get a better number than
the close, you have a real edge -- independent of whether any single bet won.

For every game where the model has a moneyline lean (book_vs_model_team.json) and
the odds history (espn_odds.py) has both an opening and a later/closing snapshot,
this computes:
  CLV (pp) = implied_prob(our side at close) - implied_prob(our side at open)
  -> positive means the line shortened on our side (the market came to us; we'd
     have beaten the closing number).
Then it aggregates: how often the close moved our way (beat-the-close rate) and
the average CLV in percentage points -- the honest, market-validated read on the
model's game-line edge. 100% free, no paid key.

NOTE: this is GAME-LINE CLV (ESPN's free feed is game lines only). It grows as
the heartbeat polls open->close through the day; with <2 snapshots it reports
"pending".

Output: data/clv_tracker.json -> clv.html
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY = os.path.join(DATA_DIR, "odds_history.json")
BVM = os.path.join(DATA_DIR, "book_vs_model_team.json")
OUT = os.path.join(DATA_DIR, "clv_tracker.json")


def _load(p) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _implied(american) -> Optional[float]:
    if american is None:
        return None
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    return 100.0 / (a + 100.0) if a >= 0 else abs(a) / (abs(a) + 100.0)


def run() -> Dict[str, Any]:
    hist = _load(HISTORY).get("history") or {}
    # latest model moneyline lean per matchup (HOME/AWAY + the team)
    leans: Dict[str, Dict[str, Any]] = {}
    for e in (_load(BVM).get("all_edges") or []):
        mk = e.get("matchup")
        if mk and mk not in leans:
            leans[mk] = {"side": e.get("side"), "team": e.get("team"),
                         "model_prob": e.get("model_prob"), "edge_pct": e.get("calibrated_edge_pct")}

    rows: List[Dict[str, Any]] = []
    for key, seq in hist.items():
        if not isinstance(seq, list) or len(seq) < 2:
            continue
        try:
            sport, matchup, gdate = key.split("|")
        except ValueError:
            continue
        lean = leans.get(matchup)
        if not lean or lean.get("side") not in ("HOME", "AWAY"):
            continue
        o, c = seq[0], seq[-1]
        side = lean["side"]
        ml_field = "ml_home" if side == "HOME" else "ml_away"
        imp_open, imp_close = _implied(o.get(ml_field)), _implied(c.get(ml_field))
        if imp_open is None or imp_close is None:
            continue
        clv_pp = round((imp_close - imp_open) * 100, 2)
        rows.append({
            "sport": sport, "matchup": matchup, "game_date": gdate,
            "side": side, "team": lean.get("team"),
            "open_american": o.get(ml_field), "close_american": c.get(ml_field),
            "clv_pp": clv_pp,
            "beat_close": clv_pp > 0,
            "model_edge_pct": lean.get("edge_pct"),
            "snapshots": len(seq),
        })

    rows.sort(key=lambda r: -r["clv_pp"])
    n = len(rows)
    beat = sum(1 for r in rows if r["beat_close"])
    avg_clv = round(sum(r["clv_pp"] for r in rows) / n, 2) if n else None
    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "source": "ESPN/DraftKings free odds history (no key)",
        "scope": "game-line moneyline leans (model vs market)",
        "n_tracked": n,
        "n_beat_close": beat,
        "beat_close_rate": round(beat / n, 3) if n else None,
        "avg_clv_pp": avg_clv,
        "status": "ok" if n else "pending — needs >=2 odds snapshots per game (fills in as the heartbeat polls open->close)",
        "note": "CLV = implied-prob shift on the model's side from open to close. Positive = "
                "the market moved to us by close (we beat the closing number). The metric that "
                "proves edge vs the market, independent of any single bet's result.",
        "rows": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[clv] {o['n_tracked']} leans tracked | beat-close {o['n_beat_close']}/{o['n_tracked']} "
          f"({o['beat_close_rate']}) | avg CLV {o['avg_clv_pp']}pp | {o['status']}")
    for r in o["rows"][:8]:
        print(f"    {r['sport']:4s} {r['matchup']:14s} {r['side']:4s} {r['team']:4s} "
              f"{r['open_american']:+d}->{r['close_american']:+d}  CLV {r['clv_pp']:+.1f}pp "
              f"{'BEAT' if r['beat_close'] else 'lost'}")
