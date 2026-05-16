"""
EdgeStat -- forecast weather drift detector.

Compares the current weather for each game (today.json) with the prior
snapshot of weather from earlier in the day. If wind or temp has shifted
materially (>= 3mph wind change OR >= 5F temp), the per-game HR-mult
changes and you may need to re-evaluate weather-leveraged bets.

Output: data/weather_drift.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
PREV_PATH = os.path.join(DATA_DIR, ".weather_prev.json")
OUT_PATH = os.path.join(DATA_DIR, "weather_drift.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    prev = _load(PREV_PATH).get("by_matchup") or {}
    curr: Dict[str, Dict[str, Any]] = {}
    drifts: List[Dict[str, Any]] = []

    for g in today.get("games") or []:
        m = g.get("matchup")
        if not m:
            continue
        w = g.get("weather") or {}
        curr[m] = {"temp_f": w.get("temp_f"), "wind_mph": w.get("wind_mph"),
                    "wind_dir_deg": w.get("wind_dir_deg"), "is_indoor": w.get("is_indoor")}
        if m not in prev:
            continue
        p = prev[m]
        if w.get("is_indoor"):
            continue
        t_delta = (w.get("temp_f") or 0) - (p.get("temp_f") or 0)
        wind_delta = (w.get("wind_mph") or 0) - (p.get("wind_mph") or 0)
        dir_delta = abs(((w.get("wind_dir_deg") or 0) - (p.get("wind_dir_deg") or 0))) % 360
        if dir_delta > 180:
            dir_delta = 360 - dir_delta
        material = abs(t_delta) >= 5 or abs(wind_delta) >= 3 or dir_delta >= 45
        if material:
            note_bits = []
            if abs(t_delta) >= 5:
                note_bits.append(f"temp {p['temp_f']}°F -> {w['temp_f']}°F ({t_delta:+d}°)")
            if abs(wind_delta) >= 3:
                note_bits.append(f"wind {p['wind_mph']}mph -> {w['wind_mph']}mph ({wind_delta:+d}mph)")
            if dir_delta >= 45:
                note_bits.append(f"wind direction shifted {dir_delta}°")
            drifts.append({
                "matchup": m,
                "prev": p,
                "curr": curr[m],
                "temp_delta": t_delta,
                "wind_delta": wind_delta,
                "wind_dir_delta": dir_delta,
                "note": "; ".join(note_bits),
                "severity": "high" if (abs(t_delta) >= 10 or abs(wind_delta) >= 8) else "moderate",
            })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(curr),
        "n_drifts": len(drifts),
        "drifts": drifts,
    }
    with open(PREV_PATH, "w") as f:
        json.dump({"by_matchup": curr, "saved": payload["generated_at"]}, f)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_drifts']} weather drifts across {p['n_games']} games")
    for d in p["drifts"][:5]:
        print(f"  {d['matchup']:18} [{d['severity']}] {d['note']}")
