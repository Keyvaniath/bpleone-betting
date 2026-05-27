"""
EdgeStat -- Tonight's top 5 curated plays.

Single highly-curated board of the top 5 plays of the night. Combines:
  - cross_sport_top_picks (top 30 by final_score)
  - tonight_lock_of_night
  - mlb_confluence_triple (TRIPLE_LOCK if present)
  - mlb_game_preview GAME_LOCKs

Curation rules:
  1. TRIPLE_LOCK MLB confluences = automatic top spot
  2. Cross-sport diversification: prefer max 2 picks per sport
  3. Mix entity types (player + team + game)
  4. Push fade picks to a separate "tonight's fades" section

Output: data/tonight_top_5_curated.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_top_5_curated.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _sport_from_source(source: str) -> str:
    src = source.split("_")[0]
    return src


def run() -> Dict[str, Any]:
    cross_top = _load(os.path.join(DATA_DIR, "cross_sport_top_picks.json"))
    triple = _load(os.path.join(DATA_DIR, "mlb_confluence_triple.json"))
    mlb_game = _load(os.path.join(DATA_DIR, "mlb_game_preview.json"))
    nba_game = _load(os.path.join(DATA_DIR, "nba_game_preview.json"))
    nhl_game = _load(os.path.join(DATA_DIR, "nhl_game_preview.json"))
    fade_board = _load(os.path.join(DATA_DIR, "daily_fade_board.json"))

    candidates: List[Dict[str, Any]] = []

    # TRIPLE_LOCK from MLB triple confluence
    for t in (triple.get("triple_locks") or []):
        candidates.append({
            "source": "TRIPLE_LOCK",
            "sport": "MLB",
            "subject": t.get("matchup"),
            "score": 100,  # automatic top
            "play": (f"FADE {t.get('fade_pitcher')} K UNDER + "
                     f"{','.join(t.get('explosion_teams') or [])} TT OVER"),
            "tier": t.get("tier"),
            "rationale": "3-source MLB confluence (matchup_conf + stack + explosion)",
        })

    # GAME_LOCK previews
    for game_src, sport in [(mlb_game, "MLB"), (nba_game, "NBA"), (nhl_game, "NHL")]:
        for g in (game_src.get("previews") or []):
            if g.get("tier") != "GAME_LOCK": continue
            angles = g.get("recommended_angles") or []
            candidates.append({
                "source": f"{sport}_GAME_LOCK",
                "sport": sport,
                "subject": g.get("matchup"),
                "score": 80,
                "play": angles[0] if angles else f"{g.get('matchup')} game lock",
                "tier": g.get("tier"),
                "rationale": "Per-game preview tier LOCK",
            })

    # Cross-sport top picks (already ranked)
    for p in (cross_top.get("top_30") or [])[:20]:
        candidates.append({
            "source": p.get("source"),
            "sport": _sport_from_source(p.get("source", "")),
            "subject": p.get("subject"),
            "team": p.get("team"),
            "matchup": p.get("matchup"),
            "score": p.get("final_score") or 0,
            "play": f"{p.get('subject')} ({p.get('tier')})",
            "tier": p.get("tier"),
            "rationale": f"Cross-sport top pick ({p.get('source')})",
        })

    # Apply diversification: max 2 per sport in the top 5
    seen_sports: Dict[str, int] = {}
    final_picks: List[Dict[str, Any]] = []
    candidates.sort(key=lambda c: -c["score"])
    for c in candidates:
        sport = c.get("sport", "?")
        if seen_sports.get(sport, 0) >= 2: continue
        if any(fp.get("subject") == c.get("subject") and fp.get("source") == c.get("source")
               for fp in final_picks): continue
        final_picks.append(c)
        seen_sports[sport] = seen_sports.get(sport, 0) + 1
        if len(final_picks) >= 5: break

    # Top 3 fades
    top_fades = (fade_board.get("top_15") or [])[:3]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_top_picks": len(final_picks),
        "top_5_picks": final_picks,
        "top_3_fades": top_fades,
        "method_note": "Curated top-5 with max 2 per sport diversification. "
                       "TRIPLE_LOCK MLB confluences automatic top. Then "
                       "GAME_LOCK previews. Then cross-sport top picks by "
                       "final_score. Plus top 3 fades from daily_fade_board.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[top-5] {o['n_top_picks']} curated picks + {len(o.get('top_3_fades',[]))} fades -> {OUT}")
