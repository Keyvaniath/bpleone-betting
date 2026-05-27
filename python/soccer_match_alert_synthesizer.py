"""
EdgeStat -- Soccer match alert synthesizer.

Counterpart to mlb_offensive_explosion_alerts / nhl_skater_ceiling_stack
but for soccer matches. Aggregates multi-market OVER alignment per match:
  - TOTAL_GOALS_OVER (over 2.5)
  - BTTS_YES
  - CORNERS_OVER
  - SHOTS_OVER (total shots)
  - CARDS_OVER
  - FIRST_TEAM_SCORE_LIVE (high-pace first team to score)

MATCH_ELITE = 5+ aligned; STRONG = 3-4; LEAN = 2.

Output: data/soccer_match_alert_synthesizer.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_match_alert_synthesizer.json")


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


def _norm_match(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    total_goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))
    btts = _load(os.path.join(DATA_DIR, "soccer_btts_props.json"))
    corners = _load(os.path.join(DATA_DIR, "soccer_corners_props.json"))
    shots = _load(os.path.join(DATA_DIR, "soccer_total_shots_props.json"))
    cards = _load(os.path.join(DATA_DIR, "soccer_cards_props.json"))
    first_score = _load(os.path.join(DATA_DIR, "soccer_first_to_score_props.json"))

    matches: Dict[str, Dict[str, Any]] = {}

    def _entry(match_str: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm_match(match_str)
        if not key: return {}
        return matches.setdefault(key, {
            "match": match_str,
            "league": r.get("league"),
            "signals": {},
            "scores": {},
        })

    def _ingest_over(src: Dict[str, Any], signal_key: str,
                     match_field: str = "match") -> None:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            m = r.get(match_field) or r.get("matchup") or ""
            entry = _entry(m, r)
            if not entry: continue
            ec = (r.get("edge_class") or "").upper()
            entry["signals"][signal_key] = 1 if "OVER" in ec else 0

    def _ingest_threshold(src: Dict[str, Any], signal_key: str,
                          p_field: str, threshold: float) -> None:
        seen: set = set()
        for k in ("rows", "strong_edges"):
            for r in (src.get(k) or []):
                if not isinstance(r, dict): continue
                m = r.get("match") or r.get("matchup") or ""
                key = _norm_match(m)
                if key in seen: continue
                seen.add(key)
                entry = _entry(m, r)
                if not entry: continue
                p_val = _safe(r.get(p_field) or r.get("p"))
                entry["signals"][signal_key] = 1 if p_val >= threshold else 0
                entry["scores"][signal_key] = round(p_val, 3)

    _ingest_over(total_goals, "TOTAL_GOALS_OVER")
    _ingest_over(corners, "CORNERS_OVER")
    _ingest_over(shots, "SHOTS_OVER")
    _ingest_over(cards, "CARDS_OVER")
    _ingest_threshold(btts, "BTTS_YES", "p_btts_yes", 0.58)
    _ingest_threshold(first_score, "FIRST_SCORE_LIVE", "p_either", 0.62)

    alerts: List[Dict[str, Any]] = []
    for key, entry in matches.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 2: continue
        if n >= 5:
            tier = "MATCH_ELITE"
        elif n >= 3:
            tier = "MATCH_STRONG"
        else:
            tier = "MATCH_LEAN"
        alerts.append({
            "match": entry["match"],
            "league": entry["league"],
            "n_aligned_overs": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_aligned_overs"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "MATCH_ELITE"),
        "n_strong": sum(1 for a in alerts if a["tier"] == "MATCH_STRONG"),
        "method_note": "Soccer counterpart to NBA/NHL ceiling synthesizers. "
                       "Aggregates per-match OVERs across goals/BTTS/corners/"
                       "shots/cards/first_score. ELITE = 5+ aligned; STRONG = 3-4; "
                       "LEAN = 2.",
        "alerts": alerts,
        "elite_matches": [a for a in alerts if a["tier"] == "MATCH_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-match] {o['n_alerts']} alerts "
          f"({o['n_elite']} ELITE, {o['n_strong']} STRONG) -> {OUT}")
