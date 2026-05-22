"""
EdgeStat -- MLB starter pitch-count danger zone alerts.

For each starting pitcher tonight, projects:
  - expected_pitches_per_out (from K-rate + WHIP)
  - workload_status based on recent starts:
      * GREEN:   workload normal, manager keeps starter in until 90+ pitches
      * YELLOW:  recent 100+ pitch outing or extra-inning bullpen call
      * RED:     coming off 110+ pitch start in last 5 days, expect short leash
      * EMERGENCY: returning from IL or back-to-back short rest

Used to bias:
  - mlb_pitcher_outs_props UNDER on RED/EMERGENCY
  - mlb_pitcher_strikeouts_props UNDER on RED
  - mlb_team_total_edge OVER on opposing offense when starter is RED

Output: data/mlb_starter_pitch_count_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _status(pitches_last_start: float, pitches_5_days: float,
            days_rest: float, returning_from_il: bool) -> str:
    """Classify danger level."""
    if returning_from_il:
        return "EMERGENCY"
    if pitches_last_start >= 110 and days_rest <= 4:
        return "RED"
    if pitches_last_start >= 100 or pitches_5_days >= 180:
        return "YELLOW"
    return "GREEN"


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    rest_data = _load(os.path.join(DATA_DIR, "mlb_pitcher_rest_advantage.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    rest_idx = {(r.get("pitcher") or "").lower(): r
                for r in (rest_data.get("rows") or []) if isinstance(r, dict)}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_l = sp_name.lower()
            sp_row = p_by_name.get(sp_l, {})
            recent = sp_row.get("recent") or {}

            pitches_last = _safe(recent.get("pitches_last_start"), 95.0)
            pitches_5d = _safe(recent.get("pitches_last_5_days"), 95.0)
            rest_row = rest_idx.get(sp_l, {})
            days_rest = _safe(rest_row.get("days_rest"), 5.0)
            returning_from_il = bool(recent.get("returning_from_il", False))

            status = _status(pitches_last, pitches_5d, days_rest, returning_from_il)

            leans: List[str] = []
            if status == "EMERGENCY":
                leans = ["OUTS_UNDER", "K_UNDER", "OPP_TT_OVER", "QS_NO"]
            elif status == "RED":
                leans = ["OUTS_UNDER", "K_UNDER", "QS_NO"]
            elif status == "YELLOW":
                leans = ["OUTS_LEAN_UNDER"]

            # Expected pitches per out (proxy from K9 + WHIP)
            stats = sp_row.get("stats") or {}
            k9 = _safe(stats.get("k_per_9"), 8.5)
            whip = _safe(stats.get("whip"), 1.30)
            # Higher K9 = more pitches per out (Ks take more pitches than balls in play)
            ppo = 4.5 + (k9 - 8.5) * 0.15 + (whip - 1.30) * 1.5
            ppo = max(3.8, min(7.0, ppo))

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "pitches_last_start": pitches_last,
                "pitches_last_5_days": pitches_5d,
                "days_rest": days_rest,
                "returning_from_il": returning_from_il,
                "status": status,
                "pitches_per_out_expected": round(ppo, 2),
                "expected_max_pitches": 95 if status == "RED" else (85 if status == "EMERGENCY" else 100),
                "expected_max_outs": round(95 / ppo, 1) if status == "RED" else round(100 / ppo, 1),
                "leans": leans,
            })

    rows.sort(key=lambda r: (
        {"EMERGENCY": 0, "RED": 1, "YELLOW": 2, "GREEN": 3}.get(r["status"], 4),
        -r["pitches_last_start"]
    ))

    n_red = sum(1 for r in rows if r["status"] == "RED")
    n_yellow = sum(1 for r in rows if r["status"] == "YELLOW")
    n_emergency = sum(1 for r in rows if r["status"] == "EMERGENCY")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_emergency": n_emergency,
        "n_red": n_red,
        "n_yellow": n_yellow,
        "method_note": "Pitch-count classifier: EMERGENCY (IL return), RED (110+ in last "
                       "start <=4 days rest), YELLOW (100+ pitches recent), GREEN normal. "
                       "Drives OUTS_UNDER + K_UNDER + opp_TT_OVER leans.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitch-cnt] {o['n_starters']} starters, {o['n_emergency']}/EMERGENCY "
          f"{o['n_red']}/RED {o['n_yellow']}/YELLOW -> {OUT}")
