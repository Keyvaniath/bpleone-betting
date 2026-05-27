"""
EdgeStat -- Tennis per-match preview synthesizer.

For each tennis match, produces a unified preview combining:
  - Both players' confluence scores
  - Tennis dominance alerts
  - Total games + set score + aces signals

Each match gets a tier:
  MATCH_LOCK   = one player LOCK + opponent FADE
  MATCH_STRONG = one player LOCK or both STRONG-aligned
  MATCH_LEAN   = at least 1 STRONG signal
  MATCH_PASS   = no aligned signals

Output: data/tennis_match_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_match_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "tennis_player_confluence_score.json"))
    dom = _load(os.path.join(DATA_DIR, "tennis_dominance_alerts.json"))
    games = _load(os.path.join(DATA_DIR, "tennis_total_games_props.json"))
    aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))

    # Group players by match
    players_by_match: Dict[str, List[Dict[str, Any]]] = {}
    for r in (conf.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("match") or ""
        players_by_match.setdefault(m, []).append(r)

    dom_idx = {_norm(a.get("player")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}

    games_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (games.get("rows") or []) if isinstance(r, dict)}

    aces_by_match: Dict[str, List[str]] = {}
    for r in (aces.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            m = r.get("match") or r.get("matchup") or ""
            aces_by_match.setdefault(m, []).append(r.get("player", ""))

    previews: List[Dict[str, Any]] = []
    for match, players in players_by_match.items():
        if not match: continue

        locks = [p for p in players if "LOCK" in (p.get("tier") or "")]
        strong = [p for p in players if "STRONG" in (p.get("tier") or "")]
        fades = [p for p in players if "FADE" in (p.get("tier") or "")]

        # MATCH_LOCK = one LOCK + opponent FADE
        if locks and fades:
            tier = "MATCH_LOCK"
        elif locks:
            tier = "MATCH_STRONG"
        elif strong and (strong or fades):
            tier = "MATCH_LEAN"
        else:
            tier = "MATCH_PASS"

        games_ec = (games_idx.get(_norm(match), {}).get("edge_class") or "").upper()
        aces_overs = aces_by_match.get(match, [])

        angle: List[str] = []
        for p in locks:
            angle.append(f"{p.get('player')} match win + 1st set + straight sets")
        for f in fades:
            angle.append(f"FADE {f.get('player')} (underdog ML)")
        if "OVER" in games_ec:
            angle.append(f"{match} total games OVER")
        elif "UNDER" in games_ec:
            angle.append(f"{match} total games UNDER")
        for ace_player in aces_overs[:2]:
            angle.append(f"{ace_player} aces OVER")

        previews.append({
            "match": match,
            "tier": tier,
            "n_locks": len(locks),
            "n_strong": len(strong),
            "n_fades": len(fades),
            "player_summary": [
                {"player": p.get("player"), "tier": p.get("tier"),
                 "score": p.get("composite_score")}
                for p in players
            ],
            "total_games_edge": games_ec or None,
            "aces_overs": aces_overs,
            "recommended_angles": angle,
        })

    tier_order = {"MATCH_LOCK": 4, "MATCH_STRONG": 3, "MATCH_LEAN": 2, "MATCH_PASS": 1}
    previews.sort(key=lambda p: -tier_order.get(p["tier"], 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(previews),
        "n_locks": sum(1 for p in previews if p["tier"] == "MATCH_LOCK"),
        "n_strong": sum(1 for p in previews if p["tier"] == "MATCH_STRONG"),
        "n_lean": sum(1 for p in previews if p["tier"] == "MATCH_LEAN"),
        "method_note": "Per-match tennis preview. MATCH_LOCK = one player LOCK + "
                       "opponent FADE; STRONG = one LOCK; LEAN = STRONGs aligned.",
        "previews": previews,
        "locks_and_strong": [p for p in previews
                             if p["tier"] in ("MATCH_LOCK", "MATCH_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-preview] {o['n_matches']} matches "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN) -> {OUT}")
