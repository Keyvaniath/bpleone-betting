"""
EdgeStat -- training feedback log.

Every cron writes a one-line "what changed since the last refresh" entry
so Brandon (or any operator) can SEE the loop ticking forward:
  - Which markets had their correction_factor move (and by how much)
  - Which players were newly flagged in player_bias
  - Confidence score delta
  - Any new anomalies

Output: data/training_feedback.json (rolling list, last 30 entries)
  {
    "entries": [
      {
        "ts": "2026-05-15T18:30:00",
        "confidence_score": 73.6, "confidence_delta": +0.4,
        "calibration_moves": [{"market": "batter_total_bases", "cf_from": 0.832, "cf_to": 0.831, "n_added": 12}],
        "new_player_overrides": ["Tyler Glasnow K"],
        "new_anomalies": [],
        "summary": "Confidence +0.4 | TB correction held 0.83 | +12 settled props"
      }
    ]
  }

Front-end /training reads this and renders the last 5 entries as a feed.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CONFIDENCE_PATH = os.path.join(DATA_DIR, "model_confidence.json")
CALIBRATION_PATH = os.path.join(DATA_DIR, "calibration_live.json")
PLAYER_BIAS_PATH = os.path.join(DATA_DIR, "player_bias.json")
ANOMALIES_PATH = os.path.join(DATA_DIR, "anomalies.json")
OUT_PATH = os.path.join(DATA_DIR, "training_feedback.json")
PREV_SNAPSHOT_PATH = os.path.join(DATA_DIR, ".feedback_prev.json")

MAX_HISTORY = 30


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    now = dt.datetime.now()
    conf = _load(CONFIDENCE_PATH)
    cal = _load(CALIBRATION_PATH)
    pb = _load(PLAYER_BIAS_PATH)
    anom = _load(ANOMALIES_PATH)
    prev = _load(PREV_SNAPSHOT_PATH)

    # 1. Confidence delta
    score = conf.get("score")
    prev_score = prev.get("confidence_score")
    conf_delta = round(score - prev_score, 2) if (score is not None and prev_score is not None) else None

    # 2. Calibration moves (per market)
    moves = []
    curr_markets = cal.get("markets", {})
    prev_markets = prev.get("calibration_markets", {})
    for mk, v in curr_markets.items():
        prev_v = prev_markets.get(mk) or {}
        cf_now = v.get("correction_factor")
        cf_prev = prev_v.get("correction_factor")
        n_now = v.get("n", 0)
        n_prev = prev_v.get("n", 0)
        if cf_now is None:
            continue
        delta_cf = round(cf_now - cf_prev, 4) if cf_prev is not None else None
        delta_n = n_now - n_prev
        if delta_n > 0 or (delta_cf is not None and abs(delta_cf) > 0.001):
            moves.append({
                "market": mk,
                "cf_from": cf_prev,
                "cf_to": cf_now,
                "cf_delta": delta_cf,
                "n_added": delta_n,
            })

    # 3. New player overrides
    curr_pb_keys = set((pb.get("by_pid_market") or {}).keys())
    prev_pb_keys = set(prev.get("player_bias_keys") or [])
    added_pb = list(curr_pb_keys - prev_pb_keys)
    removed_pb = list(prev_pb_keys - curr_pb_keys)
    new_player_overrides = []
    for k in added_pb[:5]:
        info = (pb.get("by_pid_market") or {}).get(k) or {}
        new_player_overrides.append(f"{info.get('player', k)} {info.get('market', '').replace('_',' ')}")

    # 4. New systematic anomalies
    curr_anom_keys = set((a.get("player", "") + "|" + a.get("market", "")
                          for a in (anom.get("systematic") or [])))
    prev_anom_keys = set(prev.get("anomaly_keys") or [])
    new_anomalies = list(curr_anom_keys - prev_anom_keys)[:5]

    # Compose summary
    bits = []
    if conf_delta is not None and abs(conf_delta) > 0.05:
        bits.append(f"Confidence {'+' if conf_delta >= 0 else ''}{conf_delta}")
    if moves:
        bits.append(f"{len(moves)} markets updated")
    if new_player_overrides:
        bits.append(f"{len(new_player_overrides)} new player overrides")
    if new_anomalies:
        bits.append(f"{len(new_anomalies)} new anomalies")
    if removed_pb:
        bits.append(f"{len(removed_pb)} player overrides cleared")
    if not bits:
        bits.append("no material changes")
    summary = " | ".join(bits)

    entry = {
        "ts": now.isoformat(timespec="seconds"),
        "confidence_score": score,
        "confidence_delta": conf_delta,
        "calibration_moves": moves[:10],
        "new_player_overrides": new_player_overrides,
        "removed_player_overrides": removed_pb[:5],
        "new_anomalies": new_anomalies,
        "summary": summary,
    }

    # Append to history
    history = _load(OUT_PATH).get("entries") or []
    history.append(entry)
    history = history[-MAX_HISTORY:]
    payload = {"entries": history, "generated_at": now.isoformat(timespec="seconds")}

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    # Update prev snapshot for next run's diff
    with open(PREV_SNAPSHOT_PATH, "w") as f:
        json.dump({
            "confidence_score": score,
            "calibration_markets": curr_markets,
            "player_bias_keys": list(curr_pb_keys),
            "anomaly_keys": list(curr_anom_keys),
        }, f)
    return payload


if __name__ == "__main__":
    p = run()
    last = p["entries"][-1] if p["entries"] else {}
    print(f"Wrote {OUT_PATH}: {len(p['entries'])} history entries")
    print(f"  Latest: {last.get('summary')}")
