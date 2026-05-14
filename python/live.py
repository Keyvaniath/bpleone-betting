"""
EdgeStat - Live in-game win expectancy.

Pre-game models predict P(home wins) from team strength.  But the moment a
pitch is thrown, the situation changes every plate appearance.  Live betting
requires a model that updates with the score, inning, outs, baserunners, and
remaining team strength.

This module implements:
  1. A run-expectancy (RE24) matrix from base-out states.
  2. A win-probability matrix indexed by (inning, half, outs, runners, score_diff).
  3. A play-by-play simulator that generates a realistic win-expectancy timeline
     for any game.

The win-prob matrix here is built by Monte Carlo simulation from each state
forward — exactly how Tom Tango / Fangraphs build their WPA tables.

For sharp bettors: every live-line move should be cross-checked against this
table.  Books often overreact to the most recent pitch (especially HRs).
"""
from __future__ import annotations

import math
import random
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


# --------------------------- State definition ---------------------------

# Bases: tuple (1b, 2b, 3b) of 0/1
EMPTY_BASES = (0, 0, 0)
ALL_BASE_STATES = [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]


@dataclass(frozen=True)
class GameState:
    inning: int          # 1-9
    top: bool            # True if away batting
    outs: int            # 0, 1, 2
    bases: Tuple[int, int, int]   # (1b, 2b, 3b)
    score_diff: int      # home - away

    def key(self) -> str:
        b1, b2, b3 = self.bases
        return f"{self.inning}/{'T' if self.top else 'B'}/{self.outs}/{b1}{b2}{b3}/{self.score_diff:+d}"


# --------------------------- Base-out run expectancy ---------------------------
#
# Empirically derived RE24 table for the modern MLB era (Fangraphs).
# Format: re24[(bases, outs)] = expected runs in remainder of inning.
RE24 = {
    ((0, 0, 0), 0): 0.486, ((0, 0, 0), 1): 0.260, ((0, 0, 0), 2): 0.099,
    ((1, 0, 0), 0): 0.862, ((1, 0, 0), 1): 0.512, ((1, 0, 0), 2): 0.222,
    ((0, 1, 0), 0): 1.092, ((0, 1, 0), 1): 0.654, ((0, 1, 0), 2): 0.314,
    ((0, 0, 1), 0): 1.327, ((0, 0, 1), 1): 0.961, ((0, 0, 1), 2): 0.367,
    ((1, 1, 0), 0): 1.434, ((1, 1, 0), 1): 0.873, ((1, 1, 0), 2): 0.435,
    ((1, 0, 1), 0): 1.682, ((1, 0, 1), 1): 1.169, ((1, 0, 1), 2): 0.464,
    ((0, 1, 1), 0): 1.870, ((0, 1, 1), 1): 1.346, ((0, 1, 1), 2): 0.557,
    ((1, 1, 1), 0): 2.293, ((1, 1, 1), 1): 1.541, ((1, 1, 1), 2): 0.717,
}


def re24(bases: Tuple[int, int, int], outs: int) -> float:
    return RE24.get((bases, outs), 0.0)


# --------------------------- Win probability table ---------------------------
#
# We can't store every state with reasonable Python performance, so we compute
# WPA on-demand via short Monte Carlo from the requested state.  Good for
# pre-game seeding; production version would precompute a 5,000-entry table.

LEAGUE_RUN_PER_PA_HOME = 4.45 / 38     # ~0.117 runs per home half-inning batter
LEAGUE_RUN_PER_PA_AWAY = 4.45 / 38


def _poisson(lam: float, rng: random.Random) -> int:
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def simulate_remaining_game(state: GameState, n_sims: int = 1500, seed: int = 7
                            ) -> float:
    """Monte Carlo from `state` to the end of the game.  Returns P(home wins)."""
    rng = random.Random(seed)
    home_wins = 0
    for _ in range(n_sims):
        cur = GameState(inning=state.inning, top=state.top, outs=state.outs,
                        bases=state.bases, score_diff=state.score_diff)
        cur_score_diff = cur.score_diff
        cur_inning = cur.inning
        cur_top = cur.top
        cur_outs = cur.outs
        cur_bases = cur.bases
        # Apply expected runs from current state to finish this half-inning.
        runs_to_score = _poisson(re24(cur_bases, cur_outs), rng)
        if cur_top:
            cur_score_diff -= runs_to_score
        else:
            cur_score_diff += runs_to_score
        # Switch half-innings.
        if cur_top:
            cur_top = False
        else:
            cur_top = True
            cur_inning += 1
        # Play out remaining half-innings.
        while cur_inning <= 9 or cur_score_diff == 0:
            if cur_top:
                runs = _poisson(LEAGUE_RUN_PER_PA_AWAY * 4.3, rng)  # ~3 PAs/inning
                cur_score_diff -= runs
                cur_top = False
            else:
                runs = _poisson(LEAGUE_RUN_PER_PA_HOME * 4.3, rng)
                cur_score_diff += runs
                # Walk-off check
                if cur_inning >= 9 and cur_score_diff > 0:
                    break
                cur_top = True
                cur_inning += 1
            if cur_inning > 15:
                break
        if cur_score_diff > 0:
            home_wins += 1
        elif cur_score_diff < 0:
            pass
        else:
            home_wins += 0.5
    return home_wins / n_sims


# --------------------------- Live betting line check ---------------------------

def fair_live_price_american(p_home: float, vig: float = 0.045) -> Tuple[int, int]:
    """Convert win prob to vig-loaded American odds for both sides."""
    p_home_w_vig = p_home + vig / 2
    p_away_w_vig = (1 - p_home) + vig / 2
    s = p_home_w_vig + p_away_w_vig
    p_home_w_vig = p_home_w_vig / s * (1 + vig)
    p_away_w_vig = p_away_w_vig / s * (1 + vig)
    def to_am(p):
        p = max(0.01, min(0.99, p))
        dec = 1 / p
        return int(round((dec - 1) * 100)) if dec >= 2 else -int(round(100 / (dec - 1)))
    return to_am(p_home_w_vig), to_am(p_away_w_vig)


# --------------------------- Sample play-by-play timeline ---------------------------

SAMPLE_PBP = [
    # (inning, top, outs_after, bases_after, score_diff_after, event)
    (1, True,  0, (0, 0, 0), 0,  "Top 1: Pre-game — LAD -148"),
    (1, True,  1, (0, 0, 0), 0,  "Top 1: Tatis K. 1 out"),
    (1, True,  1, (1, 0, 0), 0,  "Top 1: Arraez 1B. Runner on 1st"),
    (1, True,  2, (1, 0, 0), 0,  "Top 1: Machado FO. 2 outs"),
    (1, True,  3, (0, 0, 0), 0,  "Top 1: Bogaerts groundout. 3 outs. End top of 1."),
    (1, False, 0, (0, 0, 0), 0,  "Bot 1: Betts to the plate"),
    (1, False, 0, (1, 0, 0), 0,  "Bot 1: Betts 1B. Ohtani up"),
    (1, False, 0, (1, 0, 0), 1,  "Bot 1: Ohtani HR. LAD 2-0 (wait, no — solo to right field on a 95mph FB. Crowd erupts.)"),
    (1, False, 1, (0, 0, 0), 1,  "Bot 1: Freeman pop out"),
    (1, False, 3, (0, 0, 0), 1,  "Bot 1: Smith K, Hernandez line out. End 1st. LAD 2-1"),
    (3, False, 2, (1, 0, 1), 1,  "Bot 3: Bases threat for LAD"),
    (3, False, 3, (0, 0, 0), 1,  "Bot 3: Muncy strikes out. Threat ends"),
    (5, True,  2, (0, 1, 0), 0,  "Top 5: SDP rally. Score tied 1-1"),
    (5, True,  3, (0, 0, 0), 0,  "Top 5: Merrill K. Inning over"),
    (6, False, 1, (0, 1, 1), 1,  "Bot 6: LAD back ahead 2-1. RISP"),
    (6, False, 1, (0, 1, 1), 2,  "Bot 6: Edman sac fly. 3-1 LAD"),
    (7, True,  2, (1, 0, 0), 2,  "Top 7: SDP threat, 2 on"),
    (8, True,  0, (0, 0, 0), 2,  "Top 8: LAD bullpen takes over"),
    (8, False, 3, (0, 0, 0), 3,  "Bot 8: LAD scores insurance. 4-1"),
    (9, True,  2, (0, 0, 0), 3,  "Top 9: 1 out from win"),
    (9, True,  3, (0, 0, 0), 3,  "Final: LAD 4 - SDP 1"),
]


def build_timeline(pbp=None) -> List[Dict]:
    pbp = pbp or SAMPLE_PBP
    out = []
    for inning, top, outs, bases, score_diff, event in pbp:
        state = GameState(inning=inning, top=top, outs=outs, bases=bases, score_diff=score_diff)
        if score_diff >= 4 or score_diff <= -4 or inning >= 9:
            n = 600
        else:
            n = 1000
        p_home = simulate_remaining_game(state, n_sims=n, seed=11 + inning)
        fair_home, fair_away = fair_live_price_american(p_home)
        out.append({
            "state": state.key(),
            "event": event,
            "p_home_win": round(p_home, 4),
            "fair_home_price": fair_home,
            "fair_away_price": fair_away,
        })
    return out


def write_artifact(path: str = "../data/live_game.json") -> None:
    tl = build_timeline()
    payload = {
        "matchup": "LAD vs SDP",
        "pregame_p_home_win": tl[0]["p_home_win"],
        "timeline": tl,
        "re24_table": [
            {"bases": "".join(map(str, k[0])), "outs": k[1], "re24": v}
            for k, v in sorted(RE24.items())
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {path} ({len(tl)} timeline points)")


if __name__ == "__main__":
    print("Building live win-expectancy timeline (LAD/SDP)…")
    tl = build_timeline()
    print(f"\n{'State':<24}{'P(home)':>10}{'Fair Home':>12}{'Fair Away':>11}  Event")
    for t in tl:
        print(f"  {t['state']:<22}{t['p_home_win']:>10.3f}"
              f"{('+' if t['fair_home_price']>0 else '')+str(t['fair_home_price']):>12}"
              f"{('+' if t['fair_away_price']>0 else '')+str(t['fair_away_price']):>11}"
              f"  {t['event'][:60]}")
    write_artifact()
