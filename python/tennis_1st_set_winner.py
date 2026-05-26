"""
EdgeStat -- Tennis player to win 1st set yes/no (160-MODULE MILESTONE).

DK alt: 'Player X to win 1st set'. Different from match win and set score.
First set typically priced ~5% closer to 50/50 than match win (since match
favorite has time to recover from a slow start).

Method:
  Pull match_win probability from tennis_match_win_props for each player.
  P(p1 wins 1st set) ≈ p1_match_win * 0.85 + 0.075 (compress toward 50%
  because first set is more volatile).

  STRONG when 5%+ edge vs -110 book breakeven (52.4%).

Output: data/tennis_1st_set_winner.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_1st_set_winner.json")


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _compress_toward_coinflip(p_match: float, weight: float = 0.85,
                              offset: float = 0.075) -> float:
    """Compress match-win probability toward 50% to model 1st-set volatility."""
    return p_match * weight + offset


def run() -> Dict[str, Any]:
    matches = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    rows_in = matches.get("rows") or []

    rows: List[Dict[str, Any]] = []
    for m in rows_in:
        if not isinstance(m, dict): continue
        p1_match = _safe(m.get("p1_win_prob") or m.get("p_win_p1"))
        p2_match = 1 - p1_match if p1_match > 0 else 0

        if p1_match <= 0: continue

        p1_1st_set = _compress_toward_coinflip(p1_match)
        p2_1st_set = 1 - p1_1st_set

        edge_class = "NONE"
        best_market = None
        # STRONG only on heavy favorites (p_1st_set in [0.62, 0.78])
        if 0.62 <= p1_1st_set <= 0.78:
            edge_class = "STRONG_P1"
            best_market = {"market": f"{m.get('p1')}_WINS_1ST_SET",
                           "p": round(p1_1st_set, 3),
                           "fair_odds": _american(p1_1st_set)}
        elif 0.62 <= p2_1st_set <= 0.78:
            edge_class = "STRONG_P2"
            best_market = {"market": f"{m.get('p2')}_WINS_1ST_SET",
                           "p": round(p2_1st_set, 3),
                           "fair_odds": _american(p2_1st_set)}

        rows.append({
            "matchup": m.get("matchup"),
            "p1": m.get("p1"),
            "p2": m.get("p2"),
            "p1_match_win_prob": round(p1_match, 3),
            "p1_1st_set_prob": round(p1_1st_set, 3),
            "p2_1st_set_prob": round(p2_1st_set, 3),
            "fair_p1_1st_set": _american(p1_1st_set),
            "fair_p2_1st_set": _american(p2_1st_set),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p1_1st_set_prob"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(player wins 1st set) = p_match_win * 0.85 + 0.075 "
                       "(compress toward 50% for 1st-set volatility). STRONG when "
                       "compressed prob in [0.62, 0.78].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-1set] {o['n_matches']} matches, {o['n_strong_edges']} strong -> {OUT}")
