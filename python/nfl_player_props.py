"""
EdgeStat -- NFL player-prop projections (the model side for football).

Closes the football loop: GENERATE -> settle -> learn. The grader
(all_picks_tracker._grade_nfl_pick) and the box-score feed (espn_box_logs nfl)
are already live; this is what produces the picks they grade. Model-conviction
(odds-independent), the same shape as the cross-sport Model Conviction board:
for each player on today's NFL slate we project a per-game distribution and
surface the standard line the model is most confident over/under.

Markets: passing yards/completions/TDs/INTs, rushing yards, receiving yards,
receptions, longest reception, longest rush, and anytime touchdown.

Pricing is a play-level Monte Carlo (nfl_simulator) -- NOT a normal-CDF. For each
player we build a role profile (attempts/carries/targets, completion/catch rate,
yards-per-event, TD/INT rates), apply the opponent-defense factor to the yardage
means, simulate SIM_N games, and read each market's probability straight off the
empirical sample:
  counts ~ NegBinomial(mean, VMR)   per-event yards ~ Gamma(mean, CV)
  completions/catches ~ Binomial    TD/INT ~ Poisson
This is backtested better-calibrated than the prior Gaussian (ECE 0.027 vs 0.046
on 21.8k 2025 prediction-outcome pairs) and unlocks the skewed/extreme markets a
single Normal can't price -- longest reception/rush (a max statistic) and exact
2+ TD / 1+ INT counts. See nfl_simulator.py + NFL_SIMULATOR_AUDIT.md.

Player bases are 2025 per-game numbers (refreshed in-season from
nfl_player_gamelogs.json when present). Off-season the slate is empty -> 0 picks;
it auto-activates Week 1. Output: data/nfl_player_props.json.
"""
from __future__ import annotations

import os
import json
import math
import re
import datetime as dt
from typing import Any, Dict, List, Optional

import nfl_simulator as _SIM   # play-level Monte Carlo (backtested vs normal-CDF)
import nfl_baselines as nb     # shared roster/2025-baseline resolution (2026-08-13)


def _nz(v, d):
    """None-safe default (2026-10-26): `.get(k, d)` only covers a MISSING key;
    a key stored as None still reaches the arithmetic and crashes."""
    return d if v is None else v

SIM_N = 4000        # simulations per curated-DB player per slate
SIM_N_WIDE = 2000   # simulations for the widened (2025-baseline) universe
NFL_2026_WEEK1 = "2026-09-08"   # the picks gate holds until this date regardless
                                 # of what ESPN's season label says (it flips to
                                 # "off-season" between preseason weeks)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nfl_player_props.json")

# 2025 per-game bases. qb: pass_yds, pass_td. rb/wr: rush_yds/rec_yds, rec,
# td_rate (rush+rec TD per game). Refreshed in-season from the gamelogs.
NFL_PLAYER_DB: Dict[str, Dict[str, Any]] = {
    # Quarterbacks
    "patrick mahomes":   {"team": "KC",  "pos": "QB", "pass_yds": 265, "pass_td": 1.9},
    "josh allen":        {"team": "BUF", "pos": "QB", "pass_yds": 245, "pass_td": 2.0, "rush_yds": 35, "td_rate": 0.5},
    "joe burrow":        {"team": "CIN", "pos": "QB", "pass_yds": 285, "pass_td": 2.1},
    "lamar jackson":     {"team": "BAL", "pos": "QB", "pass_yds": 215, "pass_td": 1.8, "rush_yds": 55, "td_rate": 0.4},
    "jalen hurts":       {"team": "PHI", "pos": "QB", "pass_yds": 215, "pass_td": 1.5, "rush_yds": 40, "td_rate": 0.7},
    "dak prescott":      {"team": "DAL", "pos": "QB", "pass_yds": 265, "pass_td": 1.8},
    "jared goff":        {"team": "DET", "pos": "QB", "pass_yds": 250, "pass_td": 1.9},
    "jordan love":       {"team": "GB",  "pos": "QB", "pass_yds": 235, "pass_td": 1.7},
    "c.j. stroud":       {"team": "HOU", "pos": "QB", "pass_yds": 240, "pass_td": 1.5},
    "brock purdy":       {"team": "SF",  "pos": "QB", "pass_yds": 255, "pass_td": 1.8},
    "justin herbert":    {"team": "LAC", "pos": "QB", "pass_yds": 250, "pass_td": 1.6},
    "jayden daniels":    {"team": "WSH", "pos": "QB", "pass_yds": 225, "pass_td": 1.4, "rush_yds": 45, "td_rate": 0.5},
    # Running backs
    "saquon barkley":    {"team": "PHI", "pos": "RB", "rush_yds": 100, "rec_yds": 18, "rec": 2.0, "td_rate": 0.8},
    "bijan robinson":    {"team": "ATL", "pos": "RB", "rush_yds": 85,  "rec_yds": 25, "rec": 3.0, "td_rate": 0.6},
    "derrick henry":     {"team": "BAL", "pos": "RB", "rush_yds": 95,  "rec_yds": 8,  "rec": 1.0, "td_rate": 0.8},
    "jahmyr gibbs":      {"team": "DET", "pos": "RB", "rush_yds": 78,  "rec_yds": 22, "rec": 2.5, "td_rate": 0.8},
    "christian mccaffrey": {"team": "SF","pos": "RB", "rush_yds": 80,  "rec_yds": 35, "rec": 4.0, "td_rate": 0.7},
    "josh jacobs":       {"team": "GB",  "pos": "RB", "rush_yds": 78,  "rec_yds": 15, "rec": 2.0, "td_rate": 0.7},
    "kyren williams":    {"team": "LAR", "pos": "RB", "rush_yds": 80,  "rec_yds": 12, "rec": 1.5, "td_rate": 0.7},
    # Wide receivers / TE
    "justin jefferson":  {"team": "MIN", "pos": "WR", "rec_yds": 95, "rec": 6.5, "td_rate": 0.5},
    "ja'marr chase":     {"team": "CIN", "pos": "WR", "rec_yds": 95, "rec": 7.0, "td_rate": 0.6},
    "ceedee lamb":       {"team": "DAL", "pos": "WR", "rec_yds": 88, "rec": 7.0, "td_rate": 0.5},
    "amon-ra st. brown": {"team": "DET", "pos": "WR", "rec_yds": 85, "rec": 7.5, "td_rate": 0.5},
    "tyreek hill":       {"team": "MIA", "pos": "WR", "rec_yds": 82, "rec": 6.0, "td_rate": 0.4},
    "a.j. brown":        {"team": "PHI", "pos": "WR", "rec_yds": 82, "rec": 5.5, "td_rate": 0.5},
    "nico collins":      {"team": "HOU", "pos": "WR", "rec_yds": 80, "rec": 6.0, "td_rate": 0.4},
    "drake london":      {"team": "ATL", "pos": "WR", "rec_yds": 78, "rec": 6.5, "td_rate": 0.4},
    "brock bowers":      {"team": "LV",  "pos": "TE", "rec_yds": 72, "rec": 6.0, "td_rate": 0.4},
}

# ESPN nfl_state team-name -> abbrev (full team names from the scoreboard).
TEAM_FULL = {
    "kansas city chiefs": "KC", "buffalo bills": "BUF", "cincinnati bengals": "CIN",
    "baltimore ravens": "BAL", "philadelphia eagles": "PHI", "dallas cowboys": "DAL",
    "detroit lions": "DET", "green bay packers": "GB", "houston texans": "HOU",
    "san francisco 49ers": "SF", "los angeles chargers": "LAC", "washington commanders": "WSH",
    "atlanta falcons": "ATL", "minnesota vikings": "MIN", "miami dolphins": "MIA",
    "los angeles rams": "LAR", "las vegas raiders": "LV",
}

# Standard book lines per stat (the model picks the one it's most confident on).
STD_LINES = {
    "pass_yds": [199.5, 224.5, 249.5, 274.5, 299.5],
    "rush_yds": [39.5, 49.5, 59.5, 69.5, 79.5, 89.5],
    "rec_yds":  [39.5, 49.5, 59.5, 69.5, 79.5],
    "rec":      [2.5, 3.5, 4.5, 5.5, 6.5, 7.5],
    "pass_cmp": [17.5, 19.5, 21.5, 23.5, 25.5],
    "longest_reception": [19.5, 24.5, 29.5, 34.5],
    "longest_rush": [12.5, 16.5, 19.5, 24.5],
}
# sigma = max(floor, cv x mean) per stat (game-to-game variance).
SIGMA = {"pass_yds": (45.0, 0.28), "rush_yds": (18.0, 0.45),
         "rec_yds": (18.0, 0.55), "rec": (1.4, 0.35)}

# Only project games kicking off within this many days. Keeps us from generating
# props for the next season's schedule ESPN serves all off-season (Week 1 shows
# up months ahead). One NFL week's slate fits comfortably inside this window.
HORIZON_DAYS = 8

# Opponent-defense priors (2025): factor applied to the OPPONENT's offensive
# projection. >1.0 = generous defense (boost the offense); <1.0 = stingy. Two
# facets -- pass defense (drives pass/rec yds + pass TD) and rush defense. These
# are seasonal priors; the in-season build refreshes them from yards-allowed.
PASS_DEF = {
    "BAL": 0.90, "DEN": 0.88, "HOU": 0.92, "MIN": 0.93, "PHI": 0.94, "GB": 0.95,
    "KC": 0.96, "BUF": 0.97, "PIT": 0.95, "LAC": 0.96, "DET": 1.02, "SF": 0.98,
    "NYJ": 0.94, "CLE": 0.97, "SEA": 1.01, "TB": 1.03, "WSH": 1.05, "DAL": 1.06,
    "CAR": 1.10, "CIN": 1.07, "ATL": 1.05, "JAX": 1.06, "MIA": 1.04, "NO": 1.02,
    "LV": 1.06, "TEN": 1.05, "IND": 1.04, "NYG": 1.02, "ARI": 1.03, "CHI": 1.00,
    "NE": 1.03, "LAR": 1.01,
}
RUSH_DEF = {
    "MIN": 0.90, "PHI": 0.91, "DEN": 0.93, "BAL": 0.95, "HOU": 0.96, "KC": 0.97,
    "BUF": 0.98, "GB": 0.96, "PIT": 0.94, "SF": 0.97, "DET": 0.99, "LAC": 0.98,
    "CLE": 0.96, "TB": 1.02, "NYJ": 0.99, "SEA": 1.04, "WSH": 1.03, "DAL": 1.08,
    "CAR": 1.09, "CIN": 1.05, "ATL": 1.02, "JAX": 1.06, "MIA": 1.04, "NO": 1.01,
    "LV": 1.07, "TEN": 1.03, "IND": 1.04, "NYG": 1.05, "ARI": 1.02, "CHI": 0.99,
    "NE": 1.06, "LAR": 1.02,
}
# Dampen the raw factor so a single matchup doesn't swing the projection wildly.
_DEF_DAMP = 0.6


def _opp_factor(table: Dict[str, float], opp: str) -> float:
    raw = _nz(table.get(opp), 1.0)
    return 1.0 + _DEF_DAMP * (raw - 1.0)


# FORM RULE v2 (2026-10-23). v1 put a FLAT 65% on "recent form" = the mean of
# whatever nfl_player_gamelogs held -- an ~8-day box window, i.e. ONE NFL game
# -- and took volume (attempts/carries/targets) from that one game outright.
# Projections swung 10+ DK points between runs an hour apart (Golden 15.8 ->
# 27.1, Coker 11.6 -> 22.1) and the optimizer seated whoever had just had a
# big week. v2: recent = the SEASON-TO-DATE regular-season mean, trusted by
# sample size, w = n/(n+FORM_K), for yardage AND volume. Walk-forward over
# Weeks 2-6 (n=986 player-games, same players both rules): MAE 6.12 -> 5.76,
# corr with actual 0.483 -> 0.545, top-20%-projected bias -3.14 -> -0.78.
# K grid 2/4/8/16 all beat v1; 2 was best. Needs the season-long box file
# (espn_box_logs retains NFL rows -- see CFG_NFL retain_days).
FORM_K = 2.0


_NORM_IDX: Dict[int, Dict[str, Any]] = {}


def _norm_lookup(gamelogs_by_name, name):
    idx = _NORM_IDX.get(id(gamelogs_by_name))
    if idx is None:
        idx = {nb.norm_name(k): v for k, v in gamelogs_by_name.items()}
        _NORM_IDX.clear()
        _NORM_IDX[id(gamelogs_by_name)] = idx
    return idx.get(nb.norm_name(name))


def _form_w(n: int) -> float:
    return n / (n + FORM_K) if n else 0.0


def _blend(recent: Optional[float], season: float, n: int = 0) -> float:
    """Season prior <- season-to-date form, weighted by how many games back it."""
    if recent is None or not n:
        return season
    w = _form_w(n)
    return round(w * recent + (1 - w) * season, 2)


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _abbr(name: str) -> str:
    if not name: return ""
    return TEAM_FULL.get(name.lower().strip(), name[:3].upper())


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.02 or p >= 0.98: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _form_rows(gamelogs_by_name, name):
    """This player's REGULAR-SEASON box rows before today. Looked up by the raw
    key, then by the normalized name (box keys keep punctuation -- 'amon-ra st.
    brown' -- while the desk keys 'amonra st brown'; v1 silently gave those
    players no form at all)."""
    prec = gamelogs_by_name.get(name) or _norm_lookup(gamelogs_by_name, name)
    rows = prec if isinstance(prec, list) else ((prec or {}).get("games") or [])
    today = dt.date.today().isoformat()
    return [g for g in rows if NFL_2026_WEEK1 <= str(g.get("date") or "")[:10] < today]


def _recent_base(gamelogs_by_name, name, field):
    """Season-to-date mean of `field` over regular-season games (else None)."""
    vals = [g.get(field) for g in _form_rows(gamelogs_by_name, name) if g.get(field) is not None]
    return sum(vals) / len(vals) if vals else None


def _form_n(gamelogs_by_name, name) -> int:
    return len(_form_rows(gamelogs_by_name, name))


def _vol(gamelogs_by_name, name, field, prior: float) -> float:
    """Volume (attempts/carries/targets) blended with its season prior by the
    same sample-size weight -- v1 took one game's volume outright."""
    recent = _recent_base(gamelogs_by_name, name, field)
    return _blend(recent, prior, _form_n(gamelogs_by_name, name))


def _best_line(mean, sigma, stat, prefix):
    """Pick the standard line the model is most confident on (playable band)."""
    best = None
    for line in STD_LINES[stat]:
        z = (mean - line) / sigma
        p_over = _norm_cdf(z)
        side, p = ("OVER", p_over) if p_over >= 0.5 else ("UNDER", 1 - p_over)
        if not (0.58 <= p <= 0.80):       # real lean, not a coin flip or a lock
            continue
        if best is None or p > best["p"]:
            best = {"market": f"{prefix}_{side}_{line}", "p": round(p, 3),
                    "fair_odds": _american(p), "line": line, "side": side}
    return best


def _sim_player(name: str, info: Dict[str, Any], gl: Dict[str, Any],
                pass_f: float, rush_f: float, seed: int,
                n: int = SIM_N) -> Dict[str, List[float]]:
    """Build the player's role profile(s) from the DB + recent gamelogs, apply the
    opponent factors to the yardage means, and Monte-Carlo simulate. Returns a
    merged {stat -> samples}."""
    out: Dict[str, List[float]] = {}
    nf = _form_n(gl, name)
    if info.get("pass_yds"):
        att = _vol(gl, name, "pass_att", 33.0)
        cmp_r, att_r = _recent_base(gl, name, "pass_cmp"), _recent_base(gl, name, "pass_att")
        comp_pct = (cmp_r / att_r) if (cmp_r and att_r) else 0.64   # season-to-date ratio
        exp_yds = _blend(_recent_base(gl, name, "pass_yds"), info["pass_yds"], nf) * pass_f
        prof = {"att": att, "comp_pct": comp_pct,
                "ypc": exp_yds / max(1.0, att * comp_pct),
                "pass_td_pg": (info.get("pass_td") or 1.6) * pass_f,
                "int_pg": _recent_base(gl, name, "pass_int") or 0.7}
        out.update(_SIM.simulate_qb(prof, n=n, seed=seed))
    if info.get("rush_yds"):
        car = _vol(gl, name, "rush_att", max(6.0, info["rush_yds"] / 4.3))
        exp_yds = _blend(_recent_base(gl, name, "rush_yds"), info["rush_yds"], nf) * rush_f
        prof = {"carries": car, "ypc_rush": exp_yds / max(1.0, car),
                "rush_td_pg": (_nz(info.get("td_rate"), 0.4)) * (0.7 if info.get("rec_yds") else 1.0)}
        out.update(_SIM.simulate_rusher(prof, n=n, seed=seed + 1))
    if info.get("rec_yds"):
        recm = info.get("rec") or 5
        tgt = _vol(gl, name, "targets", max(3.0, recm / 0.65))
        exp_yds = _blend(_recent_base(gl, name, "rec_yds"), info["rec_yds"], nf) * pass_f
        prof = {"targets": tgt, "catch_rate": min(0.9, recm / tgt if tgt else 0.64),
                "ypr": exp_yds / max(1.0, recm),
                "rec_td_pg": (_nz(info.get("td_rate"), 0.4)) * (0.3 if info.get("rush_yds") else 1.0)}
        out.update(_SIM.simulate_receiver(prof, n=n, seed=seed + 2))
    return out


def dk_points_from_sims(sims: Dict[str, List[float]], n: int) -> List[float]:
    """DK Classic fantasy points PER SIMULATION (full PPR, 4pt pass TD, 100/300-yd
    bonuses applied on each sim so they land on the tail games). Shared with the
    DFS desk (nfl_dfs imports this)."""
    z = [0.0] * n
    py = sims.get("pass_yds") or z
    ptd = sims.get("pass_td") or z
    pint = sims.get("pass_int") or z
    ry = sims.get("rush_yds") or z
    rtd = sims.get("rush_td") or z
    rec = sims.get("rec") or z
    recy = sims.get("rec_yds") or z
    rectd = sims.get("rec_td") or z
    out = []
    for i in range(n):
        fp = (0.04 * py[i] + 4.0 * ptd[i] - 1.0 * pint[i] + (3.0 if py[i] >= 300 else 0.0)
              + 0.10 * ry[i] + 6.0 * rtd[i] + (3.0 if ry[i] >= 100 else 0.0)
              + 1.00 * rec[i] + 0.10 * recy[i] + 6.0 * rectd[i] + (3.0 if recy[i] >= 100 else 0.0))
        out.append(fp)
    return out


def _q(sorted_xs: List[float], q: float) -> float:
    i = min(len(sorted_xs) - 1, max(0, int(q * len(sorted_xs))))
    return sorted_xs[i]


def _detail_from_sims(sims: Dict[str, List[float]]) -> Dict[str, Any]:
    """Full per-market distribution detail for one player: mean/median/p10/p90
    per stat + P(over) at every standard line + TD/INT specials + DK points."""
    detail: Dict[str, Any] = {"markets": {}}
    n = len(next(iter(sims.values()))) if sims else 0
    if not n:
        return detail
    for field, lines in STD_LINES.items():
        samples = sims.get(field)
        if not samples:
            continue
        xs = sorted(samples)
        detail["markets"][field] = {
            "mean": round(sum(xs) / n, 2),
            "median": round(_q(xs, 0.50), 1),
            "p10": round(_q(xs, 0.10), 1),
            "p90": round(_q(xs, 0.90), 1),
            "lines": {str(ln): round(_SIM.prob_over(samples, ln), 3) for ln in lines},
        }
    if sims.get("pass_td"):
        detail["markets"]["pass_td"] = {
            "mean": round(sum(sims["pass_td"]) / n, 2),
            "lines": {"1.5": round(_SIM.prob_over(sims["pass_td"], 1.5), 3),
                      "2.5": round(_SIM.prob_over(sims["pass_td"], 2.5), 3)}}
    if sims.get("pass_int"):
        detail["markets"]["pass_int"] = {
            "mean": round(sum(sims["pass_int"]) / n, 2),
            "lines": {"0.5": round(_SIM.prob_at_least(sims["pass_int"], 1), 3)}}
    rt, ct = sims.get("rush_td"), sims.get("rec_td")
    if rt or ct:
        m = len(rt or ct)
        rt = rt or [0] * m
        ct = ct or [0] * m
        detail["markets"]["anytime_td"] = {
            "p_yes": round(sum(1 for i in range(m) if (rt[i] + ct[i]) >= 1) / m, 3)}
    fps = sorted(dk_points_from_sims(sims, n))
    detail["dk_points"] = {"mean": round(sum(fps) / n, 2),
                           "floor": round(_q(fps, 0.10), 2),
                           "ceiling": round(_q(fps, 0.90), 2)}
    return detail


def _wide_candidates(team_set: set, gl: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{norm_name: {info, source, pos, team, name}} for every baseline-resolvable
    skill player on the given teams. Universe = curated DB (priors overlaid) +
    2025 season baselines + current-season gamelogs (the rookie path). This is
    what widened the props desk from 28 hand-curated players to the full
    projectable roster (2026-08-13)."""
    by_team = nb.skill_players_by_team()
    entries: List[Any] = []
    needed: List[Any] = []
    for tm in team_set:
        for pl in by_team.get(tm) or []:
            entries.append((tm, pl))
            needed.append((pl["id"], pl["name"]))
    baselines = nb.ensure_baselines(needed)
    out: Dict[str, Dict[str, Any]] = {}
    for tm, pl in entries:
        if pl["norm"] in out:
            continue
        info, source = nb.resolve_info(pl["norm"], pl["pos"], pl["id"],
                                       baselines, gl, NFL_PLAYER_DB)
        if info:
            out[pl["norm"]] = {"info": info, "source": source, "pos": pl["pos"],
                               "team": tm, "name": pl["name"],
                               "espn_id": pl["id"]}
    return out


def _best_line_mc(samples, lines, prefix, band=(0.58, 0.80)):
    """Pick the standard line the simulated distribution leans on most (playable)."""
    best = None
    for line in lines:
        p_over = _SIM.prob_over(samples, line)
        side, p = ("OVER", p_over) if p_over >= 0.5 else ("UNDER", 1 - p_over)
        if not (band[0] <= p <= band[1]):
            continue
        if best is None or p > best["p"]:
            best = {"market": f"{prefix}_{side}_{line}", "p": round(p, 3),
                    "fair_odds": _american(p), "line": line, "side": side}
    return best


def _market_rows(nm: str, team: str, opp: str, sims: Dict[str, List[float]],
                 matchup: str, game_date: str, pass_f: float,
                 rush_f: float) -> List[Dict[str, Any]]:
    """The model-conviction prop rows for one simmed player (shape unchanged --
    the ledger collector reads these verbatim)."""
    rows: List[Dict[str, Any]] = []

    def _row(stat_type, of, samples, bm):
        return {"matchup": matchup, "game_date": game_date, "player": nm,
                "team": team, "opp_team": opp, "stat_type": stat_type,
                "opp_factor": round(of, 3),
                "projection": round(sum(samples) / len(samples), 2),
                "edge_class": f"MODEL_{bm['side']}", "best_market": bm}

    # Yardage / receptions / completions / longest -- read off the MC sample.
    for field, prefix, of in (("pass_yds", "PASS_YDS", pass_f), ("pass_cmp", "PASS_CMP", pass_f),
                              ("rush_yds", "RUSH_YDS", rush_f), ("rec_yds", "REC_YDS", pass_f),
                              ("rec", "REC", pass_f), ("longest_reception", "LONGEST_REC", pass_f),
                              ("longest_rush", "LONGEST_RUSH", rush_f)):
        samples = sims.get(field)
        if not samples:
            continue
        bm = _best_line_mc(samples, STD_LINES[field], prefix)
        if bm:
            rows.append(_row(field, of, samples, bm))

    # Passing TDs (2+) from the simulated TD count.
    if sims.get("pass_td"):
        for line in (1.5, 2.5):
            p_over = _SIM.prob_over(sims["pass_td"], line)
            side, p = ("OVER", p_over) if p_over >= 0.5 else ("UNDER", 1 - p_over)
            if 0.58 <= p <= 0.80:
                bm = {"market": f"PASS_TD_{side}_{line}", "p": round(p, 3),
                      "fair_odds": _american(p), "line": line, "side": side}
                rows.append(_row("pass_td", pass_f, sims["pass_td"], bm))
                break

    # Interceptions thrown (1+) from the simulated INT count.
    if sims.get("pass_int"):
        p_yes = _SIM.prob_at_least(sims["pass_int"], 1)
        side, p = ("OVER", p_yes) if p_yes >= 0.5 else ("UNDER", 1 - p_yes)
        if 0.58 <= p <= 0.85:
            bm = {"market": f"PASS_INT_{side}_0.5", "p": round(p, 3),
                  "fair_odds": _american(p), "line": 0.5, "side": side}
            rows.append(_row("pass_int", pass_f, sims["pass_int"], bm))

    # Anytime TD = P(rush_td + rec_td >= 1) from the sims.
    rt, ct = sims.get("rush_td"), sims.get("rec_td")
    if rt or ct:
        n = len(rt or ct)
        rt = rt or [0] * n
        ct = ct or [0] * n
        p_yes = sum(1 for i in range(n) if (rt[i] + ct[i]) >= 1) / n
        if 0.50 <= p_yes <= 0.92:   # priceable conviction; not a bogus "lock"
            bm = {"market": "ANYTIME_TD_YES", "p": round(p_yes, 3),
                  "fair_odds": _american(p_yes), "line": 0.5, "side": "YES"}
            rows.append({"matchup": matchup, "game_date": game_date, "player": nm,
                         "team": team, "opp_team": opp, "stat_type": "anytime_td",
                         "projection": round(p_yes, 3), "edge_class": "MODEL_TD",
                         "best_market": bm})
    return rows


def _generate(game_specs: List[Any], candidates: Dict[str, Dict[str, Any]],
              gl: Dict[str, Any]) -> Any:
    """(prop rows, per-player detail entries) for every projectable player on
    the given games. Curated players sim at SIM_N; the wide universe at
    SIM_N_WIDE."""
    rows: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    for matchup, home, away, game_date in game_specs:
        for nm, cand in candidates.items():
            if cand["team"] not in (home, away):
                continue
            opp = away if cand["team"] == home else home
            pass_f = _opp_factor(PASS_DEF, opp)
            rush_f = _opp_factor(RUSH_DEF, opp)
            seed = (sum(ord(c) for c in nm) * 131 + sum(ord(c) for c in game_date)) % 1_000_000
            n = SIM_N if "curated" in (cand.get("source") or "") else SIM_N_WIDE
            sims = _sim_player(nm, cand["info"], gl, pass_f, rush_f, seed, n=n)
            if not sims:
                continue
            rows.extend(_market_rows(nm, cand["team"], opp, sims, matchup,
                                     game_date, pass_f, rush_f))
            det = _detail_from_sims(sims)
            det.update({"player": cand["name"], "norm": nm, "pos": cand["pos"],
                        "team": cand["team"], "opp": opp, "matchup": matchup,
                        "game_date": game_date, "source": cand.get("source"),
                        "espn_id": cand.get("espn_id"),
                        "src_url": (f"https://www.espn.com/nfl/player/_/id/{cand['espn_id']}"
                                    if cand.get("espn_id") else None)})
            details.append(det)
    return rows, details


def _active_gate(candidates: Dict[str, Dict[str, Any]], gl: Dict[str, Any],
                 hist_games: List[Dict[str, Any]]) -> Any:
    """Drop players who are not playing (2026-10-28).

    The universe is every baseline-resolvable skill player on the roster, with
    no injury/depth check: of Week 8's ~1,000 props, 228 were on players with no
    box line (147 had not played in 2+ weeks -- injured or benched -- plus
    backup QBs like Davis Mills / Joe Flacco), and every one aged into a void.
    Rule: a player must have a box row in one of his team's last TWO completed
    regular-season games. Teams with no completed game yet (Week 1) pass."""
    norm = lambda s: re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "",
                            re.sub(r"[.'’-]", "", str(s or "").lower())).strip()
    seen: Dict[str, set] = {}
    for k, v in (gl or {}).items():
        seen.setdefault(norm(k), set()).update(str(r.get("date"))[:10]
                                               for r in (v.get("games") or []))
    played: Dict[str, List[str]] = {}
    for g in hist_games or []:
        d = str(g.get("date") or "")[:10]
        if d < NFL_2026_WEEK1 or g.get("home_score") is None:
            continue
        for tm in (g.get("home_abbrev"), g.get("away_abbrev")):
            if tm:
                played.setdefault(str(tm).upper(), []).append(d)

    def _near(d, ds):
        try:
            d0 = dt.date.fromisoformat(d)
        except Exception:
            return False
        for x in ds:
            try:
                if abs((dt.date.fromisoformat(x) - d0).days) <= 1:
                    return True
            except Exception:
                pass
        return False

    keep, dropped = {}, []
    for nm, cand in candidates.items():
        recent = sorted(set(played.get(str(cand.get("team") or "").upper(), [])))[-2:]
        if not recent:
            keep[nm] = cand
            continue
        rows = seen.get(norm(cand.get("name") or nm), set()) | seen.get(norm(nm), set())
        if any(_near(d, rows) for d in recent):
            keep[nm] = cand
        else:
            dropped.append(cand.get("name") or nm)
    return keep, dropped


PROJ_OUT = os.path.join(DATA_DIR, "nfl_player_projections.json")


def _write_projections(details: List[Dict[str, Any]], mode: str,
                       week_start: Optional[str]) -> None:
    """The data-rich per-player artifact behind nfl-players.html. Salary joined
    from the DK slate cache when present."""
    sal_by_norm: Dict[str, int] = {}
    slate = _load(os.path.join(DATA_DIR, "nfl_dfs_salaries.json"))
    for p in slate.get("players") or []:
        sal_by_norm.setdefault(nb.norm_name(p.get("name")), p.get("salary"))
    for d in details:
        d["dk_salary"] = sal_by_norm.get(d.get("norm"))
    details.sort(key=lambda d: -(((d.get("dk_points") or {}).get("mean")) or 0))
    _payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "form_rule": "form_v2",   # stamped onto every ledger pick (judged from 10/23 forward)
        "mode": mode,   # 'preview' (preseason: next regular-season slate) | 'live'
        "week_start": week_start,
        "n_players": len(details),
        "note": ("Per-player NFL projection detail from the play-level Monte Carlo: "
                 "distribution stats + P(over) at every standard line per market + "
                 "DK fantasy-point mean/floor/ceiling. "
                 + ("PREVIEW mode: projections for the upcoming Week 1 slate, "
                    "published for study -- these are NOT picks and none of this "
                    "enters the ledger until the regular season."
                    if mode == "preview" else
                    "LIVE mode: same universe the props board picks from.")),
        "players": details,
    }
    with open(PROJ_OUT, "w") as f:
        json.dump(_payload, f, indent=2)


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nfl_state.json"))
    games = state.get("games") or state.get("events") or []
    gl = _load(os.path.join(DATA_DIR, "nfl_player_gamelogs.json")).get("by_name") or {}

    # PRESEASON GATE (2026-08-13): the projections are season-baseline usage
    # (2025 gamelogs + priors). In preseason, starters play a series or two on a
    # coach's script -- the projection is structurally WRONG, not just noisy
    # (0.80 "conviction" on a starter who'll log six snaps). Before this gate,
    # 95 preseason props entered the ledger at up to -400 fair odds. No picks
    # until the regular season; payload stays shape-identical so no consumer
    # breaks, and the page can render the why.
    season_status = str(state.get("season_status") or "").lower()
    # DATE-HARDENED GATE (2026-08-18): between preseason weeks ESPN's scoreboard
    # empties and the label flips to "off-season" -- a string-keyed gate would
    # silently reopen when the next preseason slate entered the horizon. Until
    # Week 1 the gate holds no matter what the label says.
    if season_status == "preseason" or dt.date.today().isoformat() < NFL_2026_WEEK1:
        # PICKS stay gated (rows/strong_edges empty -> the ledger collector,
        # which reads ONLY strong_edges, collects nothing). But the desk still
        # publishes a WEEK 1 PREVIEW BOARD off the DK slate: full projections +
        # model leans for the next regular-season slate, clearly labeled and in
        # keys the collector never reads.
        preview_rows: List[Dict[str, Any]] = []
        details: List[Dict[str, Any]] = []
        wk_start = None
        slate = _load(os.path.join(DATA_DIR, "nfl_dfs_salaries.json"))
        wk_games = slate.get("games") or []
        wk_start = slate.get("start")
        if wk_games and wk_start:
            specs = []
            teams: set = set()
            for gname in wk_games:
                if "@" not in gname:
                    continue
                away, _, home = [s.strip().upper() for s in gname.partition("@")]
                specs.append((f"{away} @ {home}", home, away, wk_start))
                teams.update((home, away))
            candidates = _wide_candidates(teams, gl)
            preview_rows, details = _generate(specs, candidates, gl)
            _write_projections(details, "preview", wk_start)
        out = {
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "form_rule": "form_v2",   # stamped onto every ledger pick (judged from 10/23 forward)
            "season_status": season_status,
            "n_props": 0,
            "n_strong_edges": 0,
            "n_players_in_db": len(NFL_PLAYER_DB),
            "method_note": ("NFL model-conviction props (odds-independent). "
                            "GATED for preseason: starters rotate on coach scripts, "
                            "so season-baseline projections don't price these games. "
                            "Model props resume Week 1 automatically."),
            "preseason_note": ("Preseason: no model props. Usage is coach-scripted "
                               "and starters play snippets -- a season-baseline "
                               "projection can't price that honestly. Resumes Week 1."),
            "rows": [],
            "strong_edges": [],
            "preview": {"week_start": wk_start,
                        "n_rows": len(preview_rows),
                        "n_players": len(details),
                        "note": ("WEEK 1 PREVIEW: model leans for the upcoming "
                                 "regular-season slate, published for study. NOT "
                                 "picks -- nothing here enters the ledger until "
                                 "the season starts.")},
            "preview_rows": sorted(preview_rows,
                                   key=lambda r: -(r["best_market"]["p"]))[:150],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(out, f, indent=2)
        return out

    today = dt.date.today()
    horizon = today + dt.timedelta(days=HORIZON_DAYS)

    game_specs: List[Any] = []
    for g in games:
        # Skip games already final (state == "post" or a "Final" status).
        if (g.get("state") or "").lower() == "post":
            continue
        if "final" in (g.get("status") or "").lower():
            continue
        # Gate on kickoff within the horizon. Off-season, ESPN serves the next
        # season's Week 1 schedule (months out) -- without this we'd generate
        # props for games that can't settle for months and just void. A game with
        # no date is skipped (can't be dated -> can't settle).
        # ET SLATE DATE (2026-10-22). g["date"] is ESPN's UTC kickoff, so every
        # Thursday/Sunday/Monday NIGHT game (8:15pm ET = 00:15Z next day) was
        # stamped a day late, while espn_box_logs dates box rows by the ET slate
        # day (-5h). Those picks could never match a box row: they voided every
        # week and were evicted first, so the NFL record silently excluded every
        # prime-time game. Use the same -5h rule as the box logs.
        raw = str(g.get("date") or g.get("start") or "")
        gdate = None
        try:
            if len(raw) >= 16:
                t = dt.datetime.fromisoformat(raw.replace("Z", "+00:00")[:25])
                gdate = (t - dt.timedelta(hours=5)).date()
            elif raw:
                gdate = dt.date.fromisoformat(raw[:10])
        except Exception:
            try:
                gdate = dt.date.fromisoformat(raw[:10])
            except Exception:
                gdate = None
        if gdate is None or not (today <= gdate <= horizon):
            continue
        game_date = gdate.isoformat()
        # Prefer ESPN's direct abbrevs (home_abbrev); fall back to name-mapping.
        home = (g.get("home_abbrev") or _abbr(g.get("home_team") or g.get("home") or "")).upper()
        away = (g.get("away_abbrev") or _abbr(g.get("away_team") or g.get("away") or "")).upper()
        if not home or not away:
            continue
        matchup = f"{away} @ {home}"
        game_specs.append((matchup, home, away, game_date))

    # LIVE (regular season): the widened universe -- every baseline-resolvable
    # skill player on the horizon's games, not just the 28 curated names.
    all_teams: set = set()
    for _, home, away, _d in game_specs:
        all_teams.update((home, away))
    candidates = _wide_candidates(all_teams, gl) if game_specs else {}
    candidates, inactive = _active_gate(
        candidates, gl, _load(os.path.join(DATA_DIR, "nfl_historical.json")).get("games") or [])
    rows, details = _generate(game_specs, candidates, gl)
    if details:
        _write_projections(details, "live", min(s[3] for s in game_specs))

    rows.sort(key=lambda r: -(r["best_market"]["p"]))
    strong = [r for r in rows if r.get("best_market")]
    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "form_rule": "form_v2",   # stamped onto every ledger pick (judged from 10/23 forward)
        "season_status": season_status or "regular",
        "n_props": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(NFL_PLAYER_DB),
        "n_players_projected": len(details),
        "n_inactive_dropped": len(inactive),
        "inactive_dropped": sorted(inactive)[:200],
        "universe_note": ("Universe = curated priors + 2025 season baselines + "
                          "current-season gamelogs (rookies enter after "
                          f"{nb.MIN_GP_CUR} games)."),
        "method_note": ("NFL model-conviction props (odds-independent). Per-game "
                        "projection (season base, refreshed from gamelogs in-season, "
                        "opponent-defense adjusted) feeds a play-level Monte Carlo "
                        "(nfl_simulator: NegBinomial counts x Gamma per-event yards, "
                        "Poisson TD/INT) -- backtested better-calibrated than the prior "
                        "normal-CDF (ECE 0.027 vs 0.046 on 21.8k 2025 pairs). Prices "
                        "yds/cmp/rec/longest/TD/INT/anytime-TD off the simulated sample; "
                        "surfaces the standard line the model leans on (p in [0.58,0.80]). "
                        "Empty off-season; auto-activates Week 1."),
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nfl-props] {o['n_props']} props, {o['n_strong_edges']} strong "
          f"({o['n_players_in_db']} players in DB) -> {OUT}")
