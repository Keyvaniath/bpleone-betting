"""
EdgeStat -- WNBA extended player props.

Mirrors nba_extended_props but tuned for the WNBA scoring environment:
  - Top scorers around 17-25 PPG (vs NBA 20-32)
  - Per-game rebound / assist scales similar
  - Slightly tighter alt-3PM lines (4.5/5.5/6.5)
  - Same DD / TD framework

Depends on player_stats_wnba.json being correct -- see espn_player_stats.py
NBA_IDX/WNBA_IDX comment for the stat-array column-order bug history.

Active-teams filter: only emit props for players on teams with a game
scheduled today (pulled from wnba_state.json). During WNBA playoffs / off
days this drops the output from ~120 players to whoever's actually playing.

Output: data/wnba_extended_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_extended_props.json")

# WNBA per-game std/mean ratios (similar to NBA but slightly tighter)
SIGMA_PCT = {
    "pts": 0.32,
    "reb": 0.40,
    "ast": 0.45,
    "threes": 0.60,
    "stocks": 0.55,
    "to": 0.50,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_p_over(mean, sigma, line):
    if sigma <= 0: return 0.0 if mean < line else 1.0
    z = (line - mean) / sigma
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
    p_ab = p_pts10 * p_reb10
    p_ac = p_pts10 * p_ast10
    p_bc = p_reb10 * p_ast10
    p_abc = p_pts10 * p_reb10 * p_ast10
    return p_ab + p_ac + p_bc - 2 * p_abc


def _active_teams_today() -> set:
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    active = set()
    for g in (state.get("games") or []):
        if g.get("state") == "post": continue
        for fld in ("home_team", "away_team"):
            v = g.get(fld)
            if v: active.add(v)
    return active


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_wnba.json"))
    players = stats.get("players") or []
    active_teams = _active_teams_today()
    is_filter = len(active_teams) > 0 and len(active_teams) <= 8

    players_out = []
    for p in players:
        if active_teams and p.get("team") not in active_teams:
            continue
        ssn_pts = p.get("pts_per_game") or 0
        ssn_reb = p.get("reb_per_game") or 0
        ssn_ast = p.get("ast_per_game") or 0
        ssn_threes = p.get("threes_per_game") or 0
        if ssn_pts < 3: continue   # rotation regulars only

        sig_pts = ssn_pts * SIGMA_PCT["pts"]
        sig_reb = max(0.8, ssn_reb * SIGMA_PCT["reb"])
        sig_ast = max(0.6, ssn_ast * SIGMA_PCT["ast"])
        sig_3 = max(0.5, ssn_threes * SIGMA_PCT["threes"])

        p_pts_10 = _norm_p_over(ssn_pts, sig_pts, 9.5)
        p_reb_10 = _norm_p_over(ssn_reb, sig_reb, 9.5)
        p_ast_10 = _norm_p_over(ssn_ast, sig_ast, 9.5)
        p_dd = _double_double_prob(p_pts_10, p_reb_10, p_ast_10)
        p_td = p_pts_10 * p_reb_10 * p_ast_10

        props: Dict[str, Any] = {}
        # PTS over (4 lines around mean)
        for offset in (-3.5, -1.5, 0.5, 2.5):
            line = ssn_pts + offset
            line_r = round(line - 0.5) + 0.5
            if line_r < 4.5: continue
            prob = _norm_p_over(ssn_pts, sig_pts, line_r)
            if 0.10 < prob < 0.95:
                props[f"PTS_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # REB over (2 lines)
        for offset in (-1.5, 0.5):
            line = ssn_reb + offset
            line_r = round(line - 0.5) + 0.5
            if line_r < 2.5: continue
            prob = _norm_p_over(ssn_reb, sig_reb, line_r)
            if 0.10 < prob < 0.95:
                props[f"REB_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # AST over (2 lines)
        for offset in (-1.5, 0.5):
            line = ssn_ast + offset
            line_r = round(line - 0.5) + 0.5
            if line_r < 1.5: continue
            prob = _norm_p_over(ssn_ast, sig_ast, line_r)
            if 0.10 < prob < 0.95:
                props[f"AST_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # Alt-3PM lines
        for line in (2.5, 3.5, 4.5, 5.5):
            prob = _poisson_p_over(ssn_threes, line)
            if 0.03 < prob < 0.95:
                props[f"3PM_over_{line}"] = {
                    "p": round(prob, 4), "line": line,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # Double-double / triple-double
        if p_dd > 0.05:
            props["double_double"] = {"p": round(p_dd, 4),
                                        "fair_yes": _american(p_dd),
                                        "fair_no": _american(1 - p_dd)}
        if p_td > 0.005:
            props["triple_double"] = {"p": round(p_td, 4),
                                        "fair_yes": _american(p_td),
                                        "fair_no": _american(1 - p_td)}
        # PTS+REB combo (high lines)
        combo_pr_mean = ssn_pts + ssn_reb
        combo_pr_sig = math.sqrt(sig_pts ** 2 + sig_reb ** 2)
        for offset in (-3, 3):
            line_r = round(combo_pr_mean + offset - 0.5) + 0.5
            if line_r < 6.5: continue
            prob = _norm_p_over(combo_pr_mean, combo_pr_sig, line_r)
            if 0.10 < prob < 0.95:
                props[f"PR_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # PTS+AST combo
        combo_pa_mean = ssn_pts + ssn_ast
        combo_pa_sig = math.sqrt(sig_pts ** 2 + sig_ast ** 2)
        for offset in (-3, 3):
            line_r = round(combo_pa_mean + offset - 0.5) + 0.5
            if line_r < 6.5: continue
            prob = _norm_p_over(combo_pa_mean, combo_pa_sig, line_r)
            if 0.10 < prob < 0.95:
                props[f"PA_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
                    "fair_over": _american(prob), "fair_under": _american(1 - prob)
                }
        # PRA combined
        pra_mean = ssn_pts + ssn_reb + ssn_ast
        pra_sig = math.sqrt(sig_pts ** 2 + sig_reb ** 2 + sig_ast ** 2)
        for offset in (-3, 3):
            line_r = round(pra_mean + offset - 0.5) + 0.5
            if line_r < 9.5: continue
            prob = _norm_p_over(pra_mean, pra_sig, line_r)
            if 0.10 < prob < 0.95:
                props[f"PRA_over_{line_r}"] = {
                    "p": round(prob, 4), "line": line_r,
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

    # Sweet-spot picks
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
        "active_teams_today": sorted(list(active_teams)),
        "n_active_teams": len(active_teams),
        "playoff_filter_applied": is_filter,
        "n_players": len(players_out),
        "n_total_props": total_props,
        "n_sweet_spot": len(sweet),
        "top_double_doubles": sorted(players_out, key=lambda p: -p["p_double_double"])[:15],
        "top_triple_doubles": sorted(players_out, key=lambda p: -p["p_triple_double"])[:5],
        "top_picks": sweet[:40],
        "players": players_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"WNBA extended props: {p['n_players']} players, {p['n_total_props']} props, "
          f"{p['n_sweet_spot']} sweet-spot picks")
    print(f"  Active teams: {p['n_active_teams']} ({', '.join(p['active_teams_today'][:6])})")
    print("\nTop 5 double-double probabilities:")
    for pp in p["top_double_doubles"][:5]:
        print(f"  {pp['name'][:25]:25s} ({pp['team']:3s}) "
              f"{pp['season_pts']:.1f}p/{pp['season_reb']:.1f}r/{pp['season_ast']:.1f}a "
              f"DD={pp['p_double_double']*100:.0f}%")
    print("\nTop 5 sweet-spot picks:")
    for x in p["top_picks"][:5]:
        print(f"  {x['name'][:22]:22s} ({x['team']:3s}) {x['market']:25s} "
              f"p={x['prob']*100:.0f}% fair={x['fair_yes']}")
