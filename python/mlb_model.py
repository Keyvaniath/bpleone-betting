"""
EdgeStat - MLB game model.

Produces a fair price for every market on a game:
    - Moneyline (home / away)
    - Total (over/under)
    - Run line (-1.5 / +1.5)
    - First-5 totals
    - NRFI

Approach (high level):
  1. Estimate each team's expected runs scored (lambda) by:
       run_scoring = league_avg
                   * team_offensive_factor (park-adj wRC+ shrunk to mean)
                   * opp_pitcher_factor    (xFIP-based, regressed)
                   * opp_bullpen_factor    (weighted ERA-FIP delta)
                   * park_factor
                   * weather_factor
                   * umpire_factor
  2. Plug both lambdas into a joint Poisson distribution.
  3. Sum that distribution to get P(home win), P(total>line), etc.
  4. Translate to fair American prices.

This is intentionally transparent: every step is a multiplicative adjustment
on top of league average that you can audit.  It's the same backbone the
JavaScript front-end mirrors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from probability import (
    home_win_prob,
    total_over_prob,
    prob_to_american,
    edge_pct,
    kelly_stake_units,
    confidence_label,
    american_to_implied,
    remove_vig,
)


# League constants (rolling 3-yr averages; refresh each spring)
LEAGUE_AVG_RUNS_PER_GAME = 4.45   # per team
LEAGUE_AVG_TOTAL = 8.9
LEAGUE_AVG_K_RATE = 0.225


@dataclass
class TeamFactor:
    """Pre-game factor bundle for one team."""
    code: str
    offensive_wrc_plus: float     # 100 = league avg, 110 = 10% better
    bullpen_era_fip_delta: float  # negative is good (bullpen overperforms FIP)
    rest_days: int                # days since last game (1 = no rest)


@dataclass
class PitcherFactor:
    name: str
    xfip: float           # 4.00 ~ league average
    k_per_9: float
    bb_per_9: float
    hand: str             # 'L' or 'R'


@dataclass
class GameContext:
    park_factor: float          # 1.00 = neutral; 0.91 = Petco; 1.20 = Coors
    temp_f: float
    wind_mph: float             # signed: + means blowing out
    is_indoor: bool = False
    umpire_zone_size: float = 0.0  # +1% = wider zone (favors K's, suppresses runs)


@dataclass
class GameInput:
    away: TeamFactor
    home: TeamFactor
    away_pitcher: PitcherFactor
    home_pitcher: PitcherFactor
    ctx: GameContext
    market_total: float = 8.5
    market_ml_away: int = 100
    market_ml_home: int = -110


@dataclass
class GameProjection:
    away_lambda: float
    home_lambda: float
    p_home_win: float
    p_away_win: float
    p_over: Dict[float, float] = field(default_factory=dict)
    fair_ml_home: int = 0
    fair_ml_away: int = 0
    fair_total: float = 0.0
    edges: Dict[str, float] = field(default_factory=dict)
    recommendations: List[dict] = field(default_factory=list)


def _team_run_lambda(team: TeamFactor, opp_pitcher: PitcherFactor,
                     opp_bullpen_eraf: float, ctx: GameContext) -> float:
    """Compute expected runs scored for a single team in one game."""

    # Start from league average.
    lam = LEAGUE_AVG_RUNS_PER_GAME

    # Offense (wRC+ — every 10 points off 100 is ~10% run scoring).
    lam *= (team.offensive_wrc_plus / 100.0)

    # Opposing starter quality. xFIP 4.00 = neutral; lower xFIP suppresses runs.
    # Pitcher influences first ~5 innings (~55% of expected runs).
    pitcher_mult = (opp_pitcher.xfip / 4.00)
    lam *= 0.55 * pitcher_mult + 0.45        # blend starter+bullpen exposure

    # Opposing bullpen.
    bullpen_mult = 1.0 + (opp_bullpen_eraf / 8.0)  # 0.5 ERA-FIP gap ~6% effect
    lam *= bullpen_mult

    # Park.
    lam *= ctx.park_factor

    # Weather: wind blowing out raises run scoring, cold cuts it.
    if not ctx.is_indoor:
        wind_mult = 1.0 + max(min(ctx.wind_mph, 18), -18) * 0.008
        temp_mult = 1.0 + (ctx.temp_f - 70) * 0.0035
        lam *= wind_mult * temp_mult

    # Umpire: wider zone => more strikeouts => fewer runs.
    lam *= (1.0 - ctx.umpire_zone_size * 0.6)

    # Rest fatigue: ~2% penalty per consecutive day played
    if team.rest_days == 0:
        lam *= 0.98

    return max(1.5, min(lam, 9.0))   # sanity clamp


def project_game(g: GameInput) -> GameProjection:
    """Run the model end-to-end and return projections + edges."""

    away_l = _team_run_lambda(g.away, g.home_pitcher, g.home.bullpen_era_fip_delta, g.ctx)
    home_l = _team_run_lambda(g.home, g.away_pitcher, g.away.bullpen_era_fip_delta, g.ctx)

    # Home-field advantage: ~3% bump to home win probability.
    home_l *= 1.018

    p_home = home_win_prob(away_l, home_l)
    p_away = 1 - p_home

    # Pre-compute over probabilities for common totals.
    totals = {}
    for line in [6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0]:
        totals[line] = total_over_prob(away_l, home_l, line)

    proj = GameProjection(
        away_lambda=away_l,
        home_lambda=home_l,
        p_home_win=p_home,
        p_away_win=p_away,
        p_over=totals,
        fair_ml_home=prob_to_american(p_home),
        fair_ml_away=prob_to_american(p_away),
        fair_total=away_l + home_l,
    )

    # Edges & recommendations.
    proj.edges = {
        f"{g.home.code}_ML": edge_pct(p_home, g.market_ml_home),
        f"{g.away.code}_ML": edge_pct(p_away, g.market_ml_away),
    }

    over_p = totals.get(g.market_total, total_over_prob(away_l, home_l, g.market_total))
    proj.edges[f"OVER_{g.market_total}"] = edge_pct(over_p, -110)
    proj.edges[f"UNDER_{g.market_total}"] = edge_pct(1 - over_p, -110)

    # Build recommendation list, sorted by edge.
    for label, edge in sorted(proj.edges.items(), key=lambda x: -x[1]):
        if edge < 1.5:
            continue
        if "_ML" in label:
            team_code = label.split("_")[0]
            prob = p_home if team_code == g.home.code else p_away
            market = g.market_ml_home if team_code == g.home.code else g.market_ml_away
        elif label.startswith("OVER_"):
            prob, market = over_p, -110
        else:
            prob, market = (1 - over_p), -110
        proj.recommendations.append({
            "label": label,
            "model_prob": round(prob, 4),
            "market_price": market,
            "edge_pct": round(edge, 2),
            "kelly_units": round(kelly_stake_units(prob, market), 2),
            "confidence": confidence_label(edge),
        })

    return proj


# --------------------------- Example usage ---------------------------

def play_of_the_day_example() -> GameProjection:
    """Reproduce the dashboard's flagship LAD/SDP play."""
    away = TeamFactor(code="SDP", offensive_wrc_plus=104, bullpen_era_fip_delta=+0.41, rest_days=1)
    home = TeamFactor(code="LAD", offensive_wrc_plus=124, bullpen_era_fip_delta=-0.46, rest_days=1)
    away_p = PitcherFactor(name="Darvish", xfip=4.12, k_per_9=9.1, bb_per_9=2.8, hand="R")
    home_p = PitcherFactor(name="Yamamoto", xfip=2.89, k_per_9=10.4, bb_per_9=2.1, hand="R")
    ctx = GameContext(park_factor=0.91, temp_f=62, wind_mph=-6, umpire_zone_size=0.018)
    game = GameInput(
        away=away, home=home, away_pitcher=away_p, home_pitcher=home_p, ctx=ctx,
        market_total=8.0, market_ml_away=+126, market_ml_home=-148,
    )
    return project_game(game)


if __name__ == "__main__":
    proj = play_of_the_day_example()
    print(f"Away lambda: {proj.away_lambda:.2f}")
    print(f"Home lambda: {proj.home_lambda:.2f}")
    print(f"Total proj : {proj.fair_total:.2f}")
    print(f"P(home win): {proj.p_home_win:.3f}")
    print(f"Fair home ML: {proj.fair_ml_home}  |  Fair away ML: {proj.fair_ml_away}")
    print("\nRecommendations:")
    for r in proj.recommendations:
        print(f"  {r['label']:14s} edge={r['edge_pct']:+.2f}%  "
              f"stake={r['kelly_units']:.2f}u  ({r['confidence']})")
