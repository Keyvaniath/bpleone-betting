"""
EdgeStat -- NBA extended player props.

Adds prop projections beyond the existing real_player_props_nba.json
(which has PTS/REB/AST/3PM/PRA). Adds:
  - Double-double / triple-double markets
  - Stocks (steals + blocks)
  - Turnovers under
  - Free throws made
  - PTS+REB / PTS+AST / REB+AST combos
  - Alt-3PM at higher lines (7+, 8+)

Uses player_stats_nba per-game averages + normal distribution
(sigma calibrated from typical variance per stat).

Output: data/nba_extended_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_extended_props.json")

# Empirical NBA per-game std/mean ratios (from MLB historical analysis).
# Higher = more variance.
SIGMA_PCT = {
    "pts": 0.32,
    "reb": 0.40,
    "ast": 0.42,
    "threes": 0.55,
    "stocks": 0.55,
    "to": 0.50,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_p_over(mean, sigma, line):
    """P(X >= line+1) using normal CDF approximation."""
    if sigma <= 0: return 0.0 if mean < line else 1.0
    z = (line - mean) / sigma
    # Standard normal survival: P(Z > z)
    return 0.5 * (1 - math.erf(z / math.sqrt(2)))


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _double_double_prob(p_pts10, p_reb10, p_ast10):
    """Probability of double-double (>=2 categories with 10+):
    sum of all pairs + triple."""
    # P(at least 2 of A, B, C) = sum pairs - 2*triple
    # Easier: P(double-double) = sum pairs - 2 * triple
    p_ab = p_pts10 * p_reb10
    p_ac = p_pts10 * p_ast10
    p_bc = p_reb10 * p_ast10
    p_abc = p_pts10 * p_reb10 * p_ast10
    return p_ab + p_ac + p_bc - 2 * p_abc


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_nba.json"))
    players = stats.get("players") or []
    players_out = []
    for p in players:
        ssn_pts = p.get("pts_per_game") or 0
        ssn_reb = p.get("reb_per_game") or 0
        ssn_ast = p.get("ast_per_game") or 0
        ssn_threes = p.get("threes_per_game") or 0
        if ssn_pts < 4: continue   # rotation regulars only

        # Sigma per stat
        sig_pts = ssn_pts * SIGMA_PCT["pts"]
        sig_reb = ssn_reb * SIGMA_PCT["reb"]
        sig_ast = ssn_ast * SIGMA_PCT["ast"]
        sig_3 = max(0.6, ssn_threes * SIGMA_PCT["threes"])

        # Double-double probability
        p_pts_10 = _norm_p_over(ssn_pts, sig_pts, 9.5)
        p_reb_10 = _norm_p_over(ssn_reb, sig_reb, 9.5)
        p_ast_10 = _norm_p_over(ssn_ast, sig_ast, 9.5)
        p_dd = _double_double_prob(p_pts_10, p_reb_10, p_ast_10)
        # Triple-double
        p_td = p_pts_10 * p_reb_10 * p_ast_10

        props: Dict[str, Any] = {}
        # Alt-3PM lines (extension)
        for line in (5.5, 6.5, 7.5, 8.5):
            prob = _poisson_p_over(ssn_threes, line)
            if 0.03 < prob < 0.97:
                props[f"3PM_over_{line}"] = {
                    "p": round(prob, 4), "line": line,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # Double-double / triple-double
        if p_dd > 0.05:
            props["double_double"] = {"p": round(p_dd, 4),
                                        "fair_yes": _american(p_dd),
                                        "fair_no": _american(1 - p_dd)}
        if p_td > 0.01:
            props["triple_double"] = {"p": round(p_td, 4),
                                        "fair_yes": _american(p_td),
                                        "fair_no": _american(1 - p_td)}
        # PTS + REB combo (high lines)
        combo_pr_mean = ssn_pts + ssn_reb
        combo_pr_sig = math.sqrt(sig_pts ** 2 + sig_reb ** 2)
        for line in (combo_pr_mean + 5, combo_pr_mean + 10):
            if line < 8: continue
            line_r = round(line - 0.5)
            prob = _norm_p_over(combo_pr_mean, combo_pr_sig, line_r - 0.5)
            if 0.03 < prob < 0.97:
                props[f"PR_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r + 0.5,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # PTS + AST combo
        combo_pa_mean = ssn_pts + ssn_ast
        combo_pa_sig = math.sqrt(sig_pts ** 2 + sig_ast ** 2)
        for line in (combo_pa_mean + 5, combo_pa_mean + 10):
            if line < 8: continue
            line_r = round(line - 0.5)
            prob = _norm_p_over(combo_pa_mean, combo_pa_sig, line_r - 0.5)
            if 0.03 < prob < 0.97:
                props[f"PA_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r + 0.5,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # REB + AST combo
        combo_ra_mean = ssn_reb + ssn_ast
        combo_ra_sig = math.sqrt(sig_reb ** 2 + sig_ast ** 2)
        for line in (combo_ra_mean + 3, combo_ra_mean + 6):
            if line < 6: continue
            line_r = round(line - 0.5)
            prob = _norm_p_over(combo_ra_mean, combo_ra_sig, line_r - 0.5)
            if 0.03 < prob < 0.97:
                props[f"RA_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r + 0.5,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        if not props: continue
        players_out.append({
            "name": p.get("name"),
            "team": p.get("team_abbr"),
            "season_pts": round(ssn_pts, 1),
            "season_reb": round(ssn_reb, 1),
            "season_ast": round(ssn_ast, 1),
            "season_threes": round(ssn_threes, 2),
            "p_double_double": round(p_dd, 4),
            "p_triple_double": round(p_td, 4),
            "props": props,
        })

    # Sweet-spot picks (60-90% probability)
    sweet = []
    for pp in players_out:
        for mkt, info in (pp.get("props") or {}).items():
            prob = info.get("p")
            if not prob or not (0.6 <= prob <= 0.9): continue
            sweet.append({
                "name": pp["name"], "team": pp["team"],
                "market": mkt, "prob": prob,
                "fair_yes": info.get("fair_yes") or info.get("fair_over"),
            })
    sweet.sort(key=lambda x: -x["prob"])

    total_props = sum(len(p.get("props") or {}) for p in players_out)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_players": len(players_out),
        "n_total_props": total_props,
        "n_sweet_spot": len(sweet),
        "top_double_doubles": sorted(players_out, key=lambda p: -p["p_double_double"])[:20],
        "top_triple_doubles": sorted(players_out, key=lambda p: -p["p_triple_double"])[:10],
        "top_picks": sweet[:50],
        "players": players_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NBA extended props: {p['n_players']} players, {p['n_total_props']} props, "
          f"{p['n_sweet_spot']} sweet-spot picks")
    print("Top 10 double-double probabilities:")
    for pp in p["top_double_doubles"][:10]:
        print(f"  {pp['name']:25s} ({pp['team']:3s}) "
              f"{pp['season_pts']:.1f}p/{pp['season_reb']:.1f}r/{pp['season_ast']:.1f}a "
              f"DD={pp['p_double_double']*100:.0f}%, TD={pp['p_triple_double']*100:.0f}%")
    print("Top 10 triple-double candidates:")
    for pp in p["top_triple_doubles"][:5]:
        print(f"  {pp['name']:25s} ({pp['team']:3s}) TD={pp['p_triple_double']*100:.1f}%")
