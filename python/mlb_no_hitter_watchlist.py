"""
EdgeStat -- MLB no-hitter / shutout watchlist.

Surfaces pitchers with EXTREME dominance signals where a no-hitter or
shutout is statistically more likely than usual:
  - Pitcher confluence_score >= 75 (top tier)
  - 6+ IP probability >= 70%
  - Opp lineup_score <= 35 (weak lineup)
  - 1st inning ER NO probability >= 75%
  - Quality start probability >= 70%

Statistical probability of no-hitter is ~0.6% in MLB historically.
Shutout is ~5%. We surface for monitoring + small-stake high-payout
bets.

Output: data/mlb_no_hitter_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_no_hitter_watchlist.json")


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
    six_plus = _load(os.path.join(DATA_DIR, "mlb_pitcher_6plus_IP_yn.json"))
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    first_er = _load(os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_er.json"))
    qs = _load(os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json"))

    six_plus_idx = {_norm(r.get("pitcher")): r
                    for r in (six_plus.get("rows") or []) if isinstance(r, dict)}

    # Opp lineup scores by (matchup, side)
    opp_lq: Dict[str, float] = {}
    for g in (lq.get("games") or []):
        m = g.get("matchup") or ""
        for s_key in ("home", "away"):
            sd = g.get(s_key) or {}
            opp_lq[f"{m}|{s_key.upper()}"] = _safe(sd.get("score"))

    first_er_idx = {_norm(r.get("pitcher")): r
                    for r in (first_er.get("rows") or []) if isinstance(r, dict)}

    qs_idx: Dict[str, float] = {}
    for k in ("rows", "top_25_by_p_qs", "strong_edges"):
        for r in (qs.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("pitcher") or "")
                if key and key not in qs_idx:
                    qs_idx[key] = _safe(r.get("p_qs") or r.get("p_quality_start"))

    watchlist: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 75: continue

        name = _norm(r.get("pitcher") or "")
        matchup = r.get("matchup") or ""
        team = (r.get("team") or "").upper()

        # Opp side
        opp_side = ""
        for s in ("HOME", "AWAY"):
            # Pitcher's side = same as their team's side
            lq_data = next((g.get(s.lower()) for g in (lq.get("games") or [])
                            if g.get("matchup") == matchup), {}) or {}
            if (lq_data.get("team") or "").upper() == team:
                opp_side = "AWAY" if s == "HOME" else "HOME"
                break

        opp_lq_score = opp_lq.get(f"{matchup}|{opp_side}", 50)
        if opp_lq_score > 35: continue  # opp too strong

        six_data = six_plus_idx.get(name, {})
        p_6plus = _safe(six_data.get("p_6plus_IP") or six_data.get("p"))
        if p_6plus < 0.70: continue

        first_data = first_er_idx.get(name, {})
        p_no_er = _safe(first_data.get("p_no_er"))
        if p_no_er < 0.75: continue

        p_qs = qs_idx.get(name, 0)
        if p_qs < 0.70: continue

        # Approximate no-hitter and shutout probabilities
        # very rough: no_hitter ~ 0.005 * (composite_score / 75)
        # shutout ~ 0.05 * (composite_score / 75) * (p_qs / 0.6)
        no_hit_p = min(0.005 * (score / 75.0) * (p_6plus / 0.7), 0.04)
        shutout_p = min(0.05 * (score / 75.0) * (p_qs / 0.6), 0.20)

        watchlist.append({
            "pitcher": r.get("pitcher"),
            "matchup": matchup,
            "team": team,
            "composite_score": round(score, 2),
            "p_6plus_IP": round(p_6plus, 3),
            "p_no_er_1st": round(p_no_er, 3),
            "p_qs": round(p_qs, 3),
            "opp_lineup_score": opp_lq_score,
            "est_p_no_hitter": round(no_hit_p, 4),
            "est_p_shutout": round(shutout_p, 4),
            "advisory": "Extreme dominance spot. Small-stake high-payout bets: "
                        "no-hitter YES (~150-1 to 500-1 typical), pitcher "
                        "shutout YES (~15-1 to 25-1), opp 0 runs.",
            "recommended_markets": [
                "No-hitter YES (small stake)",
                "Pitcher shutout YES",
                "Opp 0 runs YES (long shot)",
                "Pitcher complete game YES",
            ],
        })

    watchlist.sort(key=lambda w: -w["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "No-hitter / shutout watchlist. Strict criteria: "
                       "confluence_score >= 75 + p_6plus_IP >= 70% + opp "
                       "lineup_score <= 35 + p_no_er_1st >= 75% + p_qs >= 70%. "
                       "Estimates no-hitter and shutout probabilities from "
                       "composite signals.",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-no-hitter] {o['n_watchlist']} on watchlist -> {OUT}")
