"""
EdgeStat -- Golf player dominance alerts.

Surfaces golfers projecting for elite tournament performance:
  - TOP5_LIVE (top 5 probability >= 12%)
  - TOP10_LIVE (top 10 probability >= 20%)
  - MAKE_CUT_HIGH (make cut probability >= 80%)
  - LEADER_LIVE (leader at round end probability >= 8%)
  - ROUND_OVER (favorable round score lean)
  - HOT_FORM (player heat HOT tier)

DOMINANCE_ELITE = 5+ signals; STRONG = 3-4.

Output: data/golf_player_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_player_dominance.json")


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


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    top_finish = _load(os.path.join(DATA_DIR, "golf_top_finish_props.json"))
    leaderboard = _load(os.path.join(DATA_DIR, "golf_leaderboard_probability.json"))
    rounds = _load(os.path.join(DATA_DIR, "golf_round_score_props.json"))
    player_heat = _load(os.path.join(DATA_DIR, "golf_player_heat.json"))
    make_cut = _load(os.path.join(DATA_DIR, "golf_makecut.json"))

    players: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return players.setdefault(key, {
            "player": name,
            "tournament": r.get("tournament"),
            "signals": {},
            "scores": {},
        })

    # Top finish (top 5 / top 10)
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (top_finish.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_5 = _safe(r.get("p_top5"))
            p_10 = _safe(r.get("p_top10"))
            entry["signals"]["TOP5_LIVE"] = 1 if p_5 >= 0.12 else 0
            entry["signals"]["TOP10_LIVE"] = 1 if p_10 >= 0.20 else 0
            entry["scores"]["p_top5"] = round(p_5, 3)
            entry["scores"]["p_top10"] = round(p_10, 3)

    # Leaderboard probability (leader / top 3)
    for k in ("rows", "strong_edges"):
        for r in (leaderboard.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_lead = _safe(r.get("p_leader") or r.get("p_top1"))
            entry["signals"]["LEADER_LIVE"] = 1 if p_lead >= 0.08 else 0
            entry["scores"]["p_leader"] = round(p_lead, 3)

    # Round score (OVER = lower scores than line)
    for r in (rounds.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("player") or ""
        entry = _entry(name, r)
        if not entry: continue
        ec = (r.get("edge_class") or "").upper()
        # In golf, UNDER on round score is the positive signal (low score = good)
        entry["signals"]["ROUND_OVER"] = 1 if "UNDER" in ec else 0

    # Make cut
    for k in ("rows", "strong_edges"):
        for r in (make_cut.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_cut = _safe(r.get("p_make_cut") or r.get("p_cut"))
            entry["signals"]["MAKE_CUT_HIGH"] = 1 if p_cut >= 0.80 else 0
            entry["scores"]["p_make_cut"] = round(p_cut, 3)

    # Player heat (HOT)
    hot_players = set()
    for k in ("hot", "hot_players"):
        for r in (player_heat.get(k) or []):
            if isinstance(r, dict):
                hot_players.add(_norm(r.get("player") or ""))
            elif isinstance(r, str):
                hot_players.add(_norm(r))
    for key in hot_players:
        entry = players.get(key)
        if entry:
            entry["signals"]["HOT_FORM"] = 1

    alerts: List[Dict[str, Any]] = []
    for key, entry in players.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        tier = "DOMINANCE_ELITE" if n >= 5 else "DOMINANCE_STRONG"
        alerts.append({
            "player": entry["player"],
            "tournament": entry["tournament"],
            "n_signals": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "DOMINANCE_ELITE"),
        "method_note": "Golf player dominance synthesizer. 3+ aligned signals "
                       "across TOP5_LIVE (>=12%), TOP10_LIVE (>=20%), LEADER_LIVE "
                       "(>=8%), MAKE_CUT_HIGH (>=80%), ROUND_OVER (UNDER round "
                       "score), HOT_FORM. DOMINANCE_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_dominance": [a for a in alerts if a["tier"] == "DOMINANCE_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-dominance] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
