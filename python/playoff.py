"""
EdgeStat - Playoff projection model.

Convert current W-L records + remaining schedule + team strength into
season-end W/L distributions and playoff probabilities.

Workflow:
  1. Take each team's current record + Elo / Glicko / true talent.
  2. For each remaining game, draw a Bernoulli outcome based on the
     opponent's strength.
  3. Roll up to season-end win totals.
  4. Apply MLB playoff format (3 division winners + 3 wild cards per league)
     to decide who makes it.
  5. Run ~5,000 simulations; aggregate probabilities.

Sportsbooks post season-long markets (Win Total, To Make Playoffs, To Win
Division, To Win World Series) and these have historically been some of the
softest markets in baseball because they require a long-horizon model.
"""
from __future__ import annotations

import math
import random
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class Team:
    code: str
    division: str           # "NLW", "NLC", "NLE", "ALW", "ALC", "ALE"
    league: str             # "NL" / "AL"
    wins: int
    losses: int
    true_p_per_game: float  # win prob vs avg team in avg context

    @property
    def games_played(self) -> int:
        return self.wins + self.losses


# --------------------------- Single season simulation ---------------------------

def _play_game(team_a: Team, team_b: Team, rng: random.Random,
               hfa: float = 0.03, home: bool = True) -> bool:
    """Return True if team A wins."""
    # Bradley-Terry style.  Convert two true_p values into head-to-head.
    pa = team_a.true_p_per_game / (team_a.true_p_per_game + (1 - team_b.true_p_per_game))
    pa = max(0.20, min(0.80, pa + (hfa if home else -hfa)))
    return rng.random() < pa


def simulate_remaining_season(teams: List[Team],
                              remaining_games_per_team: int = 60,
                              rng: Optional[random.Random] = None) -> Dict[str, Dict]:
    """Simulate the rest of the season once.  Returns per-team final W/L."""
    rng = rng or random.Random()
    final = {t.code: {"wins": t.wins, "losses": t.losses} for t in teams}
    # Each team plays `remaining_games_per_team` more games.
    # Pair them randomly (rough approximation; production uses real schedule).
    n = len(teams)
    for t in teams:
        for _ in range(remaining_games_per_team):
            opp = teams[rng.randint(0, n - 1)]
            if opp.code == t.code:
                continue
            # Random home/away.
            home = rng.random() < 0.5
            if _play_game(t, opp, rng, home=home):
                final[t.code]["wins"] += 1
            else:
                final[t.code]["losses"] += 1
    return final


# --------------------------- Playoff format ---------------------------

def determine_playoff_qualifiers(final_wins: Dict[str, int],
                                 teams: List[Team]) -> Dict[str, List[str]]:
    """Apply MLB playoff format: 3 division winners + 3 wild cards per league."""
    # Build standings per division.
    div_groups: Dict[str, List[Team]] = {}
    for t in teams:
        div_groups.setdefault(t.division, []).append(t)
    qualifiers = {"AL": [], "NL": []}
    division_winners = []
    leftovers = {"AL": [], "NL": []}
    for div, group in div_groups.items():
        sorted_group = sorted(group, key=lambda t: -final_wins[t.code])
        winner = sorted_group[0]
        division_winners.append(winner.code)
        qualifiers[winner.league].append(winner.code)
        # The rest go into wild card pool.
        leftovers[winner.league].extend([t for t in sorted_group[1:]])
    # Wild cards: top 3 leftover teams per league by wins.
    for league in ("AL", "NL"):
        sorted_lo = sorted(leftovers[league], key=lambda t: -final_wins[t.code])
        for t in sorted_lo[:3]:
            qualifiers[league].append(t.code)
    return {
        "playoffs": qualifiers["AL"] + qualifiers["NL"],
        "division_winners": division_winners,
    }


# --------------------------- Multi-sim aggregator ---------------------------

@dataclass
class PlayoffOdds:
    code: str
    p_playoffs: float
    p_division: float
    p_world_series: float
    win_total_dist: Dict[int, float] = field(default_factory=dict)
    expected_wins: float = 0.0


def run_projections(teams: List[Team],
                    remaining_games_per_team: int = 60,
                    n_sims: int = 2000, seed: int = 19) -> List[PlayoffOdds]:
    rng = random.Random(seed)
    n_sims_made_playoffs = {t.code: 0 for t in teams}
    n_sims_won_div = {t.code: 0 for t in teams}
    n_sims_won_world = {t.code: 0 for t in teams}
    win_totals = {t.code: [] for t in teams}
    for _ in range(n_sims):
        final_wls = simulate_remaining_season(teams, remaining_games_per_team, rng)
        final_wins = {k: v["wins"] for k, v in final_wls.items()}
        qual = determine_playoff_qualifiers(final_wins, teams)
        for code in qual["playoffs"]:
            n_sims_made_playoffs[code] += 1
        for code in qual["division_winners"]:
            n_sims_won_div[code] += 1
        # Crude World Series winner: top-seeded playoff team by final wins,
        # then sample with weight ~ Elo.  Production would do bracket sim.
        if qual["playoffs"]:
            # Weighted random pick by wins.
            cands = qual["playoffs"]
            ws = [final_wins[c] for c in cands]
            total = sum(ws)
            r = rng.random() * total
            cum = 0
            winner = cands[-1]
            for c, w in zip(cands, ws):
                cum += w
                if r <= cum:
                    winner = c
                    break
            n_sims_won_world[winner] += 1
        for code, fw in final_wins.items():
            win_totals[code].append(fw)
    # Aggregate.
    out: List[PlayoffOdds] = []
    for t in teams:
        wt = win_totals[t.code]
        dist: Dict[int, float] = {}
        for v in wt:
            dist[v] = dist.get(v, 0) + 1
        for k in dist:
            dist[k] = round(dist[k] / n_sims, 4)
        out.append(PlayoffOdds(
            code=t.code,
            p_playoffs=round(n_sims_made_playoffs[t.code] / n_sims, 4),
            p_division=round(n_sims_won_div[t.code] / n_sims, 4),
            p_world_series=round(n_sims_won_world[t.code] / n_sims, 4),
            win_total_dist=dist,
            expected_wins=round(sum(wt) / n_sims, 2),
        ))
    out.sort(key=lambda o: -o.p_world_series)
    return out


# --------------------------- Demo ---------------------------

DEMO_TEAMS = [
    # AL West
    Team("HOU", "ALW", "AL", 40, 28, 0.555),
    Team("TEX", "ALW", "AL", 42, 26, 0.582),
    Team("SEA", "ALW", "AL", 35, 33, 0.510),
    Team("LAA", "ALW", "AL", 30, 38, 0.451),
    # AL Central
    Team("CLE", "ALC", "AL", 38, 30, 0.535),
    Team("MIN", "ALC", "AL", 37, 31, 0.522),
    Team("DET", "ALC", "AL", 36, 32, 0.512),
    # AL East
    Team("NYY", "ALE", "AL", 44, 24, 0.605),
    Team("BAL", "ALE", "AL", 41, 27, 0.567),
    Team("TBR", "ALE", "AL", 33, 35, 0.498),
    Team("BOS", "ALE", "AL", 37, 31, 0.518),
    Team("TOR", "ALE", "AL", 33, 35, 0.495),
    # NL West
    Team("LAD", "NLW", "NL", 45, 23, 0.625),
    Team("SDP", "NLW", "NL", 34, 34, 0.495),
    Team("SFG", "NLW", "NL", 34, 34, 0.500),
    Team("ARI", "NLW", "NL", 35, 33, 0.510),
    # NL Central
    Team("CHC", "NLC", "NL", 38, 30, 0.530),
    Team("MIL", "NLC", "NL", 36, 32, 0.512),
    Team("STL", "NLC", "NL", 35, 33, 0.508),
    # NL East
    Team("PHI", "NLE", "NL", 43, 25, 0.591),
    Team("ATL", "NLE", "NL", 41, 27, 0.572),
    Team("NYM", "NLE", "NL", 34, 34, 0.502),
    Team("WSH", "NLE", "NL", 32, 36, 0.484),
]


def write_artifact(path: str = "../data/playoff_odds.json") -> None:
    odds = run_projections(DEMO_TEAMS, remaining_games_per_team=70, n_sims=1500, seed=23)
    payload = {
        "season_year": 2026,
        "n_sims": 1500,
        "remaining_games_per_team": 70,
        "as_of_record": {t.code: f"{t.wins}-{t.losses}" for t in DEMO_TEAMS},
        "projections": [{
            "code": o.code,
            "p_playoffs": o.p_playoffs,
            "p_division": o.p_division,
            "p_world_series": o.p_world_series,
            "expected_wins": o.expected_wins,
        } for o in odds]
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {path}")


if __name__ == "__main__":
    print("Running 1,500 season-end Monte Carlo simulations…")
    odds = run_projections(DEMO_TEAMS, remaining_games_per_team=70, n_sims=1500, seed=23)
    print(f"\n{'Team':6}{'EW':>6}{'P(playoffs)':>14}{'P(division)':>14}{'P(WS)':>10}")
    for o in odds:
        print(f"{o.code:6}{o.expected_wins:>6.1f}"
              f"{o.p_playoffs*100:>13.1f}%{o.p_division*100:>13.1f}%"
              f"{o.p_world_series*100:>9.2f}%")
    write_artifact()
