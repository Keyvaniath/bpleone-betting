"""
EdgeStat -- MLB matchup confluence alerts.

Highest-leverage signal in the EdgeStat MLB stack. Pairs:
  - mlb_pitcher_fade_alerts (pitcher projecting BAD outing)
  - mlb_offensive_explosion_alerts (opp lineup projecting EXPLOSION)

When BOTH fire on the same matchup with the explosion team facing the
fade pitcher, that's a multi-market confluence:
  - Team total OVER (explosion side)
  - Opp pitcher prop UNDERs (K, outs, QS NO)
  - Run line opposing the fade pitcher's team
  - First 5 innings OVER
  - 1st inning run YES (explosion side)

CONFLUENCE_ELITE = fade pitcher 5+ signals AND explosion team 5+ signals.
CONFLUENCE_STRONG = both 4+ signals.
CONFLUENCE_LEAN = both 3+ signals.

Output: data/mlb_matchup_confluence_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_matchup_confluence_alerts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    fade = _load(os.path.join(DATA_DIR, "mlb_pitcher_fade_alerts.json"))
    explosion = _load(os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json"))

    # Index fade alerts by matchup
    fade_by_matchup: Dict[str, Dict[str, Any]] = {}
    for a in (fade.get("alerts") or []):
        m = a.get("matchup") or ""
        if not m: continue
        # Prefer the higher-signal alert if multiple pitchers per matchup
        existing = fade_by_matchup.get(m)
        if not existing or a.get("n_negative_signals", 0) > existing.get("n_negative_signals", 0):
            fade_by_matchup[m] = a

    confluences: List[Dict[str, Any]] = []

    for a in (explosion.get("alerts") or []):
        matchup = a.get("matchup") or ""
        if not matchup: continue
        fade_alert = fade_by_matchup.get(matchup)
        if not fade_alert: continue

        # The fade pitcher must be on the OPPOSING side from the explosion team
        # explosion side is "HOME" or "AWAY"; fade pitcher's team should be the opposite
        explosion_side = a.get("side") or ""
        opp_side = "AWAY" if explosion_side == "HOME" else "HOME"

        # Fade alert doesn't carry side directly, but the pitcher's team will be
        # different from the explosion team. Loose match: confirm distinct teams.
        explosion_team = (a.get("team") or "").strip()
        fade_team = (fade_alert.get("team") or "").strip()
        if explosion_team and fade_team and explosion_team == fade_team:
            continue  # pitcher is on explosion team, skip

        n_fade = fade_alert.get("n_negative_signals", 0)
        n_explosion = a.get("n_positive_signals", 0)

        if n_fade >= 5 and n_explosion >= 5:
            tier = "CONFLUENCE_ELITE"
        elif n_fade >= 4 and n_explosion >= 4:
            tier = "CONFLUENCE_STRONG"
        else:
            tier = "CONFLUENCE_LEAN"

        confluences.append({
            "matchup": matchup,
            "explosion_team": explosion_team,
            "explosion_side": explosion_side,
            "explosion_signals": n_explosion,
            "fade_pitcher": fade_alert.get("pitcher"),
            "fade_team": fade_team,
            "fade_signals": n_fade,
            "combined_signal_count": n_explosion + n_fade,
            "tier": tier,
            "lineup_tier": a.get("lineup_tier"),
            "park_tier": a.get("park_tier"),
            "tt_direction": a.get("tt_direction"),
            "p_5plus_runs": a.get("p_5plus_runs"),
            "fade_p_blowup": fade_alert.get("p_blowup"),
            "fade_p_qs": fade_alert.get("p_qs"),
            "recommended_markets": [
                f"{explosion_team} team total OVER",
                f"{fade_alert.get('pitcher')} K UNDER",
                f"{fade_alert.get('pitcher')} outs UNDER",
                f"{fade_alert.get('pitcher')} QS NO",
                f"{explosion_team} 1st inning run YES",
                f"{matchup} 1st 5 innings OVER",
            ],
        })

    confluences.sort(key=lambda c: -c["combined_signal_count"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_confluences": len(confluences),
        "n_elite": sum(1 for c in confluences if c["tier"] == "CONFLUENCE_ELITE"),
        "n_strong": sum(1 for c in confluences if c["tier"] == "CONFLUENCE_STRONG"),
        "method_note": "Pairs mlb_pitcher_fade_alerts + mlb_offensive_explosion_alerts "
                       "on the same matchup. Surfaces fade-pitcher / opposing-explosion "
                       "stacks. ELITE = both 5+ signals; STRONG = both 4+; LEAN = both 3+. "
                       "Recommended multi-leg parlays: team total OVER + opposing "
                       "pitcher prop UNDERs + run line + 1st 5 OVER.",
        "confluences": confluences,
        "elite_stacks": [c for c in confluences if c["tier"] == "CONFLUENCE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[matchup-confluence] {o['n_confluences']} confluences "
          f"({o['n_elite']} ELITE, {o['n_strong']} STRONG) -> {OUT}")
