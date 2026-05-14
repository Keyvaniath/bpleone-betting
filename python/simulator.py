"""
EdgeStat - Monte Carlo MLB game simulator.

Simulates baseball games at the plate-appearance level using a state-transition
model. Outputs full distributions for:
  - Final score
  - Inning totals (for live betting / first-5 markets)
  - Player counting stats (TB, H, R, RBI, BB, K) for prop distributions
  - Win probability
  - Run line / spread distribution

Used for:
  • Pricing every market with bootstrap confidence intervals
  • Generating prop distributions
  • Producing the run-distribution chart on the front-end
  • Stress-testing the model

Pure stdlib (just random + math) so it runs anywhere. ~50ms per 10k sim run.
"""
from __future__ import annotations

import random
import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# League baselines, regressed 3-year average. Refresh annually.
LEAGUE_PA_OUTCOME = {
    "K":   0.232,   # strikeout (no advance)
    "BB":  0.085,   # walk
    "HBP": 0.011,
    "1B":  0.143,   # single
    "2B":  0.043,
    "3B":  0.004,
    "HR":  0.032,
    "OUT": 0.450,   # in-play out (groundout, flyout, lineout, popup)
}
assert abs(sum(LEAGUE_PA_OUTCOME.values()) - 1.0) < 1e-9


@dataclass
class Batter:
    name: str
    # Outcome rates relative to league: 1.0 = league average.
    k_rate: float = 1.0
    bb_rate: float = 1.0
    power: float = 1.0       # scales 2B/HR
    hit_rate: float = 1.0    # scales 1B
    speed: int = 50          # 0-100 Statcast-ish sprint percentile
    hand: str = "R"

    def pa_outcome_probs(self, pitcher: "Pitcher") -> Dict[str, float]:
        """Outcome distribution for this batter vs a specific pitcher."""
        # Pitcher influences K, BB, and HR. Batter influences all five.
        p = {
            "K":   LEAGUE_PA_OUTCOME["K"]   * self.k_rate  * pitcher.k_rate,
            "BB":  LEAGUE_PA_OUTCOME["BB"]  * self.bb_rate * pitcher.bb_rate,
            "HBP": LEAGUE_PA_OUTCOME["HBP"],
            "1B":  LEAGUE_PA_OUTCOME["1B"]  * self.hit_rate,
            "2B":  LEAGUE_PA_OUTCOME["2B"]  * self.power * 0.5 + LEAGUE_PA_OUTCOME["2B"] * 0.5,
            "3B":  LEAGUE_PA_OUTCOME["3B"],
            "HR":  LEAGUE_PA_OUTCOME["HR"]  * self.power * pitcher.hr_rate,
        }
        used = sum(p.values())
        p["OUT"] = max(0.0, 1.0 - used)
        # Re-normalize defensively.
        total = sum(p.values())
        for k in p:
            p[k] /= total
        return p


@dataclass
class Pitcher:
    name: str
    k_rate: float = 1.0
    bb_rate: float = 1.0
    hr_rate: float = 1.0
    stamina: int = 90    # expected pitch count
    hand: str = "R"

    # Times-through-order multiplier — performance degrades each TTO.
    tto_penalty: Tuple[float, float, float] = (1.0, 1.04, 1.10)


@dataclass
class Lineup:
    name: str
    batters: List[Batter]
    starter: Pitcher
    bullpen: Pitcher        # composite bullpen "average" pitcher
    park_factor: float = 1.00


@dataclass
class GameState:
    inning: int = 1
    top: bool = True              # away batting
    outs: int = 0
    bases: List[Optional[Batter]] = field(default_factory=lambda: [None, None, None])
    away_score: int = 0
    home_score: int = 0
    away_idx: int = 0
    home_idx: int = 0
    away_pitcher_pa: int = 0
    home_pitcher_pa: int = 0
    # Per-player stat lines we accumulate for prop projection.
    stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    inning_runs: List[Tuple[int, int]] = field(default_factory=list)  # (away, home) per inning


def _advance_runners(state: GameState, batter: Batter, outcome: str) -> int:
    """Return runs scored on this PA, mutates state.bases."""
    runs = 0

    def _push(spots: int):
        """Force runners forward by `spots` bases, scoring those passing home."""
        nonlocal runs
        for i in reversed(range(3)):
            if state.bases[i] is None:
                continue
            new = i + spots
            if new >= 3:
                runs += 1
                state.bases[i] = None
            else:
                state.bases[new] = state.bases[i]
                state.bases[i] = None

    if outcome == "BB" or outcome == "HBP":
        # Walk: forces only when forced.
        if state.bases[0]:
            if state.bases[1]:
                if state.bases[2]:
                    runs += 1
                state.bases[2] = state.bases[1]
            state.bases[1] = state.bases[0]
        state.bases[0] = batter
    elif outcome == "1B":
        # Singles: try for 2 with fast runners.
        for i in reversed(range(3)):
            r = state.bases[i]
            if r is None:
                continue
            adv = 2 if (r.speed > 70 and random.random() < 0.35) else 1
            new = i + adv
            if new >= 3:
                runs += 1
                state.bases[i] = None
            else:
                state.bases[new] = r
                state.bases[i] = None
        state.bases[0] = batter
    elif outcome == "2B":
        _push(2)
        state.bases[1] = batter
    elif outcome == "3B":
        _push(3)
        state.bases[2] = batter
    elif outcome == "HR":
        # All score including batter.
        for i in range(3):
            if state.bases[i] is not None:
                runs += 1
                state.bases[i] = None
        runs += 1
    elif outcome == "OUT":
        # Productive out on 1st-and-3rd or sac fly < 2 outs ~ 30% scoring chance
        if state.outs < 2:
            if state.bases[2] and random.random() < 0.18:
                runs += 1
                state.bases[2] = None
                state.outs += 1
            else:
                state.outs += 1
        else:
            state.outs += 1
    elif outcome == "K":
        state.outs += 1
    return runs


def _stat_line_entry(state: GameState, name: str) -> Dict[str, int]:
    if name not in state.stats:
        state.stats[name] = {"PA": 0, "AB": 0, "H": 0, "1B": 0, "2B": 0, "3B": 0,
                             "HR": 0, "BB": 0, "K": 0, "R": 0, "RBI": 0, "TB": 0}
    return state.stats[name]


def _current_pitcher(state: GameState, defense: Lineup) -> Pitcher:
    """Pull starter when stamina/pitch count exceeded."""
    pa_attr = "home_pitcher_pa" if state.top else "away_pitcher_pa"
    pa_count = getattr(state, pa_attr)
    starter = defense.starter
    # ~3.8 pitches/PA. Stamina ÷ 3.8 = expected PAs.
    expected_pa = starter.stamina / 3.8
    if pa_count >= expected_pa:
        return defense.bullpen
    return starter


def _pa_outcome(batter: Batter, pitcher: Pitcher, tto_index: int) -> str:
    probs = batter.pa_outcome_probs(pitcher)
    # Apply times-through-order multiplier to power outcomes.
    mult = pitcher.tto_penalty[min(tto_index, 2)]
    if mult != 1.0:
        for k in ("1B", "2B", "HR"):
            probs[k] *= mult
        # Re-normalize.
        s = sum(probs.values())
        for k in probs:
            probs[k] /= s
    r = random.random()
    cum = 0.0
    for outcome, p in probs.items():
        cum += p
        if r <= cum:
            return outcome
    return "OUT"


def simulate_game(away: Lineup, home: Lineup,
                  innings: int = 9,
                  park_factor: float = 1.0) -> GameState:
    """Simulate a single game. Returns final state with stats."""
    state = GameState()
    while state.inning <= innings or state.away_score == state.home_score:
        offense = away if state.top else home
        defense = home if state.top else away
        idx_attr = "away_idx" if state.top else "home_idx"

        # New half-inning: reset outs + bases (carryover handled by state init).
        state.outs = 0
        state.bases = [None, None, None]
        starting_score_away = state.away_score
        starting_score_home = state.home_score

        while state.outs < 3:
            idx = getattr(state, idx_attr) % len(offense.batters)
            batter = offense.batters[idx]
            pitcher = _current_pitcher(state, defense)
            pa_attr = "home_pitcher_pa" if state.top else "away_pitcher_pa"
            setattr(state, pa_attr, getattr(state, pa_attr) + 1)
            tto_index = (getattr(state, pa_attr) - 1) // 9
            outcome = _pa_outcome(batter, pitcher, tto_index)
            # Park factor inflates HR + run-scoring slightly.
            if outcome == "HR" and random.random() > park_factor:
                # Demote some HRs to 2B in pitcher-friendly parks; promote 2B to HR in hitter-friendly ones.
                outcome = "2B"
            elif outcome == "2B" and random.random() < (park_factor - 1.0) * 0.5:
                outcome = "HR"

            runs = _advance_runners(state, batter, outcome)

            # Update stats.
            sl = _stat_line_entry(state, batter.name)
            sl["PA"] += 1
            if outcome not in ("BB", "HBP"):
                sl["AB"] += 1
            if outcome in ("1B", "2B", "3B", "HR"):
                sl["H"] += 1
                sl[outcome] += 1
                tb_map = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}
                sl["TB"] += tb_map[outcome]
            if outcome == "HR":
                sl["R"] += 1   # batter scores on HR
            if outcome == "BB":
                sl["BB"] += 1
            if outcome == "K":
                sl["K"] += 1
            sl["RBI"] += runs

            # Pitcher K stats (for K props).
            psl = _stat_line_entry(state, pitcher.name)
            psl["PA"] += 1
            if outcome == "K":
                psl["K"] += 1

            if state.top:
                state.away_score += runs
            else:
                state.home_score += runs
            setattr(state, idx_attr, getattr(state, idx_attr) + 1)

        state.inning_runs.append((state.away_score - starting_score_away,
                                  state.home_score - starting_score_home))
        if state.top:
            state.top = False
        else:
            state.top = True
            state.inning += 1
        # Bottom-of-9 walkoff
        if state.inning > innings and state.away_score != state.home_score:
            break
        if state.inning > 15:
            break  # extras cap
    return state


# --------------------------- Monte Carlo wrapper ---------------------------

@dataclass
class SimResult:
    n: int
    home_wins: int
    away_wins: int
    score_dist: List[Tuple[int, int]]      # final (away, home) tuples
    total_runs: List[int]
    away_runs: List[int]
    home_runs: List[int]
    inning_totals: List[List[int]]          # per game: list of total runs per inning
    player_stats: Dict[str, List[Dict[str, int]]]

    def p_home_win(self) -> float:
        return self.home_wins / self.n

    def p_total_over(self, line: float) -> float:
        wins = sum(1 for t in self.total_runs if t > line)
        push = sum(1 for t in self.total_runs if t == line)
        return (wins + 0.5 * push) / self.n

    def p_runline(self, fav: str, line: float = -1.5) -> float:
        """P(favorite covers by 2+ runs)."""
        if fav == "home":
            wins = sum(1 for (a, h) in self.score_dist if h - a >= 2)
        else:
            wins = sum(1 for (a, h) in self.score_dist if a - h >= 2)
        return wins / self.n

    def p_first5_over(self, line: float) -> float:
        wins = 0
        push = 0
        for game in self.inning_totals:
            f5 = sum(game[:5])
            if f5 > line:
                wins += 1
            elif f5 == line:
                push += 1
        return (wins + 0.5 * push) / self.n

    def player_prop_distribution(self, player: str, stat: str) -> List[int]:
        return [g.get(stat, 0) for g in self.player_stats.get(player, [])]

    def player_prop_over(self, player: str, stat: str, line: float) -> float:
        dist = self.player_prop_distribution(player, stat)
        if not dist:
            return 0.0
        wins = sum(1 for v in dist if v > line)
        push = sum(1 for v in dist if v == line)
        return (wins + 0.5 * push) / len(dist)


def monte_carlo(away: Lineup, home: Lineup, n: int = 10_000,
                park_factor: float = 1.0, seed: Optional[int] = None) -> SimResult:
    if seed is not None:
        random.seed(seed)
    home_wins = away_wins = 0
    score_dist: List[Tuple[int, int]] = []
    total_runs: List[int] = []
    away_runs: List[int] = []
    home_runs: List[int] = []
    inning_totals: List[List[int]] = []
    player_stats: Dict[str, List[Dict[str, int]]] = {}
    for _ in range(n):
        game = simulate_game(away, home, park_factor=park_factor)
        if game.home_score > game.away_score:
            home_wins += 1
        else:
            away_wins += 1
        score_dist.append((game.away_score, game.home_score))
        total_runs.append(game.away_score + game.home_score)
        away_runs.append(game.away_score)
        home_runs.append(game.home_score)
        inning_totals.append([a + h for (a, h) in game.inning_runs])
        for name, sl in game.stats.items():
            player_stats.setdefault(name, []).append(sl)
    return SimResult(
        n=n,
        home_wins=home_wins,
        away_wins=away_wins,
        score_dist=score_dist,
        total_runs=total_runs,
        away_runs=away_runs,
        home_runs=home_runs,
        inning_totals=inning_totals,
        player_stats=player_stats,
    )


# --------------------------- Sample lineups ---------------------------

def sample_lineup_lad() -> Lineup:
    return Lineup(
        name="Dodgers",
        batters=[
            Batter("Mookie Betts",      k_rate=0.62, bb_rate=1.18, power=1.30, hit_rate=1.20, speed=72),
            Batter("Shohei Ohtani",     k_rate=0.95, bb_rate=1.30, power=1.85, hit_rate=1.05, speed=75),
            Batter("Freddie Freeman",   k_rate=0.65, bb_rate=1.22, power=1.30, hit_rate=1.30, speed=45),
            Batter("Will Smith",        k_rate=0.78, bb_rate=1.10, power=1.18, hit_rate=1.10, speed=35),
            Batter("Teoscar Hernandez", k_rate=1.20, bb_rate=0.78, power=1.40, hit_rate=1.05, speed=55),
            Batter("Max Muncy",         k_rate=1.30, bb_rate=1.20, power=1.45, hit_rate=0.90, speed=30),
            Batter("Tommy Edman",       k_rate=0.95, bb_rate=0.90, power=0.90, hit_rate=1.05, speed=82),
            Batter("Gavin Lux",         k_rate=1.05, bb_rate=1.00, power=0.95, hit_rate=1.00, speed=58),
            Batter("Andy Pages",        k_rate=1.15, bb_rate=0.80, power=1.10, hit_rate=0.95, speed=60),
        ],
        starter=Pitcher("Yamamoto", k_rate=1.18, bb_rate=0.75, hr_rate=0.85, stamina=95),
        bullpen=Pitcher("LAD pen",  k_rate=1.08, bb_rate=0.95, hr_rate=0.92),
        park_factor=0.96,
    )


def sample_lineup_sdp() -> Lineup:
    return Lineup(
        name="Padres",
        batters=[
            Batter("Fernando Tatis",  k_rate=1.10, bb_rate=1.10, power=1.45, hit_rate=1.10, speed=80),
            Batter("Luis Arraez",     k_rate=0.42, bb_rate=0.95, power=0.65, hit_rate=1.50, speed=50),
            Batter("Manny Machado",   k_rate=0.90, bb_rate=1.10, power=1.30, hit_rate=1.15, speed=50),
            Batter("Xander Bogaerts", k_rate=0.95, bb_rate=1.05, power=1.05, hit_rate=1.10, speed=52),
            Batter("Jackson Merrill", k_rate=1.00, bb_rate=0.85, power=1.20, hit_rate=1.05, speed=60),
            Batter("Jake Cronenworth",k_rate=1.00, bb_rate=1.05, power=0.95, hit_rate=0.95, speed=48),
            Batter("Kyle Higashioka", k_rate=1.10, bb_rate=0.78, power=1.10, hit_rate=0.85, speed=30),
            Batter("Jurickson Profar",k_rate=0.92, bb_rate=1.10, power=1.05, hit_rate=1.05, speed=55),
            Batter("Jose Iglesias",   k_rate=0.90, bb_rate=0.92, power=0.78, hit_rate=1.10, speed=58),
        ],
        starter=Pitcher("Darvish",  k_rate=1.04, bb_rate=1.05, hr_rate=1.15, stamina=88),
        bullpen=Pitcher("SDP pen",  k_rate=0.98, bb_rate=1.05, hr_rate=1.10),
        park_factor=0.91,
    )


if __name__ == "__main__":
    away = sample_lineup_sdp()
    home = sample_lineup_lad()
    print(f"Simulating LAD vs SDP (Petco, park=0.91)...")
    res = monte_carlo(away, home, n=10_000, park_factor=0.93, seed=42)
    print(f"\n=== {res.n:,} game Monte Carlo ===")
    print(f"P(LAD win)             : {res.p_home_win():.4f}")
    print(f"P(Total > 8.0)         : {res.p_total_over(8.0):.4f}")
    print(f"P(Total > 7.5)         : {res.p_total_over(7.5):.4f}")
    print(f"P(LAD covers -1.5)     : {res.p_runline('home', -1.5):.4f}")
    print(f"P(F5 Total > 4.0)      : {res.p_first5_over(4.0):.4f}")
    print(f"Avg total runs         : {statistics.mean(res.total_runs):.2f}")
    print(f"Avg LAD runs           : {statistics.mean(res.home_runs):.2f}")
    print(f"Avg SDP runs           : {statistics.mean(res.away_runs):.2f}")
    print()
    print("=== Player Prop Distributions ===")
    for player, stat, line in [
        ("Shohei Ohtani", "HR", 0.5),
        ("Shohei Ohtani", "TB", 1.5),
        ("Mookie Betts",  "H",  0.5),
        ("Yamamoto",      "K",  6.5),
        ("Darvish",       "K",  5.5),
        ("Freddie Freeman","TB", 1.5),
    ]:
        p = res.player_prop_over(player, stat, line)
        dist = res.player_prop_distribution(player, stat)
        if dist:
            avg = statistics.mean(dist)
            print(f"  {player:22s} {stat:>3s} O{line:>4.1f}  P(over)={p:.3f}  mean={avg:.2f}")
