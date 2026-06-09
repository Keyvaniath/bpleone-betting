"""
EdgeStat -- MLB bullpen freshness tracker.

For each team tonight, classifies bullpen status:
   FRESH       <= 4 IP in last 2 days (full rest)
   NORMAL      4-8 IP last 2 days
   TIRED       8-12 IP last 2 days (multiple relievers unavailable)
   GASSED      >12 IP last 2 days (forced to use B-arm relievers)

When the opposing starter is projected EARLY_HOOK (from pitch-count
predictor) AND their bullpen is TIRED / GASSED, the opposing offense
should see late-inning runs. Compound OVER signal for team totals
+5/+6.

Output: data/mlb_bullpen_freshness.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_bullpen_freshness.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _classify(ip_2d):
    if ip_2d is None: return "UNKNOWN"
    if ip_2d <= 4: return "FRESH"
    if ip_2d <= 8: return "NORMAL"
    if ip_2d <= 12: return "TIRED"
    return "GASSED"


def _fatigue_index(ip_2d):
    """Continuous 0-1 fatigue from last-2-day relief IP, centered so NORMAL ~0.5
    (the same default the innings generators fall back to when a team is missing,
    so wiring this in only MOVES probabilities where a pen is genuinely fresh or
    gassed). 2 IP -> 0.0, 8 IP -> 0.5, 14+ IP -> 1.0; UNKNOWN -> 0.5."""
    try:
        ip = float(ip_2d)
    except (TypeError, ValueError):
        return 0.5
    return round(max(0.0, min(1.0, (ip - 2.0) / 12.0)), 3)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitch_count = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count.json"))

    # Index pitch count projections by pitcher name
    proj_by_pitcher = {}
    for p in (pitch_count.get("all_starters") or []):
        proj_by_pitcher[p["pitcher"]] = p

    results = []
    for g in (matchups.get("games") or []):
        mu = g.get("matchup")
        bullpens = g.get("bullpens") or {}
        home_bp = bullpens.get("home") or {}
        away_bp = bullpens.get("away") or {}

        home_starter = (g.get("home_pitcher") or {}).get("name")
        away_starter = (g.get("away_pitcher") or {}).get("name")
        home_proj = proj_by_pitcher.get(home_starter, {})
        away_proj = proj_by_pitcher.get(away_starter, {})

        # Identify compound signals
        compound_alerts = []
        # Home offense gets late-inning OVER if away starter is early hook + away bullpen is gassed
        if (away_proj.get("depth_tier") in ("EARLY_HOOK", "SHORT_LEASH") and
            _classify(away_bp.get("ip_2d")) in ("TIRED", "GASSED")):
            compound_alerts.append(f"AWAY starter projected short ({away_proj.get('projected_ip_today',0):.1f} IP) + AWAY bullpen {_classify(away_bp.get('ip_2d'))} -> HOME team total OVER late")
        if (home_proj.get("depth_tier") in ("EARLY_HOOK", "SHORT_LEASH") and
            _classify(home_bp.get("ip_2d")) in ("TIRED", "GASSED")):
            compound_alerts.append(f"HOME starter projected short ({home_proj.get('projected_ip_today',0):.1f} IP) + HOME bullpen {_classify(home_bp.get('ip_2d'))} -> AWAY team total OVER late")

        results.append({
            "matchup": mu,
            "home_bp_ip_2d": home_bp.get("ip_2d"),
            "home_bp_tier": _classify(home_bp.get("ip_2d")),
            "home_bp_gassed_flag": home_bp.get("gassed"),
            "away_bp_ip_2d": away_bp.get("ip_2d"),
            "away_bp_tier": _classify(away_bp.get("ip_2d")),
            "away_bp_gassed_flag": away_bp.get("gassed"),
            "home_starter_depth": home_proj.get("depth_tier"),
            "away_starter_depth": away_proj.get("depth_tier"),
            "compound_alerts": compound_alerts,
        })

    # Aggregates
    from collections import Counter
    home_tiers = Counter(r["home_bp_tier"] for r in results)
    away_tiers = Counter(r["away_bp_tier"] for r in results)

    all_alerts = []
    for r in results:
        for a in r["compound_alerts"]:
            all_alerts.append({"matchup": r["matchup"], "alert": a})

    # Per-TEAM fatigue index in the vocab the innings 4-6 / 7-9 totals generators
    # consume (`teams` + `fatigue_index`). Before this existed they found nothing
    # and silently defaulted every team to 0.5 -- a no-op adjustment. This is the
    # bridge that makes the bullpen-fatigue signal actually reach the model.
    teams = []
    for r in results:
        mu = r.get("matchup") or ""
        if "@" not in mu:
            continue
        away_ab, home_ab = [s.strip().upper() for s in mu.split("@", 1)]
        teams.append({"team": away_ab, "ip_2d": r["away_bp_ip_2d"],
                      "tier": r["away_bp_tier"], "fatigue_index": _fatigue_index(r["away_bp_ip_2d"])})
        teams.append({"team": home_ab, "ip_2d": r["home_bp_ip_2d"],
                      "tier": r["home_bp_tier"], "fatigue_index": _fatigue_index(r["home_bp_ip_2d"])})

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(results),
        "n_compound_alerts": len(all_alerts),
        "home_bullpen_tiers": dict(home_tiers),
        "away_bullpen_tiers": dict(away_tiers),
        "compound_alerts": all_alerts,
        "teams": teams,
        "games": results,
        "note": ("Compound bullpen alerts fire when an EARLY_HOOK starter "
                  "meets a TIRED/GASSED bullpen -- opposing offense gets late-"
                  "inning ABs against B-arm relievers. Team-total OVER signal."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB bullpen freshness: {p['n_games']} games")
    print(f"  Home BP tiers: {p['home_bullpen_tiers']}")
    print(f"  Away BP tiers: {p['away_bullpen_tiers']}")
    print(f"  Compound alerts: {p['n_compound_alerts']}")
    for a in p['compound_alerts'][:5]:
        print(f"    [{a['matchup']}] {a['alert']}")
