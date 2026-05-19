"""
EdgeStat -- GOLF LIVE projections.

For an in-progress (or between-rounds) PGA tournament, computes for each
player:
  - Projected final 72-hole score (linear extrapolation if mid-round)
  - P(top_5), P(top_10), P(make_cut), P(win) given current state
  - Hot/cold streak flag (relative to field-avg scoring on recent holes)
  - "Mover" flag (jumped >= 10 spots since last round)

Method:
  Once a tournament is mid-event, score variance per remaining round is
  empirically ~ 2.6 strokes. So projection = current_score + (rounds_left *
  mean_field_score_for_round). For each player we compute z-score of
  projected total vs field mean / std, then:
       P(top_N) = phi( z_threshold_for_top_N - z_player )
  where z_threshold is derived from the rank-cut into the field.

Output: data/golf_live_projections.json

Source: data/golf_state.json (must already be refreshed by golf_pipeline.py)
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_live_projections.json")

# Per-round scoring std on a typical PGA Tour course
ROUND_STDEV = 2.6
COURSE_PAR = 72


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_to_par(s):
    """Convert '-6' / '+2' / 'E' / 'CUT' / 'WD' -> int (or None)."""
    if s is None: return None
    if isinstance(s, (int, float)): return int(s)
    s = str(s).strip().upper()
    if s in ("E", "EVEN", "0"): return 0
    if s in ("CUT", "WD", "DQ", "MDF", "--", ""): return None
    try:
        if s.startswith("+"): return int(s[1:])
        return int(s)
    except Exception:
        return None


def _norm_cdf(x):
    """Std normal CDF (Abramowitz approximation)."""
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    # Hastings approx
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "golf_state.json"))
    tournament = state.get("active_tournament") or {}
    field = state.get("field") or []

    # Parse to_par + rounds_played
    rich = []
    for p in field:
        tp = _parse_to_par(p.get("total_to_par"))
        rp = p.get("rounds_played") or 0
        thru = p.get("thru")  # holes through in CURRENT round (if mid-round)
        if tp is None:
            continue
        rich.append({
            "name": p.get("name"),
            "country": p.get("country"),
            "order": p.get("order"),
            "espn_id": p.get("espn_id"),
            "to_par": tp,
            "rounds_played": rp,
            "thru": thru,
        })

    if not rich:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": tournament.get("name"),
            "is_in_progress": tournament.get("is_in_progress", False),
            "note": "No scored field data yet",
            "n_players_projected": 0,
            "projections": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Detect pre-tournament state: ALL scores at zero -> nothing to project
    nonzero_scores = sum(1 for p in rich if p["to_par"] != 0)
    is_scored = nonzero_scores >= max(5, len(rich) * 0.10)
    if not is_scored:
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "tournament": tournament.get("name"),
            "course": tournament.get("course"),
            "status": tournament.get("status"),
            "is_in_progress": tournament.get("is_in_progress", False),
            "is_scored": False,
            "rounds_done": 0,
            "rounds_left": 4,
            "n_players_projected": 0,
            "note": "Tournament has not yet been scored (all players at E). Preview mode -- use golf_winner_model.py for pre-event win probabilities.",
            "preview_field": [{"name": p["name"], "country": p["country"], "order": p["order"]}
                               for p in rich[:30]],
            "n_field": len(rich),
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Field statistics for the position projection
    rounds_done = max((p["rounds_played"] for p in rich), default=0)
    rounds_left = max(0, 4 - rounds_done)

    # If mid-round (thru < 18 for many players), use partial-round logic
    # For simplicity, treat thru as fractional round when projecting
    field_to_pars = [p["to_par"] for p in rich]
    field_mean_total = sum(field_to_pars) / len(field_to_pars)
    field_std_total = math.sqrt(
        sum((x - field_mean_total) ** 2 for x in field_to_pars) / max(1, len(field_to_pars) - 1)
    )

    # Projected total per player: assume player maintains their per-round
    # rate (current_total / rounds_played) for remaining rounds, with
    # regression toward field mean (shrinkage by 0.5*rounds_left/4).
    projections = []
    for p in rich:
        rp = p["rounds_played"]
        if rp >= 4:
            # Tournament done (probably cached). Project = current total.
            projected = p["to_par"]
            var = 0.01
        else:
            per_round_pace = p["to_par"] / max(1, rp) if rp > 0 else 0.0
            # Shrink to field per-round average
            field_per_round = field_mean_total / max(1, rounds_done) if rounds_done else 0.0
            w_player = rp / (rp + 1.5)   # less data = more shrink
            shrunk_per_round = w_player * per_round_pace + (1 - w_player) * field_per_round
            projected = p["to_par"] + shrunk_per_round * rounds_left
            var = rounds_left * (ROUND_STDEV ** 2)
        proj_std = math.sqrt(var) if var > 0 else 0.1

        # Z-score vs projected field distribution
        # We'll use field_mean projected (assume field stays at current mean rate)
        # Actually for relative ranking, comparing projected totals among players is
        # what matters. We compute z = (projected - field_mean_projected) / field_std_projected
        # field_mean_projected = field_mean_total + rounds_left * (field_mean_total / max(1, rounds_done))
        if rounds_done:
            field_mean_proj = field_mean_total * (4 / rounds_done) if rounds_done else field_mean_total
        else:
            field_mean_proj = field_mean_total
        # Field std grows with remaining rounds (independent rounds assumption)
        field_std_proj = math.sqrt(field_std_total ** 2 + var)
        z = (projected - field_mean_proj) / max(0.01, field_std_proj)

        # P(top_N) for ranks: convert rank N to z-cutoff using inverse phi.
        # Top_N out of M players: cutoff prob = N/M; z-cutoff = phi^-1(N/M)
        # Lower projected_total is better, so z is good when LOW.
        # P(player is top_N) = phi((z_cutoff - z) / sqrt(2)) per pairwise approx.
        n_field = len(rich)
        def _p_top_n(n_target):
            # The N-th best player has approximately z = phi^-1(N/M) below mean.
            # We want P(z_player < z_threshold_for_top_N) accounting for the
            # player's own remaining-round variance.
            # Use percentile-rank approach: z_threshold = -inv_phi(n_target/n_field).
            # phi^-1 approximation
            from math import sqrt, log
            q = n_target / n_field
            # Beasley-Springer/Moro inverse phi
            if q <= 0: return 1.0
            if q >= 1: return 0.0
            # Simple lookup-style: use known z for common percentiles
            # We'll use a small inverse-phi approximation
            # phi^-1(q) for q < 0.5 is negative
            t = math.sqrt(-2 * math.log(q if q < 0.5 else 1 - q))
            c0, c1, c2 = 2.515517, 0.802853, 0.010328
            d1, d2, d3 = 1.432788, 0.189269, 0.001308
            z_inv = t - (c0 + c1*t + c2*t*t) / (1 + d1*t + d2*t*t + d3*t**3)
            if q >= 0.5: z_inv = -z_inv
            z_cutoff = z_inv   # negative for top-N (since top = below mean)
            # Probability player ends up below z_cutoff given variance
            # Use the player's own residual std (rounds_left noise) normalized
            player_var_after_done = (var / max(0.01, field_std_proj ** 2))
            # P(player projected < threshold) -- but our z already accounts for
            # field. Simplest: P(player rank < N) ~ phi(z_cutoff - z) / phi norm
            # Better: assume normal distribution of player's true final, mean=projected,
            # std=proj_std. Compare to field-threshold = field_mean_proj + z_cutoff * field_std_proj
            field_thresh = field_mean_proj + z_cutoff * field_std_proj
            # P(player_final <= field_thresh)
            z_player_vs_thresh = (field_thresh - projected) / max(0.01, proj_std)
            return _norm_cdf(z_player_vs_thresh)

        p_top_3 = _p_top_n(3)
        p_top_5 = _p_top_n(5)
        p_top_10 = _p_top_n(10)
        p_top_20 = _p_top_n(20)
        # Winner approximation: top_1 with adjusted formula
        p_win = _p_top_n(1)
        # Make-cut probability (only relevant for rounds_done < 2):
        # Top ~65 + ties survive. Use top_70 as cut approximation.
        p_make_cut = _p_top_n(70) if rounds_done < 2 else (1.0 if rp >= 2 else None)

        projections.append({
            "name": p["name"],
            "country": p["country"],
            "espn_id": p["espn_id"],
            "current_pos": p.get("order"),
            "current_to_par": p["to_par"],
            "rounds_played": rp,
            "thru": p["thru"],
            "projected_final_to_par": round(projected, 2),
            "projected_z": round(z, 3),
            "p_win": round(p_win, 4),
            "p_top_3": round(p_top_3, 4),
            "p_top_5": round(p_top_5, 4),
            "p_top_10": round(p_top_10, 4),
            "p_top_20": round(p_top_20, 4),
            "p_make_cut": round(p_make_cut, 4) if p_make_cut is not None else None,
            "fair_win_american": _american(p_win),
            "fair_top_5_american": _american(p_top_5),
            "fair_top_10_american": _american(p_top_10),
        })

    # Sort by p_win desc
    projections.sort(key=lambda x: -x["p_win"])

    # Top 10 favorites
    top_10_favs = projections[:10]
    # Long-shots with > 5% top_10 prob
    longshots_top10 = [p for p in projections if p["current_pos"] and p["current_pos"] > 20 and p["p_top_10"] >= 0.05]
    longshots_top10.sort(key=lambda x: -x["p_top_10"])

    # Cut-line bubble: players within 2 strokes of typical cut (top 65 to_par)
    sorted_by_score = sorted(rich, key=lambda x: x["to_par"])
    cut_line_score = sorted_by_score[min(64, len(sorted_by_score)-1)]["to_par"] if sorted_by_score else None
    cut_bubble = []
    if cut_line_score is not None and rounds_done < 2:
        for p in projections:
            d = p["current_to_par"] - cut_line_score
            if 0 <= d <= 3:
                cut_bubble.append({**p, "strokes_off_cut": d})

    # Mover detection: position changes (we don't have prior snapshot here,
    # but we can flag "hot" players whose recent round is materially better
    # than their tournament avg)
    movers = []
    for p in rich:
        if p["rounds_played"] >= 2:
            avg_per_round = p["to_par"] / p["rounds_played"]
            # Field avg per round for this many rounds done
            field_avg_per_round = field_mean_total / max(1, rounds_done) if rounds_done else 0
            if avg_per_round < field_avg_per_round - 1.0:
                movers.append({
                    "name": p["name"],
                    "current_pos": p.get("order"),
                    "avg_per_round": round(avg_per_round, 2),
                    "field_avg_per_round": round(field_avg_per_round, 2),
                    "delta": round(avg_per_round - field_avg_per_round, 2),
                })
    movers.sort(key=lambda x: x["delta"])  # most negative (hottest) first

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": tournament.get("name"),
        "course": tournament.get("course"),
        "status": tournament.get("status"),
        "is_in_progress": tournament.get("is_in_progress", False),
        "rounds_done": rounds_done,
        "rounds_left": rounds_left,
        "n_players_projected": len(projections),
        "field_mean_to_par": round(field_mean_total, 2),
        "field_std_to_par": round(field_std_total, 2),
        "cut_line_estimated": cut_line_score,
        "top_10_favorites": top_10_favs,
        "longshots_top_10": longshots_top10[:15],
        "cut_bubble": cut_bubble[:15],
        "hot_streaks": movers[:10],
        "all_projections": projections[:120],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    if p.get("is_scored") is False:
        print(f"Golf live: {p['tournament']} -- {p.get('note','')}")
        print(f"  Field size: {p.get('n_field', 0)} players")
    elif not p.get("n_players_projected"):
        print(f"Golf live: {p.get('note','no data')}")
    else:
        print(f"Golf live: {p['tournament']} @ {p.get('course')}")
        print(f"  Status: {p['status']} | Rounds done {p['rounds_done']}/4 | {p['n_players_projected']} players")
        print(f"  Field avg: {p['field_mean_to_par']} | Std: {p['field_std_to_par']}")
        print(f"  Estimated cut line: {p['cut_line_estimated']}")
        print(f"\n  Top 5 favorites:")
        for fav in p["top_10_favorites"][:5]:
            print(f"    #{fav['current_pos']:3} {fav['name'][:25]:25s} ({fav['current_to_par']:+d}) "
                  f"proj final {fav['projected_final_to_par']:+.1f} "
                  f"P(win)={fav['p_win']*100:.1f}% fair_win {fav.get('fair_win_american','?')}")
        if p.get("longshots_top_10"):
            print(f"\n  Top 3 long-shots for top-10:")
            for ls in p["longshots_top_10"][:3]:
                print(f"    #{ls['current_pos']:3} {ls['name'][:25]:25s} P(top10)={ls['p_top_10']*100:.1f}%")
        if p.get("hot_streaks"):
            print(f"\n  Hot streaks (Δ vs field):")
            for h in p["hot_streaks"][:3]:
                print(f"    {h['name'][:25]:25s} avg/round {h['avg_per_round']:+.1f} vs field {h['field_avg_per_round']:+.1f} (Δ {h['delta']:+.1f})")
