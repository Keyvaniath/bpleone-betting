"""
EdgeStat -- per-player streak chart data for /player.

For each player with 14+ settled props, generates rolling-window time
series (5-game and 10-game) for the primary stats they're bet on. Powers
sparklines and trend charts on the player deep-dive page.

Output: data/streak_charts.json keyed by player_id
"""
from __future__ import annotations
import os, json, datetime as dt
from collections import defaultdict
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "streak_charts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    props = _load(TR_PATH).get("props") or []
    by_player_market: Dict[Any, Dict[str, List]] = defaultdict(lambda: defaultdict(list))
    for p in props:
        pid = p.get("player_id")
        market = p.get("market")
        if pid is None or market is None:
            continue
        actual = p.get("actual")
        line = p.get("line")
        date = p.get("date")
        if actual is None or date is None:
            continue
        by_player_market[pid][market].append({"date": date, "actual": actual, "line": line})

    out: Dict[str, Any] = {}
    for pid, by_market in by_player_market.items():
        total_n = sum(len(v) for v in by_market.values())
        if total_n < 14:
            continue
        player_payload = {}
        for market, rows in by_market.items():
            rows.sort(key=lambda x: x["date"])
            rows_last30 = rows[-30:]
            # Rolling 5-game avg
            roll = []
            for i in range(len(rows_last30)):
                window = rows_last30[max(0, i - 4): i + 1]
                roll.append({"date": rows_last30[i]["date"],
                              "actual": rows_last30[i]["actual"],
                              "rolling_5": round(sum(r["actual"] for r in window) / len(window), 2)})
            player_payload[market] = {
                "n_total": len(rows),
                "series": roll[-20:],
            }
        out[str(pid)] = player_payload
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_players": len(out),
        "by_player": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_players']} players with streak charts")
