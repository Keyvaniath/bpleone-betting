"""
EdgeStat -- Slate quality index.

Measures the overall density and quality of tonight's slate by aggregating
LOCK + STRONG counts across all confluence-score modules. Tells you
whether tonight is a high-conviction night to load up or a "no-action"
night to stand down.

Calculations:
  total_locks = sum of LOCKs across all 14 confluence modules
  total_strong = sum of STRONGs
  total_fades = sum of FADEs
  slate_quality_score = total_locks * 10 + total_strong * 4 - total_fades * 1

Tiers:
  ELITE_NIGHT    = score >= 100 (multiple LOCKs across sports)
  STRONG_NIGHT   = score >= 50
  MODEST_NIGHT   = score >= 20
  NO_ACTION_NIGHT = score < 20 (stand down)

Output: data/slate_quality_index.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_quality_index.json")


CONFLUENCE_FILES = [
    ("MLB_PITCHER", "mlb_pitcher_confluence_score.json"),
    ("MLB_BATTER", "mlb_batter_confluence_score.json"),
    ("MLB_TEAM", "mlb_team_confluence_score.json"),
    ("NBA_PLAYER", "nba_player_confluence_score.json"),
    ("NBA_TEAM", "nba_team_confluence_score.json"),
    ("NHL_GOALIE", "nhl_goalie_confluence_score.json"),
    ("NHL_SKATER", "nhl_skater_confluence_score.json"),
    ("NHL_TEAM", "nhl_team_confluence_score.json"),
    ("WNBA_PLAYER", "wnba_player_confluence_score.json"),
    ("SOCCER_MATCH", "soccer_match_confluence_score.json"),
    ("TENNIS_PLAYER", "tennis_player_confluence_score.json"),
    ("UFC_FIGHTER", "ufc_fighter_confluence_score.json"),
    ("GOLF_PLAYER", "golf_player_confluence_score.json"),
    ("F1_DRIVER", "f1_driver_confluence_score.json"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    breakdown: Dict[str, Dict[str, int]] = {}
    total_locks = 0
    total_strong = 0
    total_fades = 0
    sports_with_locks: List[str] = []
    sports_with_strong: List[str] = []

    for source_id, fname in CONFLUENCE_FILES:
        data = _load(os.path.join(DATA_DIR, fname))
        n_lock = int(data.get("n_lock", 0) or 0)
        n_strong = int(data.get("n_strong", 0) or 0)
        n_fade = int(data.get("n_fade", 0) or 0)
        breakdown[source_id] = {
            "lock": n_lock,
            "strong": n_strong,
            "fade": n_fade,
        }
        total_locks += n_lock
        total_strong += n_strong
        total_fades += n_fade
        if n_lock > 0:
            sports_with_locks.append(source_id)
        if n_strong > 0:
            sports_with_strong.append(source_id)

    score = total_locks * 10 + total_strong * 4 - total_fades

    if score >= 100:
        tier = "ELITE_NIGHT"
    elif score >= 50:
        tier = "STRONG_NIGHT"
    elif score >= 20:
        tier = "MODEST_NIGHT"
    else:
        tier = "NO_ACTION_NIGHT"

    advisory = {
        "ELITE_NIGHT": "Multiple high-conviction LOCKs across sports. Load up "
                       "on tonight's top picks + parlay anchors.",
        "STRONG_NIGHT": "Solid slate. Pick top STRONG/LOCK picks; consider "
                        "Kelly 25-50% sizing.",
        "MODEST_NIGHT": "Light slate. Limit to 1-3 strongest plays; use 25% "
                        "Kelly or less.",
        "NO_ACTION_NIGHT": "STAND DOWN. Slate has no aligned conviction. "
                           "Skip betting tonight or watch only.",
    }[tier]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "slate_quality_score": score,
        "tier": tier,
        "advisory": advisory,
        "total_locks": total_locks,
        "total_strong": total_strong,
        "total_fades": total_fades,
        "n_sources_with_locks": len(sports_with_locks),
        "n_sources_with_strong": len(sports_with_strong),
        "sports_with_locks": sports_with_locks,
        "sports_with_strong": sports_with_strong,
        "breakdown_by_source": breakdown,
        "method_note": "slate_quality_score = total_locks*10 + total_strong*4 "
                       "- total_fades. ELITE >=100; STRONG >=50; MODEST >=20; "
                       "NO_ACTION <20.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[slate-quality] score={o['slate_quality_score']} tier={o['tier']} "
          f"(L={o['total_locks']} S={o['total_strong']} F={o['total_fades']}) "
          f"-> {OUT}")
