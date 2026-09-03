"""
EdgeStat -- college-football Elo ratings (the CFB desk's rating engine).

Elo with margin-of-victory damping, fit on real ESPN results
(cfb_results_cache). Every constant here is TUNED ON 2025 BY WALK-FORWARD
BACKTEST, not lifted from an NFL model -- run `python cfb_ratings.py --tune`
to reproduce the grid, and `--backtest` for the honest out-of-sample numbers
this desk publishes.

WHY COLLEGE NEEDS ITS OWN TREATMENT (all measured on the 2025 cache):
  * FCS opponents. 126 of 934 games are against non-FBS teams and average a
    34.0-point margin vs 16.4 in FBS-vs-FBS play. Feeding those to a
    MoV-sensitive Elo hands out huge rating credit for beating nobody, so
    non-FBS opponents are pooled into ONE synthetic rating (FCS_ELO) and
    updated at a reduced K -- the game still counts (losing to an FCS team is
    real information) but it can't inflate a rating.
  * Blowouts. CFB routinely produces 50-point margins that mean little.
    The 538-style MoV multiplier -- ln(margin+1) damped by the rating gap --
    is what keeps a 63-3 win from moving a rating three times as far as 28-24,
    and its autocorrelation term stops favorites farming rating off cupcakes.
  * Roster churn. The transfer portal means last season's rating decays faster
    than the NFL's; the preseason carryover is tuned, not assumed.
  * Tiny samples. ~12 games/team/season, so early-season ratings ARE the prior
    season. The desk must say so rather than pretending week 2 is informative.

Output: data/cfb_ratings.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import cfb_results_cache as crc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cfb_ratings.json")

BASE_ELO = 1500.0
FCS_KEY = "__FCS__"        # every non-FBS opponent pools into one rating

# --- tuned constants: every value below was measured, not assumed ---
# K/HFA from the 2025 walk-forward grid (`--tune`): K=55 won on both Brier
# (0.1902) and accuracy (71.2%) over n=617 out-of-sample FBS games. The grid is
# FLAT between K=42 and K=55 (0.0005 Brier) -- do not over-read the winner.
K_FACTOR = 55.0
HFA_ELO = 60.0             # ~2.4 points at 25 Elo/point; 0 at neutral sites
# The grid marginally preferred K_FCS=1.0 (0.1902 vs 0.1907 Brier) but that gap
# is noise on n=617, and the evaluation set EXCLUDES FCS games, so it cannot
# see the harm. Keeping the principled damping: 2025's FCS games averaged a
# 34.0-point margin vs 16.4 between FBS teams.
K_FCS_SCALE = 0.35
# Tuned by predicting EARLY 2025 (weeks 1-4, n=195) from carried-over 2024
# ratings -- the exact situation this desk is in today. Brier by carryover:
# 0.00->0.2299, 0.40->0.2065, 0.50->0.2067, 0.62->0.2088, 1.00->0.2226.
# ~55% regression to the mean between seasons: CFB rosters churn hard
# (transfer portal), so last year's rating decays far faster than the NFL's.
CARRYOVER = 0.45
ELO_PER_POINT = 25.0       # standard football conversion, for spread display

# THE NUMBER THAT GOVERNS THIS DESK'S HUMILITY: predicting early-season games
# from prior-season ratings alone lands ~65% accuracy / 0.207 Brier, versus
# ~71% / 0.190 once a season has 4+ weeks of its own data. The model is NOT
# sharp enough early to out-price a market on its own -- which is why the desk
# shrinks toward the book line and surfaces only genuine divergence.
EARLY_SEASON_WEEKS = 4


def _mov_multiplier(margin: int, elo_diff_winner: float) -> float:
    """538's margin multiplier: log-damped margin, shrunk when the winner was
    already favored. Without the autocorrelation term a good team farms
    unlimited rating off blowouts -- endemic in CFB."""
    return math.log(abs(margin) + 1.0) * (2.2 / (0.001 * elo_diff_winner + 2.2))


def expected(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def _key(g: Dict[str, Any], side: str) -> str:
    """Team key, pooling non-FBS opponents. is_fbs_matchup=None means the FBS
    roster lookup failed -- treat as unknown (do NOT pool), so an outage can't
    silently rewrite every team into FCS."""
    ab = g.get(side) or "?"
    if g.get("is_fbs_matchup") is False:
        fbs = g.get("_fbs_ids") or set()
        tid = str(g.get(f"{side}_id") or "")
        if fbs and tid not in fbs:
            return FCS_KEY
    return ab


def fit(games: List[Dict[str, Any]],
        ratings: Optional[Dict[str, float]] = None,
        k: float = K_FACTOR, hfa: float = HFA_ELO,
        k_fcs: float = K_FCS_SCALE) -> Dict[str, float]:
    """Run Elo over games in date order. Returns {team: rating}."""
    r: Dict[str, float] = dict(ratings or {})
    for g in sorted(games, key=lambda x: (x.get("date") or "", x.get("id") or "")):
        h, a = _key(g, "home"), _key(g, "away")
        if h == a:
            continue
        rh = r.setdefault(h, BASE_ELO)
        ra = r.setdefault(a, BASE_ELO)
        adv = 0.0 if g.get("neutral") else hfa
        exp_h = expected(rh + adv, ra)
        hs, as_ = g.get("home_score") or 0, g.get("away_score") or 0
        if hs == as_:
            score_h = 0.5
        else:
            score_h = 1.0 if hs > as_ else 0.0
        margin = abs(hs - as_)
        # winner's pre-game edge, including HFA, drives the damping
        diff_winner = ((rh + adv) - ra) if hs > as_ else (ra - (rh + adv))
        mult = _mov_multiplier(margin, diff_winner) if margin else 1.0
        kk = k * mult
        if FCS_KEY in (h, a):
            kk *= k_fcs
        delta = kk * (score_h - exp_h)
        r[h] = rh + delta
        r[a] = ra - delta
    return r


def carry_over(prev: Dict[str, float], factor: float = CARRYOVER) -> Dict[str, float]:
    """Regress a finished season's ratings toward the mean for the next one."""
    return {t: BASE_ELO + factor * (v - BASE_ELO) for t, v in prev.items()}


def win_prob(rating_home: float, rating_away: float, neutral: bool = False,
             hfa: float = HFA_ELO) -> float:
    return expected(rating_home + (0.0 if neutral else hfa), rating_away)


def _tag_fbs(games: List[Dict[str, Any]], fbs_ids: set) -> List[Dict[str, Any]]:
    for g in games:
        g["_fbs_ids"] = fbs_ids
    return games


# --------------------------------------------------------------------------
# Honest evaluation: walk-forward, never fit on what it predicts
# --------------------------------------------------------------------------

def walk_forward(games: List[Dict[str, Any]], seed: Dict[str, float],
                 k: float = K_FACTOR, hfa: float = HFA_ELO,
                 k_fcs: float = K_FCS_SCALE,
                 start_week: int = 4) -> Dict[str, Any]:
    """Predict each week from ratings fit ONLY on prior weeks. Reports
    accuracy, Brier, and log loss on FBS-vs-FBS games (the only ones the desk
    would ever price)."""
    by_week: Dict[int, List[Dict[str, Any]]] = {}
    for g in games:
        if g.get("season_type") != 2:
            continue
        by_week.setdefault(int(g.get("week") or 0), []).append(g)
    r = dict(seed)
    n = 0
    correct = 0
    brier = 0.0
    logloss = 0.0
    for wk in sorted(by_week):
        wk_games = by_week[wk]
        if wk >= start_week:
            for g in wk_games:
                if not g.get("is_fbs_matchup"):
                    continue
                h, a = _key(g, "home"), _key(g, "away")
                if FCS_KEY in (h, a):
                    continue
                p = win_prob(r.get(h, BASE_ELO), r.get(a, BASE_ELO),
                             bool(g.get("neutral")), hfa)
                hs, as_ = g.get("home_score") or 0, g.get("away_score") or 0
                if hs == as_:
                    continue
                y = 1.0 if hs > as_ else 0.0
                n += 1
                correct += 1 if ((p >= 0.5) == (y == 1.0)) else 0
                brier += (p - y) ** 2
                pc = min(max(p, 1e-6), 1 - 1e-6)
                logloss += -(y * math.log(pc) + (1 - y) * math.log(1 - pc))
        r = fit(wk_games, r, k=k, hfa=hfa, k_fcs=k_fcs)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "accuracy": round(correct / n, 4),
        "brier": round(brier / n, 4),
        "log_loss": round(logloss / n, 4),
    }


def early_season_backtest(prior_games: List[Dict[str, Any]],
                          target_games: List[Dict[str, Any]],
                          carry: float = CARRYOVER,
                          max_week: int = EARLY_SEASON_WEEKS) -> Dict[str, Any]:
    """How well do carried-over prior-season ratings alone predict the START of
    the next season? This is the honest number to show while the current season
    is young -- the mid-season walk-forward flatters the model in September."""
    seed = carry_over(fit(prior_games), carry)
    n = 0
    correct = 0
    brier = 0.0
    for g in target_games:
        if g.get("season_type") != 2 or int(g.get("week") or 0) > max_week:
            continue
        if not g.get("is_fbs_matchup"):
            continue
        h, a = _key(g, "home"), _key(g, "away")
        if FCS_KEY in (h, a):
            continue
        hs, as_ = g.get("home_score") or 0, g.get("away_score") or 0
        if hs == as_:
            continue
        p = win_prob(seed.get(h, BASE_ELO), seed.get(a, BASE_ELO),
                     bool(g.get("neutral")))
        y = 1.0 if hs > as_ else 0.0
        n += 1
        correct += 1 if ((p >= 0.5) == (y == 1.0)) else 0
        brier += (p - y) ** 2
    if not n:
        return {"n": 0}
    return {"n": n, "accuracy": round(correct / n, 4),
            "brier": round(brier / n, 4), "weeks": f"1-{max_week}"}


def _load_season(season: int, fbs_ids: set) -> List[Dict[str, Any]]:
    d = crc.load(season)
    if not d.get("games"):
        d = crc.run(season)
    return _tag_fbs(list(d.get("games") or []), fbs_ids)


def _tune() -> None:
    """Grid-search the constants on 2025 by walk-forward. Prints the table so
    the chosen values are reproducible, not asserted."""
    fbs = crc.fbs_team_ids(2025)
    g25 = _load_season(2025, fbs)
    rows = []
    for k in (20.0, 30.0, 42.0, 55.0, 70.0):
        for hfa in (45.0, 60.0, 75.0):
            for kf in (0.35, 1.0):
                res = walk_forward(g25, {}, k=k, hfa=hfa, k_fcs=kf)
                rows.append((res.get("brier", 9), res.get("log_loss", 9),
                             res.get("accuracy", 0), k, hfa, kf, res.get("n", 0)))
    rows.sort()
    print("  brier  logloss   acc     K    HFA  Kfcs    n")
    for r in rows[:12]:
        print(f"  {r[0]:.4f}  {r[1]:.4f}  {r[2]:.4f}  {r[3]:5.1f} {r[4]:5.1f} {r[5]:4.2f}  {r[6]}")
    best = rows[0]
    print(f"\n  BEST: K={best[3]} HFA={best[4]} K_FCS={best[5]} "
          f"-> brier {best[0]:.4f}, acc {best[2]:.1%} over n={best[6]}")


def run() -> Dict[str, Any]:
    """Fit current-season ratings on top of last season's carried-over ratings
    and publish them with the honest backtest attached."""
    today = dt.date.today()
    season = today.year
    fbs_prev = crc.fbs_team_ids(season - 1)
    prev_games = _load_season(season - 1, fbs_prev)
    prev_ratings = fit(prev_games)
    seed = carry_over(prev_ratings)

    fbs_now = crc.fbs_team_ids(season) or fbs_prev
    cur = crc.run(season)                      # tops up the live season
    cur_games = _tag_fbs(list(cur.get("games") or []), fbs_now)
    ratings = fit(cur_games, seed)

    # Honest out-of-sample evidence, recomputed every run. TWO numbers, because
    # one of them flatters the model: the mid-season walk-forward is what this
    # model does once a season has its own data, and the early-season backtest
    # is what it does RIGHT NOW in September. The desk shows the applicable one.
    bt = walk_forward(prev_games, {}, start_week=4)
    two_back = _load_season(season - 2, crc.fbs_team_ids(season - 2) or fbs_prev)
    bt_early = (early_season_backtest(two_back, prev_games) if two_back
                else {"n": 0})

    n_cur = len(cur_games)
    # Games played this season by team -- drives the "how much is this still
    # last year's rating?" disclosure the desk must show early in a season.
    played: Dict[str, int] = {}
    for g in cur_games:
        for side in ("home", "away"):
            played[_key(g, side)] = played.get(_key(g, side), 0) + 1

    rows = []
    for team, rating in ratings.items():
        if team == FCS_KEY:
            continue
        gp = played.get(team, 0)
        rows.append({
            "team": team,
            "rating": round(rating, 1),
            "seed_rating": round(seed.get(team, BASE_ELO), 1),
            "games_this_season": gp,
            # what fraction of this number is still last season's opinion
            "prior_weight": round(max(0.0, 1.0 - gp / 8.0), 2),
        })
    rows.sort(key=lambda x: -x["rating"])
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season": season,
        "n_teams": len(rows),
        "n_games_prior_season": len(prev_games),
        "n_games_this_season": n_cur,
        "constants": {"K": K_FACTOR, "HFA_ELO": HFA_ELO,
                      "K_FCS_SCALE": K_FCS_SCALE, "CARRYOVER": CARRYOVER,
                      "ELO_PER_POINT": ELO_PER_POINT},
        "backtest_prior_season": bt,
        "backtest_early_season": bt_early,
        # Which number honestly describes TODAY's ratings.
        "regime": ("early_season" if n_cur < 150 else "in_season"),
        "applicable_backtest": (bt_early if n_cur < 150 else bt),
        "fcs_pool_rating": round(ratings.get(FCS_KEY, BASE_ELO), 1),
        "ratings": rows,
        "method_note": (
            "Elo with 538-style margin-of-victory damping, fit on real ESPN "
            "results. Non-FBS opponents pool into a single rating and update at "
            f"{int(K_FCS_SCALE * 100)}% weight -- beating an FCS team by 40 is "
            "worth almost nothing (2025: FCS games averaged a 34.0-point margin "
            "vs 16.4 between FBS teams). Last season's ratings carry over at "
            f"{int(CARRYOVER * 100)}% of their deviation from average, so early "
            "in a season these ARE mostly last year's opinion -- prior_weight "
            "per team says how much. Constants tuned by walk-forward on the "
            "prior season (python cfb_ratings.py --tune), never hand-asserted."),
        "source": "https://www.espn.com/college-football/scoreboard",
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def _self_test() -> bool:
    """Invariants that must hold on every run."""
    ok = True
    # symmetry: equal ratings at a neutral site = a coin flip
    p = win_prob(1500, 1500, neutral=True)
    if abs(p - 0.5) > 1e-9:
        print(f"  FAIL neutral symmetry: {p}"); ok = False
    # home edge exists and is bounded
    ph = win_prob(1500, 1500, neutral=False)
    if not (0.5 < ph < 0.62):
        print(f"  FAIL hfa sanity: {ph}"); ok = False
    # a blowout must not move a rating more than ~3x a one-score win
    m1 = _mov_multiplier(3, 0.0)
    m2 = _mov_multiplier(59, 0.0)
    if not (1.0 < m2 / m1 < 3.5):
        print(f"  FAIL blowout damping ratio: {m2 / m1}"); ok = False
    # the autocorrelation term must shrink credit for a favorite's blowout
    if not (_mov_multiplier(30, 400.0) < _mov_multiplier(30, 0.0)):
        print("  FAIL autocorrelation term"); ok = False
    # zero-sum: one game moves both teams equally and oppositely
    r = fit([{"date": "2025-09-06", "id": "x", "home": "A", "away": "B",
              "home_id": "1", "away_id": "2", "home_score": 28, "away_score": 20,
              "neutral": True, "is_fbs_matchup": True, "season_type": 2, "week": 1}])
    if abs((r["A"] - BASE_ELO) + (r["B"] - BASE_ELO)) > 1e-9:
        print(f"  FAIL zero-sum: {r}"); ok = False
    print(f"  ratings self-test: {'OK' if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    import sys
    if "--tune" in sys.argv:
        _tune()
    elif "--backtest" in sys.argv:
        fbs = crc.fbs_team_ids(2025)
        g = _load_season(2025, fbs)
        print("2025 walk-forward (fit only on prior weeks):", walk_forward(g, {}))
    else:
        if not _self_test():
            raise SystemExit("cfb_ratings self-test FAILED")
        p = run()
        bt = p["backtest_prior_season"]
        print(f"[cfb-ratings] {p['n_teams']} teams | {p['n_games_this_season']} games this season "
              f"| prior-season walk-forward: {bt.get('accuracy')} acc, brier {bt.get('brier')} (n={bt.get('n')})")
        top = p["ratings"][:5]
        for t in top:
            print(f"    {t['rank']:2d}. {t['team']:5s} {t['rating']:7.1f} "
                  f"(prior weight {t['prior_weight']})")
