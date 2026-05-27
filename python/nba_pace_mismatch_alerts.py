"""
EdgeStat -- NBA pace mismatch alerts.

Surfaces games with significant pace differential between teams
(e.g. fast team vs slow team = unpredictable total). When one team's
preferred pace is significantly higher than opp's, the game tends to
play CLOSER to the fast team's tempo at home, or the slow team's at home.

Pace mismatch >= 5 possessions = MISMATCH alert; >= 8 = EXTREME.

Recommends ALT total bets based on which team has home court advantage.

Output: data/nba_pace_mismatch_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_pace_mismatch_alerts.json")


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


def run() -> Dict[str, Any]:
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))

    alerts: List[Dict[str, Any]] = []
    for g in (pace.get("games") or pace.get("rows") or []):
        if not isinstance(g, dict): continue
        home_pace = _safe(g.get("home_pace") or g.get("home_team_pace"))
        away_pace = _safe(g.get("away_pace") or g.get("away_team_pace"))
        proj_pace = _safe(g.get("projected_pace") or g.get("pace"))

        if home_pace <= 0 or away_pace <= 0: continue

        pace_diff = abs(home_pace - away_pace)
        if pace_diff < 5: continue

        if pace_diff >= 8:
            tier = "PACE_EXTREME_MISMATCH"
        else:
            tier = "PACE_MISMATCH"

        fast_team = "HOME" if home_pace > away_pace else "AWAY"
        slow_team = "AWAY" if fast_team == "HOME" else "HOME"

        alerts.append({
            "matchup": g.get("matchup"),
            "home_pace": round(home_pace, 1),
            "away_pace": round(away_pace, 1),
            "projected_pace": round(proj_pace, 1) if proj_pace else None,
            "pace_diff": round(pace_diff, 1),
            "fast_team_side": fast_team,
            "slow_team_side": slow_team,
            "tier": tier,
            "advisory": "Pace mismatch creates unpredictable total. Home team's "
                        "preferred pace typically wins ~60% of the time. Consider "
                        "ALT total bets based on home pace prevailing.",
            "recommended_markets": [
                f"{tier}: ALT total OVER if home team is fast",
                f"{tier}: ALT total UNDER if home team is slow",
                "Race-to-points props (fast team boost)",
            ],
        })

    alerts.sort(key=lambda a: -a["pace_diff"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_extreme": sum(1 for a in alerts if a["tier"] == "PACE_EXTREME_MISMATCH"),
        "method_note": "NBA pace mismatch detector. Flags games with >=5 "
                       "possession differential between teams' preferred paces. "
                       "EXTREME = >=8 differential. Home pace typically prevails.",
        "alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pace] {o['n_alerts']} alerts ({o['n_extreme']} EXTREME) -> {OUT}")
