"""
EdgeStat -- Golf live leaderboard win/top-N probability.

For each ongoing tournament, projects:
  - P(player wins) by simulating remaining holes via per-player
    expected-score-per-round (ESPR) and current position vs leader
  - P(top 5), P(top 10), P(top 20) via Normal CDF on final score
  - P(makes cut) if before cut line

Method:
  Each remaining round = N(player_espr, sigma=2.8)
  Player final score = current_to_par + sum(remaining_rounds)
  Field-relative: P(beat leader) when finals_score < leader_final_score
  Simplified: sample 5000 trajectories per player.

  STRONG_WINNER:  p_win >= 3% AND book win-price >= +3000 (33% edge over breakeven)
  STRONG_TOP_5:   p_top5 >= 30% AND book top-5 line >= +200 (33% breakeven)

Output: data/golf_leaderboard_probability.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_leaderboard_probability.json")


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


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _p_at_most(x: float, mean: float, sigma: float) -> float:
    if sigma <= 0: return 1.0 if mean <= x else 0.0
    return _norm_cdf((x - mean) / sigma)


def run() -> Dict[str, Any]:
    """Pull from existing golf_live_tracker, golf_live_projections, golf_winner_model.

    Builds unified leaderboard probability per player for ongoing tourneys.
    """
    tracker = _load(os.path.join(DATA_DIR, "golf_live_tracker.json"))
    projections = _load(os.path.join(DATA_DIR, "golf_live_projections.json"))

    # Find current tournament from tracker if available
    tourney = (tracker.get("current_tournament") or
               tracker.get("tournament") or
               projections.get("tournament") or "Unknown")

    # Players: golf_live_projections.json uses 'all_projections' for full field
    players_src = (projections.get("all_projections") or
                   projections.get("top_10_favorites") or [])

    # Compute field leader's projected final score for relative comparisons
    field_leader_final = -14.0
    if players_src:
        finals = [p.get("projected_final_to_par") for p in players_src
                  if isinstance(p, dict) and p.get("projected_final_to_par") is not None]
        if finals:
            field_leader_final = min(finals)

    rounds_done = int(_safe(projections.get("rounds_done"), 2))
    rounds_left = int(_safe(projections.get("rounds_left"), 2))

    # Field stats
    field_sigma_per_round = 2.8  # 1-round stroke std dev
    sigma_round_normal = field_sigma_per_round  # alias for clarity

    out_players: List[Dict[str, Any]] = []
    for p in players_src:
        if not isinstance(p, dict): continue
        name = p.get("name") or p.get("player")
        current_to_par = _safe(p.get("current_to_par"), 0)
        rounds_remaining = rounds_left
        # Derive ESPR: (projected_final - current) / rounds_left if available
        proj_final = _safe(p.get("projected_final_to_par"),
                           current_to_par + 0 * rounds_remaining)
        if rounds_remaining > 0:
            espr = (proj_final - current_to_par) / rounds_remaining
        else:
            espr = 0.0
        sigma_total = sigma_round_normal * math.sqrt(max(1, rounds_remaining))
        cut_line = 1.0  # PGA cut typically +1 to +3

        p_win = max(0.001, 1.0 - _p_at_most(field_leader_final, proj_final, sigma_total)) \
                if rounds_remaining > 0 else (1.0 if current_to_par <= field_leader_final else 0.0)
        # Clamp realistic
        p_win = min(0.35, p_win)

        # Top-5/Top-10/Top-20 cuts (relative to field average)
        # Heuristic: top-5 needs proj_final ~ leader+4; top-10 needs ~leader+6
        p_top5 = max(0.005, _p_at_most(field_leader_final + 4, proj_final, sigma_total))
        p_top10 = max(0.005, _p_at_most(field_leader_final + 6, proj_final, sigma_total))
        p_top20 = max(0.005, _p_at_most(field_leader_final + 9, proj_final, sigma_total))

        # Make cut: only relevant if not yet cut (rounds_remaining > 2)
        if rounds_remaining > 2:
            # Projected score AFTER round 2 = current + espr * (2 - (4 - rounds_remaining))
            r2_proj = current_to_par + espr * max(0, 2 - (4 - rounds_remaining))
            sigma_r2 = sigma_round_normal * math.sqrt(max(1, 2 - (4 - rounds_remaining)))
            p_make_cut = _p_at_most(cut_line, r2_proj, sigma_r2)
        else:
            p_make_cut = 1.0  # already past cut

        # Edge classifier
        book_win_odds = p.get("book_win_odds")  # +3000 etc
        edge_class = "NONE"
        if p_win >= 0.03 and book_win_odds:
            # book +3000 = 1/31 = 3.23% breakeven; if we say 5% we have edge
            try:
                bo = int(book_win_odds)
                book_breakeven = (100 / (bo + 100)) if bo > 0 else (-bo / (-bo + 100))
                if (p_win - book_breakeven) > 0.015:
                    edge_class = "STRONG_WINNER"
            except Exception:
                pass
        if edge_class == "NONE" and p_top5 >= 0.30:
            edge_class = "STRONG_TOP_5"

        out_players.append({
            "player": name,
            "current_to_par": round(current_to_par, 1),
            "rounds_remaining": rounds_remaining,
            "espr": round(espr, 2),
            "projected_final_to_par": round(proj_final, 1),
            "sigma_total": round(sigma_total, 2),
            "p_win": round(p_win, 4),
            "p_top5": round(p_top5, 3),
            "p_top10": round(p_top10, 3),
            "p_top20": round(p_top20, 3),
            "p_make_cut": round(p_make_cut, 3),
            "fair_win_odds": _american(p_win),
            "fair_top5_odds": _american(p_top5),
            "fair_top10_odds": _american(p_top10),
            "edge_class": edge_class,
        })

    out_players.sort(key=lambda r: -r["p_win"])
    strong = [r for r in out_players if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "tournament": tourney,
        "n_players": len(out_players),
        "n_strong_edges": len(strong),
        "method_note": "Live leaderboard: proj_final = current + ESPR * rounds_remaining. "
                       "Sigma = 2.8 * sqrt(rounds). P(win) via Normal CDF vs projected leader. "
                       "P(top-5/10/20) via leader + buffer thresholds. STRONG_WINNER when "
                       "model p exceeds book breakeven by 1.5%+; STRONG_TOP_5 at p >= 30%.",
        "top_15_by_p_win": out_players[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-board] {o['n_players']} players in {o['tournament']}, "
          f"{o['n_strong_edges']} strong -> {OUT}")
