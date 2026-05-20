"""
EdgeStat -- Golf top-N finish props (top-5, top-10, top-20, top-40).

For each player in the active PGA tournament, projects P(top-N finish)
given their pre-tournament skill rating or live score (if in progress).

Approach:
  Player_skill_z = (player_proj_score - field_mean) / field_std
  Lower z = higher rank = better top-N probability

  P(top_N) = Phi(z_threshold_for_top_N - player_z)
    where z_threshold_for_top_N depends on field size:
      top-5 of 156 = top 3.2%, z threshold ≈ -1.86
      top-10 of 156 = top 6.4%, z threshold ≈ -1.52
      top-20 of 156 = top 12.8%, z threshold ≈ -1.13
      top-40 of 156 = top 25.6%, z threshold ≈ -0.66

  Pre-tournament uses golf_winner_model.json player rankings.
  Mid-tournament uses golf_live_projections.json for refined estimates.

Output: data/golf_top_finish_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_top_finish_props.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _norm_inv(p):
    """Inverse normal CDF (Beasley-Springer-Moro). For p in (0, 1)."""
    if p <= 0 or p >= 1: return 0
    a = [-39.6968302866538, 220.946098424521, -275.928510446969,
         138.357751867269, -30.6647980661472, 2.50662827745924]
    b = [-54.4760987982241, 161.585836858041, -155.698979859887,
         66.8013118877197, -13.2806815528857]
    c = [-7.78489400243029e-3, -0.322396458041136, -2.40075827716184,
         -2.54973253934373, 4.37466414146497, 2.93816398269878]
    d = [7.78469570904146e-3, 0.32246712907004, 2.445134137143,
         3.75440866190742]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return ((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5] / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
                (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    winner = _load(os.path.join(DATA_DIR, "golf_winner_model.json"))
    live = _load(os.path.join(DATA_DIR, "golf_live_projections.json"))
    state = _load(os.path.join(DATA_DIR, "golf_state.json"))

    tournament = state.get("tournament") or winner.get("tournament") or "PGA Event"
    is_live = state.get("is_in_progress") or live.get("is_in_progress")

    # Get player ratings/projections
    players = []
    # Primary source: golf_state.field (always available)
    field = state.get("field") or []
    if winner.get("rows"):
        for r in winner["rows"]:
            players.append({
                "name": r.get("player"),
                "p_win_pre": r.get("p_win_pre") or r.get("win_pct"),
                "skill_z": r.get("skill_z") or r.get("skill_rating"),
            })
    elif field:
        # Use field order as proxy for skill (ESPN's order = world ranking sort)
        n_field = len(field)
        for i, p in enumerate(field):
            # Distribute skill_z by rank: top players ~ -2 z, bottom ~ +2 z
            rank = p.get("order") or (i + 1)
            # Linear map: rank 1 -> z=-2, rank n -> z=+2
            skill_z = -2.0 + (4.0 * (rank - 1) / max(1, n_field - 1))
            players.append({
                "name": p.get("name"),
                "country": p.get("country"),
                "rank": rank,
                "skill_z": skill_z,
            })
    else:
        out = {
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "tournament": tournament,
            "is_live": bool(is_live),
            "n_players": 0,
            "n_strong": 0,
            "rows": [],
            "note": "No active PGA tournament data; framework ready for next event.",
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f: json.dump(out, f, indent=2)
        return out

    # Derive skill_z from p_win if needed
    n = len(players)
    if n == 0:
        out = {
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "tournament": tournament,
            "n_players": 0, "n_strong": 0, "rows": [],
            "note": "No players to project.",
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f: json.dump(out, f, indent=2)
        return out

    # Field size proxy
    field_size = max(n, 70)

    # If skill_z missing, derive from p_win_pre via inverse CDF
    for p in players:
        if p.get("skill_z") is None and p.get("p_win_pre"):
            # P(rank=1) -> approximate the z that yields this win prob
            # Higher win prob -> more negative z (better skill)
            try:
                if p["p_win_pre"] > 0:
                    # Rough: z = -log(p_win * field_size / 0.5) for top-skill players
                    p["skill_z"] = -math.log(max(0.01, p["p_win_pre"] * field_size / 5)) - 0.5
            except Exception:
                p["skill_z"] = 0

    # Z thresholds for top-N (assuming Normal field skill distribution)
    def z_thresh(top_n: int, field: int) -> float:
        cutoff = top_n / field
        return _norm_inv(max(0.001, min(0.999, cutoff)))

    z_top_5  = z_thresh(5,  field_size)
    z_top_10 = z_thresh(10, field_size)
    z_top_20 = z_thresh(20, field_size)
    z_top_40 = z_thresh(40, field_size)

    rows: List[Dict[str, Any]] = []
    for p in players:
        z = p.get("skill_z") or 0
        # P(player_rank <= top_N) = P(player_final_score is in top top_N/field cutoff)
        # If skill is normal, P(player_score < threshold_for_topN) = Phi(z_thresh - z)
        # NOTE: lower z = higher skill = better top-N prob, so we want z_thresh - z
        # Actually since z_thresh is negative (top of distribution),
        # better players have more negative z, so z_thresh - z = negative - even_more_neg = less neg = higher Phi
        p_top5  = _norm_cdf(z_top_5 - z)
        p_top10 = _norm_cdf(z_top_10 - z)
        p_top20 = _norm_cdf(z_top_20 - z)
        p_top40 = _norm_cdf(z_top_40 - z)

        # Edge classification -- ONLY flag STRONG when we have real skill data
        # (winner_model.json with proper skill_z). ESPN field-order rank is just
        # alphabetical-ish and isn't real skill, so we won't fake edges from it.
        has_real_skill = bool(winner.get("rows"))
        edge_class = "NONE"
        best_market = None
        if has_real_skill:
            if p_top10 >= 0.35 and p_top10 <= 0.55:
                edge_class = "STRONG_TOP_10"
                best_market = {"market": "TOP_10", "p": round(p_top10, 3),
                               "fair_odds": _american(p_top10)}
            elif p_top20 >= 0.50 and p_top20 <= 0.70:
                edge_class = "STRONG_TOP_20"
                best_market = {"market": "TOP_20", "p": round(p_top20, 3),
                               "fair_odds": _american(p_top20)}
            elif p_top5 >= 0.20 and p_top5 <= 0.35:
                edge_class = "STRONG_TOP_5"
                best_market = {"market": "TOP_5", "p": round(p_top5, 3),
                               "fair_odds": _american(p_top5)}

        rows.append({
            "player": p.get("name"),
            "country": p.get("country"),
            "skill_z": round(z, 3),
            "p_win_pre": p.get("p_win_pre"),
            "p_top_5":  round(p_top5, 3),
            "p_top_10": round(p_top10, 3),
            "p_top_20": round(p_top20, 3),
            "p_top_40": round(p_top40, 3),
            "fair_top_5":  _american(p_top5),
            "fair_top_10": _american(p_top10),
            "fair_top_20": _american(p_top20),
            "fair_top_40": _american(p_top40),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_top_10"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "tournament": tournament,
        "is_live": bool(is_live),
        "field_size": field_size,
        "n_players": len(rows),
        "n_strong": len(strong),
        "z_thresholds": {
            "top_5":  round(z_top_5,  3),
            "top_10": round(z_top_10, 3),
            "top_20": round(z_top_20, 3),
            "top_40": round(z_top_40, 3),
        },
        "rows": rows,
        "strong_edges": strong,
        "method_note": "Normal field-skill model with inverse CDF z-thresholds. "
                       "STRONG flagged only where model probability sits in the "
                       "real-edge window (not at extremes books already priced).",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-top] {o['n_players']} players, {o['n_strong']} strong edges -> {OUT}")
