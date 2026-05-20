"""
EdgeStat -- MLB catcher framing K-add for pitcher prop adjustments.

Catcher pitch-framing skill steals roughly 0.6 - 1.0 K per start for elite
framers and costs the same for poor framers. This module overlays a per-game
framing adjustment on top of the pitcher K projection so the K-prop market
edge accounts for who's behind the plate.

Source data (FanGraphs/Statcast frame runs above average -- baked in as
constants here; refresh periodically from public CSV).

Output: data/mlb_catcher_framing.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_catcher_framing.json")

# 2025 season framing runs above avg (per 100 called pitches). Top 10 / bottom 10.
# Updated periodically -- compatible with most "starting catcher" lookups.
# Format: lower-case name -> { framing_rpcp, k_per_start_add, tier }
FRAMING_RUNS = {
    # Elite framers (>+1.0 RPCP)
    "patrick bailey":   {"rpcp": +1.5, "k_per_start": +1.1, "tier": "elite"},
    "yainer diaz":      {"rpcp": +1.4, "k_per_start": +1.0, "tier": "elite"},
    "austin wells":     {"rpcp": +1.3, "k_per_start": +0.9, "tier": "elite"},
    "francisco alvarez":{"rpcp": +1.2, "k_per_start": +0.9, "tier": "elite"},
    "cal raleigh":      {"rpcp": +1.1, "k_per_start": +0.8, "tier": "elite"},
    # Above average
    "adley rutschman":  {"rpcp": +0.9, "k_per_start": +0.7, "tier": "above_avg"},
    "jonah heim":       {"rpcp": +0.8, "k_per_start": +0.6, "tier": "above_avg"},
    "j.t. realmuto":    {"rpcp": +0.6, "k_per_start": +0.4, "tier": "above_avg"},
    "yasmani grandal":  {"rpcp": +0.5, "k_per_start": +0.4, "tier": "above_avg"},
    "logan ohoppe":     {"rpcp": +0.5, "k_per_start": +0.4, "tier": "above_avg"},
    "shea langeliers":  {"rpcp": +0.4, "k_per_start": +0.3, "tier": "above_avg"},
    "tyler stephenson": {"rpcp": +0.3, "k_per_start": +0.2, "tier": "above_avg"},
    # League average (-0.2 to +0.2 RPCP) -- omitted, treat as 0
    # Below average
    "willson contreras":{"rpcp": -0.4, "k_per_start": -0.3, "tier": "below_avg"},
    "salvador perez":   {"rpcp": -0.5, "k_per_start": -0.4, "tier": "below_avg"},
    "william contreras":{"rpcp": -0.6, "k_per_start": -0.4, "tier": "below_avg"},
    "gabriel moreno":   {"rpcp": -0.7, "k_per_start": -0.5, "tier": "below_avg"},
    "elias diaz":       {"rpcp": -0.8, "k_per_start": -0.6, "tier": "below_avg"},
    # Poor framers (>-1.0 RPCP) cost pitchers a full K
    "martin maldonado": {"rpcp": -1.2, "k_per_start": -0.9, "tier": "poor"},
    "austin hedges":    {"rpcp": -1.4, "k_per_start": -1.0, "tier": "poor"},
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _lookup(name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not name: return None
    return FRAMING_RUNS.get(name.lower().strip())


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    games = matchups.get("games") or today.get("games") or []

    adjustments: List[Dict[str, Any]] = []
    for g in games:
        # matchups.json shape: lineups -> { home: [...], away: [...] }; pos field is "pos"
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""
        away_code, home_code = "", ""
        if "@" in matchup_str:
            try:
                away_code, home_code = [p.strip().upper() for p in matchup_str.split("@", 1)]
            except Exception:
                pass

        for side in ("home", "away"):
            lineup = lineups.get(side) or g.get(f"{side}_lineup") or []
            catcher = None
            for b in lineup:
                if isinstance(b, dict):
                    pos = (b.get("pos") or b.get("position") or "").upper()
                    if pos in ("C", "CATCHER") or b.get("position_code") in (2, "2"):
                        catcher = b
                        break
            if not catcher: continue
            c_name = catcher.get("name") or catcher.get("fullName")
            frame = _lookup(c_name)
            if not frame: continue

            # Catcher catches own team's starter; the starter throws to opposing batters
            own_pitcher_raw = g.get(f"{side}_pitcher")
            own_pitcher = own_pitcher_raw if isinstance(own_pitcher_raw, str) else (own_pitcher_raw or {}).get("name")
            team_code = home_code if side == "home" else away_code
            adjustments.append({
                "matchup": matchup_str or f"AWAY @ HOME",
                "team": team_code,
                "catcher": c_name,
                "framing_rpcp": frame["rpcp"],
                "tier": frame["tier"],
                "pitcher_caught": own_pitcher,
                "k_per_start_adj": frame["k_per_start"],
                "note": f"{frame['tier'].replace('_', ' ').title()} framer "
                        f"({'+' if frame['rpcp'] > 0 else ''}{frame['rpcp']:.1f} RPCP) "
                        f"-> {'+' if frame['k_per_start'] > 0 else ''}{frame['k_per_start']:.1f} K for {own_pitcher}",
            })

    # Sort by magnitude of adjustment
    adjustments.sort(key=lambda a: -abs(a.get("k_per_start_adj", 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_adjustments": len(adjustments),
        "n_framers_in_db": len(FRAMING_RUNS),
        "adjustments": adjustments,
        "top_5_positive": adjustments[:5] if adjustments else [],
        "top_5_negative": sorted(adjustments, key=lambda a: a.get("k_per_start_adj", 0))[:5],
        "note": "Catcher framing K-add overlay for pitcher props. Use to shade K-OVER edges.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[catcher-framing] {o['n_adjustments']} pitcher-catcher pairs flagged -> {OUT}")
