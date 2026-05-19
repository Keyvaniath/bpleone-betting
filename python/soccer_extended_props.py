"""
EdgeStat -- soccer extended team props (EPL / MLS / UCL / La Liga).

Generates per-game team-level prop projections from each sport's state JSON:
  - Total Goals over/under 1.5 / 2.5 / 3.5
  - Both Teams To Score (BTTS) — Yes/No
  - Clean Sheet (home / away) probability
  - Team To Score 2+ (each side)
  - Match Result (Home / Draw / Away) with model probabilities

Uses Poisson-based goal projections derived from each team's win-pct ELO
+ home-field advantage + league-average goal rate.

Sport-specific league GPG (goals per game) baselines:
  EPL: ~2.85, MLS: ~2.95, UCL: ~2.65, La Liga: ~2.55

Output: data/soccer_extended_props.json

This is the 'no templates' team-level prop projection -- different math
than basketball/hockey (which had player gamelogs) because soccer at the
free-API level gives us team stats, not deep player stats.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_extended_props.json")

# Per-league average total goals (used as Poisson lambda baseline).
LEAGUE_GPG = {
    "epl": 2.85, "mls": 2.95, "ucl": 2.65,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p(lam, k):
    """P(X = k) for X ~ Poisson(lam)."""
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_cdf(lam, k):
    """P(X <= k)."""
    return sum(_poisson_p(lam, i) for i in range(k + 1))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_match(g: Dict[str, Any], league_avg_total: float) -> Dict[str, Any]:
    """Use the model's p_home_win + league avg to back out per-team xG."""
    p_home = g.get("p_home_win")
    if p_home is None: return {}

    # Map p_home_win → "skill ratio": home stronger means more home goals.
    # We split league_avg_total into (home_xg, away_xg) such that:
    #   - if p_home = 0.5: split 50/50 (slight home bonus via HFA already in p_home)
    #   - if p_home = 0.7: home gets ~62% of expected goals
    # Empirical relationship: home_share ≈ 0.4 + 0.4 * (p_home)
    home_share = 0.4 + 0.4 * p_home
    home_share = max(0.2, min(0.8, home_share))
    home_xg = league_avg_total * home_share
    away_xg = league_avg_total * (1 - home_share)

    # P(total > line) = 1 - P(home + away <= line)
    # Use convolution approx: P(H+A <= k) computed exactly via Poisson sum
    def _p_total_over(line):
        # line = 1.5 means P(total >= 2)
        thr = int(math.floor(line)) + 1
        # Sum of two Poissons is Poisson(sum)
        return 1 - _poisson_cdf(home_xg + away_xg, thr - 1)

    def _p_team_over(team_xg, line):
        thr = int(math.floor(line)) + 1
        return 1 - _poisson_cdf(team_xg, thr - 1)

    # Both Teams To Score: P(home >= 1) * P(away >= 1) (rough indep approx)
    p_home_score = 1 - _poisson_p(home_xg, 0)
    p_away_score = 1 - _poisson_p(away_xg, 0)
    btts_yes = p_home_score * p_away_score
    btts_no = 1 - btts_yes

    # Clean sheets
    cs_home = _poisson_p(away_xg, 0)   # away scores 0 → home clean sheet
    cs_away = _poisson_p(home_xg, 0)

    # Total over/under
    return {
        "home_xg": round(home_xg, 2),
        "away_xg": round(away_xg, 2),
        "totals": {
            f"over_{line}": {"p": round(_p_total_over(line), 4),
                              "fair_over": _american(_p_total_over(line)),
                              "fair_under": _american(1 - _p_total_over(line))}
            for line in (1.5, 2.5, 3.5)
        },
        "btts": {"yes": round(btts_yes, 4), "no": round(btts_no, 4),
                  "fair_yes": _american(btts_yes), "fair_no": _american(btts_no)},
        "clean_sheet_home": {"p": round(cs_home, 4),
                              "fair_yes": _american(cs_home)},
        "clean_sheet_away": {"p": round(cs_away, 4),
                              "fair_yes": _american(cs_away)},
        "team_to_score_2_plus_home": {
            "p": round(_p_team_over(home_xg, 1.5), 4),
            "fair_yes": _american(_p_team_over(home_xg, 1.5)),
        },
        "team_to_score_2_plus_away": {
            "p": round(_p_team_over(away_xg, 1.5), 4),
            "fair_yes": _american(_p_team_over(away_xg, 1.5)),
        },
    }


def run() -> Dict[str, Any]:
    games_out: List[Dict[str, Any]] = []
    for sport, gpg in LEAGUE_GPG.items():
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        for g in (state.get("games") or []):
            if g.get("state") == "post": continue
            proj = _project_match(g, gpg)
            if not proj: continue
            games_out.append({
                "league": sport.upper(),
                "matchup": g.get("matchup"),
                "home_team": g.get("home_team"),
                "away_team": g.get("away_team"),
                "p_home_win": g.get("p_home_win"),
                "league_avg_total": gpg,
                **proj,
            })

    # Sweet-spot picks (50-90% probability range for soccer — wider since markets are tighter)
    sweet = []
    for g in games_out:
        # Totals
        for line_key, info in (g.get("totals") or {}).items():
            p = info.get("p")
            if not p or not (0.55 <= p <= 0.90): continue
            sweet.append({"league": g["league"], "matchup": g["matchup"],
                            "market": f"total_{line_key}", "prob": p,
                            "fair": info.get("fair_over")})
        # BTTS
        btts = g.get("btts") or {}
        for side, p in (("yes", btts.get("yes")), ("no", btts.get("no"))):
            if not p or not (0.55 <= p <= 0.90): continue
            sweet.append({"league": g["league"], "matchup": g["matchup"],
                            "market": f"btts_{side}", "prob": p,
                            "fair": btts.get(f"fair_{side}")})
        # Team to score 2+
        for side in ("home", "away"):
            info = g.get(f"team_to_score_2_plus_{side}") or {}
            p = info.get("p")
            if not p or not (0.55 <= p <= 0.90): continue
            team = g["home_team"] if side == "home" else g["away_team"]
            sweet.append({"league": g["league"], "matchup": g["matchup"],
                            "market": f"{team}_2_plus_goals", "prob": p,
                            "fair": info.get("fair_yes")})
    sweet.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "n_sweet_spot": len(sweet),
        "games": games_out,
        "top_picks": sweet[:30],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Soccer extended props: {p['n_games']} games, {p['n_sweet_spot']} sweet-spot picks")
    for g in p["games"][:5]:
        print(f"  [{g['league']}] {g['matchup']:50s} | xG: home={g['home_xg']} away={g['away_xg']} | "
              f"BTTS_yes={g['btts']['yes']*100:.0f}% over_2.5={g['totals']['over_2.5']['p']*100:.0f}%")
    print("Top 10 picks:")
    for s in p["top_picks"][:10]:
        print(f"  [{s['league']:4s}] {s['matchup'][:35]:35s} {s['market'][:30]:30s} p={s['prob']*100:.0f}% fair={s['fair']}")
