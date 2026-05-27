"""
EdgeStat -- Soccer per-match preview synthesizer.

For each soccer match, produces a unified preview combining:
  - Match confluence score (from soccer_match_confluence_score)
  - Match alert (from soccer_match_alert_synthesizer)
  - Total goals + BTTS + corners + cards directional signals
  - Goalscorer / first-to-score angles

Each match gets a tier:
  MATCH_LOCK   = match_confluence LOCK
  MATCH_STRONG = match_confluence STRONG OR alert ELITE
  MATCH_LEAN   = alert STRONG or 3+ aligned secondary signals
  MATCH_PASS   = no aligned signals

Output: data/soccer_match_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_match_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "soccer_match_confluence_score.json"))
    alerts = _load(os.path.join(DATA_DIR, "soccer_match_alert_synthesizer.json"))
    goals = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))
    btts = _load(os.path.join(DATA_DIR, "soccer_btts_props.json"))
    corners = _load(os.path.join(DATA_DIR, "soccer_corners_props.json"))
    cards = _load(os.path.join(DATA_DIR, "soccer_cards_props.json"))
    goalscorer = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))

    conf_idx = {_norm(r.get("match")): r for r in (conf.get("rows") or []) if isinstance(r, dict)}
    alerts_idx = {_norm(a.get("match")): a for a in (alerts.get("alerts") or []) if isinstance(a, dict)}

    goals_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (goals.get("rows") or []) if isinstance(r, dict)}
    btts_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (btts.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("match") or r.get("matchup") or "")
                if key and key not in btts_idx:
                    btts_idx[key] = float(r.get("p_btts_yes") or r.get("p") or 0)

    corners_idx = {_norm(r.get("match") or r.get("matchup")): r
                   for r in (corners.get("rows") or []) if isinstance(r, dict)}
    cards_idx = {_norm(r.get("match") or r.get("matchup")): r
                 for r in (cards.get("rows") or []) if isinstance(r, dict)}

    # Top goalscorer pick per match
    top_scorers: Dict[str, str] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (goalscorer.get(k) or []):
            if not isinstance(r, dict): continue
            m = _norm(r.get("match") or r.get("matchup") or "")
            if m and m not in top_scorers and (r.get("p_score") or r.get("p")):
                top_scorers[m] = r.get("player") or ""

    all_matches = set(conf_idx) | set(alerts_idx) | set(goals_idx) | set(btts_idx)

    previews: List[Dict[str, Any]] = []
    for key in all_matches:
        c = conf_idx.get(key, {})
        a = alerts_idx.get(key, {})
        g = goals_idx.get(key, {})
        p_btts = btts_idx.get(key, 0)
        cr = corners_idx.get(key, {})
        cdr = cards_idx.get(key, {})
        scorer = top_scorers.get(key, "")

        conf_tier = c.get("tier") or ""
        alert_tier = a.get("tier") or ""

        goals_ec = (g.get("edge_class") or "").upper()
        corners_ec = (cr.get("edge_class") or "").upper()
        cards_ec = (cdr.get("edge_class") or "").upper()

        secondary_signals = sum([
            "OVER" in goals_ec,
            p_btts >= 0.58,
            "OVER" in corners_ec,
            "OVER" in cards_ec,
        ])

        if "LOCK" in conf_tier:
            tier = "MATCH_LOCK"
        elif "STRONG" in conf_tier or "ELITE" in alert_tier:
            tier = "MATCH_STRONG"
        elif "STRONG" in alert_tier or secondary_signals >= 3:
            tier = "MATCH_LEAN"
        else:
            tier = "MATCH_PASS"

        angle: List[str] = []
        if "OVER" in goals_ec:
            angle.append(f"{c.get('match') or key} total goals OVER")
        if p_btts >= 0.58:
            angle.append(f"{c.get('match') or key} BTTS YES")
        if "OVER" in corners_ec:
            angle.append(f"{c.get('match') or key} corners OVER")
        if "OVER" in cards_ec:
            angle.append(f"{c.get('match') or key} cards OVER")
        if scorer:
            angle.append(f"{scorer} anytime goal YES")

        previews.append({
            "match": c.get("match") or a.get("match") or g.get("match") or key,
            "league": c.get("league") or g.get("league"),
            "tier": tier,
            "confluence_tier": conf_tier or None,
            "alert_tier": alert_tier or None,
            "goals_edge": goals_ec or None,
            "p_btts_yes": round(p_btts, 3),
            "corners_edge": corners_ec or None,
            "cards_edge": cards_ec or None,
            "top_goalscorer": scorer or None,
            "secondary_signals": secondary_signals,
            "recommended_angles": angle,
        })

    tier_order = {"MATCH_LOCK": 4, "MATCH_STRONG": 3, "MATCH_LEAN": 2, "MATCH_PASS": 1}
    previews.sort(key=lambda p: (-tier_order.get(p["tier"], 0),
                                  -(p.get("secondary_signals") or 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(previews),
        "n_locks": sum(1 for p in previews if p["tier"] == "MATCH_LOCK"),
        "n_strong": sum(1 for p in previews if p["tier"] == "MATCH_STRONG"),
        "n_lean": sum(1 for p in previews if p["tier"] == "MATCH_LEAN"),
        "n_pass": sum(1 for p in previews if p["tier"] == "MATCH_PASS"),
        "method_note": "Per-match soccer preview. Combines confluence_score + "
                       "match_alert + goals/BTTS/corners/cards signals + top "
                       "goalscorer. MATCH_LOCK = confluence LOCK; STRONG = "
                       "confluence STRONG or alert ELITE; LEAN = alert STRONG "
                       "or 3+ secondary signals.",
        "previews": previews,
        "locks_and_strong": [p for p in previews
                             if p["tier"] in ("MATCH_LOCK", "MATCH_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-preview] {o['n_matches']} matches "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN, {o['n_pass']} PASS) -> {OUT}")
