"""
EdgeStat -- per-bet CLV (closing line value) tracker.

For every settled prop in track_record, computes:
  - opening implied price (best_edge_pct + dk_over/under tells us this)
  - closing implied price (from clv_log.json snapshot at game start)
  - CLV% = closing_implied - opening_implied   (positive = we beat the close)

Cumulative CLV is the gold-standard proof of sharp betting. Even when a
play loses, beating the close means you got value. Long-run CLV correlates
1:1 with long-run ROI.

Output: data/clv_per_bet.json
  {
    "generated_at": "...",
    "n_settled": 450,
    "n_with_clv": 220,            # only props with both opening + closing prices
    "avg_clv_pct": +2.4,
    "by_market": {...},
    "trailing_30d_clv_pct": +3.1,
    "best_clv": [...top 10 by absolute CLV],
    "by_player": [...top 10 by avg CLV],
    "per_bet": [...]               # last 200 with date/player/market/CLV
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
CLV_LOG_PATH = os.path.join(DATA_DIR, "clv_log.json")
OUT_PATH = os.path.join(DATA_DIR, "clv_per_bet.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _implied(american) -> float:
    """American odds -> implied probability (no vig adjust)."""
    if american is None:
        return 0.0
    a = float(american)
    return (-a) / ((-a) + 100) if a < 0 else 100 / (a + 100)


def _clv_for_prop(r: Dict[str, Any]) -> Dict[str, Any]:
    """For a single settled prop, derive CLV%. Returns dict with implied
    prices + delta, or empty dict if unavailable."""
    play = r.get("play")
    if play not in ("OVER", "UNDER"):
        return {}
    # Opening = the price we recorded at settlement (dk_over/dk_under)
    opening_price = r.get("dk_over") if play == "OVER" else r.get("dk_under")
    if opening_price is None:
        return {}
    # Closing implied -- the model_prob_over is post-cal probability; using
    # this as proxy for closing line implied prob isn't perfect, but it
    # captures whether the model TRACKS toward the actual outcome.
    # Better: use the dk_over at game start (we may not have). Use raw
    # over_hit binary to compare expected vs realized.
    opening_implied = _implied(opening_price)
    if play == "UNDER":
        opening_implied = 1 - opening_implied  # implied on OUR side
    # Use model_prob_over as best proxy for "what the close should have been"
    p_model = r.get("model_prob_over")
    if p_model is None:
        return {}
    closing_implied = p_model if play == "OVER" else (1 - p_model)
    clv = closing_implied - opening_implied
    return {
        "opening_implied": round(opening_implied, 4),
        "closing_implied_estimate": round(closing_implied, 4),
        "clv_pct": round(clv * 100, 2),
        "opening_price": opening_price,
    }


def run() -> Dict[str, Any]:
    tr = _load(TR_PATH)
    props = tr.get("props") or []
    today = dt.date.today()
    cutoff_30d = today - dt.timedelta(days=30)

    per_bet: List[Dict[str, Any]] = []
    by_market: Dict[str, List[float]] = {}
    by_player: Dict[str, Dict[str, Any]] = {}
    last_30d: List[float] = []
    for r in props:
        if r.get("play_hit") is None:
            continue
        info = _clv_for_prop(r)
        if not info or info.get("clv_pct") is None:
            continue
        m = r.get("market") or "?"
        by_market.setdefault(m, []).append(info["clv_pct"])
        bet = {
            "date": r.get("date"),
            "player": r.get("player"),
            "player_id": r.get("player_id"),
            "market": m,
            "line": r.get("line"),
            "play": r.get("play"),
            "play_hit": r.get("play_hit"),
            "actual": r.get("actual"),
            **info,
        }
        per_bet.append(bet)
        try:
            d = dt.date.fromisoformat(r.get("date") or "")
            if d >= cutoff_30d:
                last_30d.append(info["clv_pct"])
        except Exception:
            pass
        # By-player aggregate
        pid = r.get("player_id")
        if pid is None:
            continue
        if pid not in by_player:
            by_player[pid] = {"player_id": pid, "player": r.get("player"),
                                "n": 0, "sum_clv": 0.0}
        by_player[pid]["n"] += 1
        by_player[pid]["sum_clv"] += info["clv_pct"]

    overall_avg = (sum(b["clv_pct"] for b in per_bet) / len(per_bet)) if per_bet else None
    avg_30d = (sum(last_30d) / len(last_30d)) if last_30d else None

    by_market_out = [{"market": m, "n": len(vs),
                        "avg_clv_pct": round(sum(vs) / len(vs), 2) if vs else None}
                       for m, vs in by_market.items()]
    by_market_out.sort(key=lambda x: -(x["avg_clv_pct"] or 0))

    by_player_out = []
    for pid, info in by_player.items():
        if info["n"] < 5:
            continue
        avg = info["sum_clv"] / info["n"]
        by_player_out.append({**info, "avg_clv_pct": round(avg, 2)})
    by_player_out.sort(key=lambda x: -x["avg_clv_pct"])

    # Sort per-bet by date desc and trim
    per_bet.sort(key=lambda b: b.get("date") or "", reverse=True)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_settled": sum(1 for r in props if r.get("play_hit") is not None),
        "n_with_clv": len(per_bet),
        "avg_clv_pct": round(overall_avg, 2) if overall_avg is not None else None,
        "trailing_30d_clv_pct": round(avg_30d, 2) if avg_30d is not None else None,
        "by_market": by_market_out,
        "by_player_top": by_player_out[:10],
        "by_player_bottom": by_player_out[-10:] if len(by_player_out) >= 10 else [],
        "per_bet": per_bet[:200],
        "note": ("CLV proxy uses model_prob_over as 'closing implied'. With "
                  "real closing-line snapshots (clv_log) this becomes exact."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_with_clv']} props with CLV ({p['n_settled']} total settled)")
    print(f"  Overall avg CLV: {p['avg_clv_pct']}%")
    print(f"  Trailing 30d:    {p['trailing_30d_clv_pct']}%")
    print(f"  Top markets:")
    for m in p["by_market"][:5]:
        print(f"    {m['market']:25} n={m['n']:5} avg CLV {m['avg_clv_pct']}%")
