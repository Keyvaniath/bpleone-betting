"""
EdgeStat -- MLB starter quality composite score.

Combines every pitcher-level signal we have into a single 0-100 score so
slate ranking is instant.

Inputs (all already computed):
  - ERA + K/9 (mlb_pitcher_logs.json)
  - Form delta (mlb_pitcher_form_regression.json)
  - Opposing lineup K-rate (mlb_lineup_strength.json)
  - TTO penalty + lineup mismatch (mlb_pitcher_deep_matchup.json)
  - Catcher framing add (mlb_catcher_framing.json)
  - Park run factor (today.json)

Output: data/mlb_starter_quality.json

Useful for:
  - Quick ranking: "who are tonight's 5 best starter matchups?"
  - F5 / K-prop pre-filter (top-15 starters are where the edge lives)
  - Whale confluence check (good starter + good catcher + bad opponent
    K-rate = strong K-OVER stack)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_starter_quality.json")


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


def _clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def _score_pitcher(era: float, k_per_9: float, form_delta: float,
                   opp_k_rate: float, park_factor: float,
                   catcher_k_add: float, tto_mult: float) -> Dict[str, Any]:
    """Produce a 0-100 composite. Each component is normalized into 0-100, then weighted."""
    # ERA component: 2.50 ERA = 95, 3.50 = 75, 4.50 = 50, 5.50 = 25, 6.50 = 5
    era_score = _clamp(100 - (era - 2.5) * 22.5)
    # K/9 component: 5.0 = 30, 8.0 = 60, 11.0 = 90
    k9_score = _clamp((k_per_9 - 5.0) * 10 + 30)
    # Form delta: -1.0 = 30, 0 = 55, +1.0 = 80
    form_score = _clamp(form_delta * 25 + 55)
    # Opp K-rate: 18% (low K opp) = 35, 22% = 55, 26% (high K opp) = 75
    opp_score = _clamp((opp_k_rate - 0.18) / 0.08 * 40 + 35)
    # Park: pitcher-friendly (0.90 RF) = 70, neutral (1.0) = 55, hitter (1.10) = 40
    park_score = _clamp((1.0 - park_factor) * 150 + 55)
    # Catcher framing: -1.0 K = 35, 0 = 55, +1.0 K = 75
    catcher_score = _clamp(catcher_k_add * 20 + 55)
    # TTO weighted (0.85 to 1.05 typical range): 0.85 = 35, 1.0 = 55, 1.05 = 65
    tto_score = _clamp((tto_mult - 0.85) / 0.20 * 30 + 35)

    # Weight: ERA + K/9 are the foundational signals
    weights = {
        "era": 0.25, "k_per_9": 0.20, "form": 0.15,
        "opp_k": 0.12, "park": 0.10, "catcher": 0.08, "tto": 0.10,
    }
    composite = (era_score * weights["era"] + k9_score * weights["k_per_9"] +
                 form_score * weights["form"] + opp_score * weights["opp_k"] +
                 park_score * weights["park"] + catcher_score * weights["catcher"] +
                 tto_score * weights["tto"])

    return {
        "composite_score": round(composite, 1),
        "components": {
            "era": round(era_score, 1),
            "k_per_9": round(k9_score, 1),
            "form": round(form_score, 1),
            "opp_k_rate": round(opp_score, 1),
            "park": round(park_score, 1),
            "catcher_framing": round(catcher_score, 1),
            "tto_weighted": round(tto_score, 1),
        },
        "inputs": {
            "era": era, "k_per_9": k_per_9, "form_delta": round(form_delta, 2),
            "opp_k_rate": round(opp_k_rate, 3), "park_factor": park_factor,
            "catcher_k_add": round(catcher_k_add, 2), "tto_mult": round(tto_mult, 3),
        },
        "tier": ("ELITE" if composite >= 70 else
                 "STRONG" if composite >= 60 else
                 "AVERAGE" if composite >= 50 else
                 "POOR"),
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_regression.json"))
    lineup_strength = _load(os.path.join(DATA_DIR, "mlb_lineup_strength.json"))
    deep_match = _load(os.path.join(DATA_DIR, "mlb_pitcher_deep_matchup.json"))
    catcher = _load(os.path.join(DATA_DIR, "mlb_catcher_framing.json"))

    # Index pitchers
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    # Form index
    form_by_name = {}
    for r in (form.get("rows") or form.get("pitchers") or []):
        nm = (r.get("name") or r.get("pitcher") or "").lower()
        if nm: form_by_name[nm] = _safe(r.get("delta") or r.get("z_score"), 0.0)
    # Opp lineup K-rate index (team -> rate)
    opp_k = {}
    for row in (lineup_strength.get("rows") or lineup_strength.get("teams") or []):
        t = (row.get("team") or row.get("code") or "").upper()
        kr = _safe(row.get("k_rate") or row.get("k_pct"), 0.224)
        if kr > 1: kr = kr / 100.0
        opp_k[t] = kr
    # TTO index from deep matchup
    tto_by_pitcher = {}
    for m in (deep_match.get("matchups") or []):
        for side in ("home_pitcher", "away_pitcher"):
            p = m.get(side, {}) or {}
            nm = (p.get("name") or "").lower()
            if nm: tto_by_pitcher[nm] = _safe(p.get("k_projection", {}).get("factors", {}).get("tto_weighted"), 1.0)
    # Catcher framing index (pitcher -> k_per_start_adj)
    catcher_by_pitcher = {}
    for adj in (catcher.get("adjustments") or []):
        nm = (adj.get("pitcher_caught") or "").lower()
        if nm: catcher_by_pitcher[nm] = _safe(adj.get("k_per_start_adj"), 0.0)

    parks = today.get("parks") or {}
    games = matchups.get("games") or today.get("games") or []
    rows = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        for side in ("home", "away"):
            opp_team = away if side == "home" else home
            p_raw = g.get(f"{side}_pitcher")
            name = p_raw if isinstance(p_raw, str) else (p_raw or {}).get("name")
            pitcher = p_by_name.get((name or "").lower())
            if not pitcher and isinstance(p_raw, dict): pitcher = p_raw
            if not pitcher: continue

            era = _safe(pitcher.get("era") or pitcher.get("season", {}).get("era"), 4.20)
            k9 = _safe(pitcher.get("k_per_9") or pitcher.get("season", {}).get("k_per_9"), 8.5)
            fd = form_by_name.get((name or "").lower(), 0.0)
            opk = opp_k.get(opp_team, 0.224)
            tto = tto_by_pitcher.get((name or "").lower(), 1.0)
            cat = catcher_by_pitcher.get((name or "").lower(), 0.0)

            score = _score_pitcher(era, k9, fd, opk, park_factor, cat, tto)
            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "opp_team": opp_team,
                **score,
            })

    rows.sort(key=lambda r: -r["composite_score"])
    elite = [r for r in rows if r["tier"] == "ELITE"]
    poor = [r for r in rows if r["tier"] == "POOR"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_elite": len(elite),
        "n_poor": len(poor),
        "weights": {"era": 0.25, "k_per_9": 0.20, "form": 0.15, "opp_k": 0.12,
                    "park": 0.10, "catcher": 0.08, "tto": 0.10},
        "starters_ranked": rows,
        "elite": elite,
        "poor_matchups": poor,
        "note": ("Composite 0-100 score per starter from ERA + K/9 + form + opp lineup + "
                 "park + catcher framing + TTO. ELITE>=70, STRONG>=60, AVG>=50."),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[starter-quality] {o['n_starters']} starters | {o['n_elite']} elite | "
          f"{o['n_poor']} poor -> {OUT}")
