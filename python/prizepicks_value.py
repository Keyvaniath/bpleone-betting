"""
EdgeStat -- PrizePicks Value Board.

PrizePicks pays FLAT multipliers (2-pick ~3x, 3-pick ~5x, ...), so each leg has a
fixed break-even probability (~0.55-0.585) regardless of the book's juice. That
means a prop is a +EV PrizePicks leg whenever its TRUE hit probability clears that
break-even -- and crucially, several families that LOSE money at a sportsbook's
fair price are still +EV at PrizePicks' soft flat line (the "priced-short" families
from the calibration map: hit unders, K overs, etc.).

This board is only sound because of the calibration stack: the raw PrizePicks model
probabilities are 0/1 extremes (useless on their own). Every prop is therefore:
  1. CALIBRATED -- the raw prob is blended toward its family's realized hit rate
     (prob_calibration.calibrate_play), so we use what actually happens, not a
     0/1 guess.
  2. CURATED -- families the model is provably OVERCONFIDENT on (fake edge at any
     line: total_bases over, rbis over, hrr over, ...) are dropped.
  3. EVIDENCE-GATED -- only props whose family has real settled history are shown;
     no uncalibrated extremes.
A surviving prop's calibrated prob is then compared to the PrizePicks per-leg
break-even. Edge = calibrated_prob - break_even.

Output: data/prizepicks_value.json -> prizepicks-value.html
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from itertools import combinations
from typing import Any, Dict, List

import prob_calibration as pc
import correlations as corr

# Pairwise correlation between two UNDER (or same-side) prop legs, used to price
# the joint hit probability of a Power Play honestly. Same-team legs co-occur
# (one offense shut down -> all its batters' unders hit together); same-game
# opposing legs share the game's run environment; cross-game legs are independent.
RHO_SAME_TEAM = 0.35
RHO_SAME_GAME = 0.18

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PICKEM = os.path.join(DATA_DIR, "pickem.json")
OUT = os.path.join(DATA_DIR, "prizepicks_value.json")

MIN_EDGE = 0.02     # calibrated prob must clear break-even by >= 2pp
MAX_BOARD = 30
DEFAULT_BE = 0.577  # 2-pick PrizePicks break-even if the feed doesn't carry it


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _corr_matrix(combo: List[Dict[str, Any]]) -> List[List[float]]:
    """Pairwise correlation matrix for a same-side (under) Power Play. Positive
    within a team/game because those unders co-occur; 0 across games."""
    n = len(combo)
    m = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = combo[i], combo[j]
            if a.get("team") and a["team"] == b.get("team"):
                rho = RHO_SAME_TEAM
            elif a.get("game") and a["game"] == b.get("game"):
                rho = RHO_SAME_GAME
            else:
                rho = 0.0
            m[i][j] = m[j][i] = rho
    return m


def _build_slates(legs: List[Dict[str, Any]], be_by_legs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best 2/3/4-leg PrizePicks Power Plays, CORRELATION-AWARE. PP is all-or-
    nothing: a $1 N-pick at multiplier M (= (1/break_even)^N) returns joint*M - 1.

    Same-family legs ARE allowed (the user can stack hrr-unders), and the joint
    probability is priced with a Gaussian copula (correlations.py) instead of the
    naive product: legs in the same game/team are positively correlated (a shut-
    down offense makes all its batters' unders hit together), which RAISES the
    joint hit prob above independence -- and the variance too, so the stake stays
    quarter-Kelly capped at 10%. Ranked by expected LOG-GROWTH (the right bankroll
    objective), which trades the higher EV of more legs against their ruin risk."""
    pool = legs[:12]
    slates: List[Dict[str, Any]] = []
    for n in (2, 3, 4):
        be_n = float(be_by_legs.get(str(n)) or DEFAULT_BE)
        if be_n <= 0 or len(pool) < n:
            continue
        mult = (1.0 / be_n) ** n
        b = mult - 1.0
        # Stage 1 (cheap): rank candidate combos by INDEPENDENT joint prob, keep top few.
        cands = []
        for combo in combinations(pool, n):
            if len({c["player"] for c in combo}) < n:   # never two legs on one player
                continue
            jp_ind = 1.0
            for c in combo:
                jp_ind *= c["cal_prob"]
            cands.append((jp_ind, combo))
        cands.sort(key=lambda t: -t[0])
        # Stage 2: refine the top with the correlation-aware copula joint prob.
        refined = []
        for jp_ind, combo in cands[:6]:
            cm = _corr_matrix(list(combo))
            has_corr = any(cm[i][j] > 0 for i in range(n) for j in range(i + 1, n))
            jp = (corr.correlated_parlay_prob([c["cal_prob"] for c in combo], cm, n_sims=12000)
                  if has_corr else jp_ind)
            ev = jp * mult - 1.0
            kelly = max(0.0, ev / b) if b > 0 else 0.0
            f = min(0.10, kelly * 0.25)               # quarter-Kelly, capped 10%
            growth = (jp * math.log(1 + f * b) + (1 - jp) * math.log(max(1e-9, 1 - f))) if f > 0 else 0.0
            teams = {c.get("team") for c in combo}
            games = {c.get("game") for c in combo if c.get("game")}
            n_corr_pairs = sum(1 for i in range(n) for j in range(i + 1, n) if cm[i][j] > 0)
            if len(teams) == 1:
                corr_label = "same-team stack (correlated)"
            elif n_corr_pairs:
                corr_label = f"mixed — {n_corr_pairs} correlated pair(s)"
            else:
                corr_label = "cross-game (independent)"
            refined.append({
                "n_legs": n,
                "payout_multiple": round(mult, 2),
                "joint_prob": round(jp, 4),
                "joint_prob_independent": round(jp_ind, 4),
                "correlation": corr_label,
                "expected_roi_pct": round(100 * ev, 1),
                "kelly_fraction": round(kelly, 3),
                "stake_pct_quarter_kelly": round(100 * f, 1),
                "exp_log_growth": round(growth, 5),
                "legs": [{"player": c["player"], "team": c.get("team"), "game": c.get("game"),
                          "side": c["side"], "line": c["line"], "market": c["market"],
                          "cal_prob": c["cal_prob"]} for c in combo],
            })
        refined.sort(key=lambda x: -x["exp_log_growth"])
        slates.extend(refined[:3])
    slates.sort(key=lambda x: -x["exp_log_growth"])
    return slates


def run() -> Dict[str, Any]:
    pc.reset_caches()
    d = _load(PICKEM)
    props = d.get("props") or []
    be_by_legs = d.get("pp_breakeven_by_legs") or {}
    be = float(be_by_legs.get("2") or DEFAULT_BE)   # 2-pick = standard entry

    board: List[Dict[str, Any]] = []
    n_overconf = n_uncalibrated = 0
    for p in props:
        po, pu = p.get("model_prob_over"), p.get("model_prob_under")
        if po is None and pu is None:
            continue
        side = "OVER" if (po or 0) >= (pu or 0) else "UNDER"
        raw = (po if side == "OVER" else pu) or 0.0
        market, line = p.get("market"), p.get("pp_line")

        # CURATION: drop families the model is provably overconfident on (this side).
        if pc.is_overconfident_play(market, side, line):
            n_overconf += 1
            continue
        cal, meta = pc.calibrate_play(market, side, line, raw)
        if cal is None:
            continue
        # EVIDENCE GATE: only publish props we can calibrate on real outcomes.
        if meta.get("method") != "empirical":
            n_uncalibrated += 1
            continue
        edge = cal - be
        if edge < MIN_EDGE:
            continue
        board.append({
            "player": p.get("player"), "team": p.get("team"),
            "game": p.get("game"),
            "market": market, "stat": p.get("stat_type") or market,
            "side": side, "line": line,
            "cal_prob": round(cal, 4), "raw_prob": round(raw, 4),
            "realized": meta.get("realized"), "cal_n": meta.get("n"),
            "family": meta.get("family"),
            "breakeven": round(be, 4), "edge_pp": round(100 * edge, 1),
        })

    # de-dup one play per player+market+side, and cap each family so the board
    # is DIVERSE (otherwise a single near-lock family -- hrr under 4.5 hits ~96%
    # for every batter -- would fill all 30 slots with the same prop).
    seen, fam_count, deduped = set(), {}, []
    MAX_PER_FAMILY = 4
    for b in sorted(board, key=lambda x: -x["edge_pp"]):
        k = (b["player"], b["market"], b["side"])
        if k in seen:
            continue
        fam = b["family"]
        if fam_count.get(fam, 0) >= MAX_PER_FAMILY:
            continue
        seen.add(k)
        fam_count[fam] = fam_count.get(fam, 0) + 1
        deduped.append(b)
    top = deduped[:MAX_BOARD]
    slates = _build_slates(top, be_by_legs)

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "book": "prizepicks",
        "breakeven_per_leg": round(be, 4),
        "breakeven_by_legs": be_by_legs,
        "n_board": len(top),
        "n_props_scanned": len(props),
        "n_overconfident_dropped": n_overconf,
        "n_uncalibrated_skipped": n_uncalibrated,
        "suggested_slates": slates,
        "best_slate": (slates[0] if slates else None),
        "method_note": "PrizePicks pays flat multipliers, so each leg's break-even is fixed "
                       f"(~{be:.3f} for a 2-pick). A prop is a +EV leg when its CALIBRATED hit "
                       "probability (raw model prob blended toward the family's realized rate) "
                       "clears that break-even. Overconfident families (fake edge at any line) "
                       "are dropped; only props with real settled history are shown.",
        "board": top,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[pp-value] {o['n_board']} +EV PrizePicks legs from {o['n_props_scanned']} props "
          f"(be {o['breakeven_per_leg']}); dropped {o['n_overconfident_dropped']} overconfident, "
          f"skipped {o['n_uncalibrated_skipped']} uncalibrated -> {OUT}")
    for b in o["board"][:8]:
        print(f"    {b['player']:20s} {b['side']:5s} {b['line']} {b['market']:20s} "
              f"cal={b['cal_prob']} (real {b['realized']}, n={b['cal_n']}) edge=+{b['edge_pp']}pp")
