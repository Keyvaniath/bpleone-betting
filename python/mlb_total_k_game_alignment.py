"""
EdgeStat -- MLB total K's game alignment alerts.

Surfaces games where BOTH starting pitchers project K_OVER, producing
high-conviction game total K OVER alerts. Also identifies the inverse:
both pitchers project K_UNDER -> game K total UNDER.

Output: data/mlb_total_k_game_alignment.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_total_k_game_alignment.json")


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
    k_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    total_k = _load(os.path.join(DATA_DIR, "mlb_total_K_game.json"))

    # Group pitcher K projections by matchup
    k_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (k_props.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup", "")
        k_by_matchup.setdefault(m, []).append(r)

    # Total K game lean
    total_k_by_matchup: Dict[str, str] = {}
    for r in (total_k.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            total_k_by_matchup[r.get("matchup", "")] = "OVER"
        elif "UNDER" in ec:
            total_k_by_matchup[r.get("matchup", "")] = "UNDER"

    alignments: List[Dict[str, Any]] = []
    for matchup, pitchers in k_by_matchup.items():
        if not matchup or len(pitchers) < 2: continue

        over_count = sum(1 for p in pitchers
                         if "OVER" in (p.get("edge_class") or "").upper())
        under_count = sum(1 for p in pitchers
                          if "UNDER" in (p.get("edge_class") or "").upper())

        total_lean = total_k_by_matchup.get(matchup, "")

        if over_count >= 2 and (total_lean == "OVER" or total_lean == ""):
            tier = "BOTH_K_OVER_ALIGNMENT"
        elif under_count >= 2 and (total_lean == "UNDER" or total_lean == ""):
            tier = "BOTH_K_UNDER_ALIGNMENT"
        else:
            continue

        sum_expected_k = sum(_safe(p.get("expected_k")) for p in pitchers)

        alignments.append({
            "matchup": matchup,
            "tier": tier,
            "n_pitchers": len(pitchers),
            "n_over": over_count,
            "n_under": under_count,
            "sum_expected_k": round(sum_expected_k, 2),
            "game_total_k_lean": total_lean or None,
            "pitchers": [
                {"pitcher": p.get("pitcher"), "team": p.get("team"),
                 "expected_k": p.get("expected_k"),
                 "edge_class": p.get("edge_class")}
                for p in pitchers
            ],
            "recommended_markets": [
                ("Game Total K OVER" if "OVER" in tier else "Game Total K UNDER"),
                (f"{pitchers[0].get('pitcher')} K OVER + "
                 f"{pitchers[1].get('pitcher')} K OVER (parlay)"
                 if "OVER" in tier else
                 f"{pitchers[0].get('pitcher')} K UNDER + "
                 f"{pitchers[1].get('pitcher')} K UNDER (parlay)"),
            ],
        })

    alignments.sort(key=lambda a: -a["sum_expected_k"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alignments": len(alignments),
        "n_over_aligned": sum(1 for a in alignments
                              if a["tier"] == "BOTH_K_OVER_ALIGNMENT"),
        "n_under_aligned": sum(1 for a in alignments
                               if a["tier"] == "BOTH_K_UNDER_ALIGNMENT"),
        "method_note": "Total K game alignment. When both starters project "
                       "K_OVER (or both UNDER) + game total K props confirm, "
                       "surface as alignment. Recommends game total K OVER/UNDER "
                       "+ both-pitcher K parlay.",
        "alignments": alignments,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-total-k-align] {o['n_alignments']} alignments "
          f"({o['n_over_aligned']} OVER, {o['n_under_aligned']} UNDER) -> {OUT}")
