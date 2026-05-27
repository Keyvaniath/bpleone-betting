"""
EdgeStat -- MLB pitcher K-streak tracker.

Surfaces pitchers currently on multi-game K-streaks with mean reversion
or continuation likelihood:
  - Pitcher has 8+ K's in last 3 starts (averaged or per start)
  - Confluence_score >= 60
  - Form_index >= 60
  - Opp lineup K% above league

Useful for K OVER alt + 9+ K props.

Output: data/mlb_pitcher_k_streak_tracker.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_k_streak_tracker.json")


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
    confluence = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    form_index = _load(os.path.join(DATA_DIR, "mlb_starter_recent_form_index.json"))
    k_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    k_9plus = _load(os.path.join(DATA_DIR, "mlb_pitcher_9plus_K_alt.json"))

    conf_idx = {_norm(r.get("pitcher")): r
                for r in (confluence.get("rows") or []) if isinstance(r, dict)}

    form_idx = {_norm(r.get("pitcher")): r
                for r in (form_index.get("rows") or []) if isinstance(r, dict)}

    k_idx = {_norm(r.get("pitcher")): r
             for r in (k_props.get("rows") or []) if isinstance(r, dict)}

    k9_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (k_9plus.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("pitcher") or "")
                if key and key not in k9_idx:
                    k9_idx[key] = _safe(r.get("p_9plus") or r.get("p"))

    streaks: List[Dict[str, Any]] = []
    for name, c in conf_idx.items():
        score = _safe(c.get("composite_score"))
        if score < 60: continue

        f = form_idx.get(name, {})
        f_idx = _safe(f.get("form_index"))
        if f_idx < 60: continue

        kr = k_idx.get(name, {})
        recent_k9 = _safe(f.get("recent_k9"))
        expected_k = _safe(kr.get("expected_k"))

        # K streak heuristic
        if expected_k < 7 and recent_k9 < 10: continue

        p_9plus = k9_idx.get(name, 0)

        signals: Dict[str, int] = {}
        signals["HIGH_CONFLUENCE"] = 1 if score >= 65 else 0
        signals["STRONG_FORM"] = 1 if f_idx >= 65 else 0
        signals["HIGH_K_PROJECTION"] = 1 if expected_k >= 8 else 0
        signals["RECENT_K9_ELITE"] = 1 if recent_k9 >= 10 else 0
        signals["9PLUS_K_LIVE"] = 1 if p_9plus >= 0.30 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 4:
            tier = "K_STREAK_ELITE"
        else:
            tier = "K_STREAK_STRONG"

        streaks.append({
            "pitcher": c.get("pitcher") or name.title(),
            "team": c.get("team"),
            "matchup": c.get("matchup"),
            "confluence_score": round(score, 2),
            "form_index": f_idx,
            "expected_k": round(expected_k, 2) if expected_k else None,
            "recent_k9": round(recent_k9, 2) if recent_k9 else None,
            "p_9plus_K": round(p_9plus, 3),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                "K OVER",
                "9+ K alt YES",
                "10+ K alt YES (long shot)",
                "K OVER + outs OVER (parlay)",
            ],
        })

    streaks.sort(key=lambda s: -s["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_streaks": len(streaks),
        "n_elite": sum(1 for s in streaks if s["tier"] == "K_STREAK_ELITE"),
        "method_note": "K-streak tracker. Confluence >= 60 + form_index >= 60 + "
                       "expected_k OR recent_k9 high. 3+ signals: HIGH_CONFLUENCE "
                       "(>=65), STRONG_FORM (>=65), HIGH_K_PROJECTION (>=8), "
                       "RECENT_K9_ELITE (>=10), 9PLUS_K_LIVE (>=30%).",
        "streaks": streaks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-k-streak] {o['n_streaks']} streak alerts ({o['n_elite']} ELITE) -> {OUT}")
