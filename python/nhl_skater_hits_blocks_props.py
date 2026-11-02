"""
EdgeStat -- NHL skater hits + blocks + PIM prop projections.

Existing nhl_skater_props.py covers shots/points. This module adds the
defensive-grit props that DK/FD list separately:
  - Hits 1+, 2+, 3+
  - Blocks 1+, 2+
  - Penalty minutes 1.5+ (over/under)

Per-player baseline from 2024-25 season hits-per-game, blocks-per-game.
Poisson approximation since these are count events.

Player DB: top defensive forwards + physical defensemen (50 names).

Output: data/nhl_skater_hits_blocks_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from nhl_teams import abbr as _abbr   # full scoreboard name -> abbrev (fixes [:3] team drops)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json")

# 2024-25 season hits + blocks per game (top physical players, mostly playoff teams)
PLAYER_DB = {
    # Hits leaders
    "tom wilson":          {"team": "WSH", "hits_pg": 4.5, "blocks_pg": 1.2, "pim_pg": 1.8},
    "matt rempe":          {"team": "NYR", "hits_pg": 4.8, "blocks_pg": 0.8, "pim_pg": 2.5},
    "trent frederic":      {"team": "EDM", "hits_pg": 3.5, "blocks_pg": 1.0, "pim_pg": 1.5},
    "ryan reaves":         {"team": "SJS", "hits_pg": 4.0, "blocks_pg": 0.5, "pim_pg": 2.2},
    "garnet hathaway":     {"team": "PHI", "hits_pg": 4.2, "blocks_pg": 1.0, "pim_pg": 1.2},
    "nicolas roy":         {"team": "VGK", "hits_pg": 3.0, "blocks_pg": 0.9, "pim_pg": 0.6},
    "barclay goodrow":     {"team": "SJS", "hits_pg": 3.5, "blocks_pg": 1.3, "pim_pg": 0.8},
    "luke schenn":         {"team": "NSH", "hits_pg": 4.2, "blocks_pg": 2.0, "pim_pg": 0.5},
    "radko gudas":         {"team": "ANA", "hits_pg": 3.8, "blocks_pg": 1.8, "pim_pg": 1.0},
    "brady tkachuk":       {"team": "OTT", "hits_pg": 3.5, "blocks_pg": 0.8, "pim_pg": 1.2},
    "matthew tkachuk":     {"team": "FLA", "hits_pg": 3.2, "blocks_pg": 1.0, "pim_pg": 1.4},
    "sam reinhart":        {"team": "FLA", "hits_pg": 0.8, "blocks_pg": 0.8, "pim_pg": 0.4},
    "aleksander barkov":   {"team": "FLA", "hits_pg": 1.0, "blocks_pg": 1.2, "pim_pg": 0.3},
    "nikita kucherov":     {"team": "TBL", "hits_pg": 0.8, "blocks_pg": 0.5, "pim_pg": 0.4},
    "leon draisaitl":      {"team": "EDM", "hits_pg": 1.5, "blocks_pg": 0.6, "pim_pg": 0.4},
    "connor mcdavid":      {"team": "EDM", "hits_pg": 1.0, "blocks_pg": 0.5, "pim_pg": 0.3},
    # Blocks leaders (defensemen)
    "ryan suter":          {"team": "STL", "hits_pg": 1.5, "blocks_pg": 2.5, "pim_pg": 0.3},
    "jacob trouba":        {"team": "ANA", "hits_pg": 3.0, "blocks_pg": 2.2, "pim_pg": 0.8},
    "k'andre miller":      {"team": "NYR", "hits_pg": 2.8, "blocks_pg": 2.0, "pim_pg": 0.4},
    "noah hanifin":        {"team": "VGK", "hits_pg": 1.5, "blocks_pg": 2.3, "pim_pg": 0.3},
    "alex pietrangelo":    {"team": "VGK", "hits_pg": 2.0, "blocks_pg": 2.5, "pim_pg": 0.4},
    "shea theodore":       {"team": "VGK", "hits_pg": 1.5, "blocks_pg": 1.8, "pim_pg": 0.3},
    "mark giordano":       {"team": "TOR", "hits_pg": 1.0, "blocks_pg": 2.5, "pim_pg": 0.4},
    "morgan rielly":       {"team": "TOR", "hits_pg": 1.2, "blocks_pg": 2.0, "pim_pg": 0.5},
    "jaccob slavin":       {"team": "CAR", "hits_pg": 0.9, "blocks_pg": 2.5, "pim_pg": 0.2},
    "brent burns":         {"team": "CAR", "hits_pg": 2.5, "blocks_pg": 2.0, "pim_pg": 0.5},
    "victor hedman":       {"team": "TBL", "hits_pg": 1.5, "blocks_pg": 2.2, "pim_pg": 0.3},
    "cale makar":          {"team": "COL", "hits_pg": 1.2, "blocks_pg": 1.4, "pim_pg": 0.5},
    "miro heiskanen":      {"team": "DAL", "hits_pg": 0.8, "blocks_pg": 1.8, "pim_pg": 0.3},
    "esa lindell":         {"team": "DAL", "hits_pg": 1.5, "blocks_pg": 2.2, "pim_pg": 0.3},
    # Star skaters (lower hits)
    "auston matthews":     {"team": "TOR", "hits_pg": 1.0, "blocks_pg": 0.5, "pim_pg": 0.3},
    "william nylander":    {"team": "TOR", "hits_pg": 0.5, "blocks_pg": 0.4, "pim_pg": 0.3},
    "mitch marner":        {"team": "TOR", "hits_pg": 0.5, "blocks_pg": 0.6, "pim_pg": 0.2},
    "sidney crosby":       {"team": "PIT", "hits_pg": 1.0, "blocks_pg": 0.4, "pim_pg": 0.4},
    "evgeni malkin":       {"team": "PIT", "hits_pg": 1.5, "blocks_pg": 0.5, "pim_pg": 0.6},
    "alex ovechkin":       {"team": "WSH", "hits_pg": 1.5, "blocks_pg": 0.5, "pim_pg": 0.4},
}
# Live current teams over the hard-coded ones (2026-10-23, real_stats_lookup).
PLAYER_DB = __import__("real_stats_lookup").apply_live_teams("nhl", PLAYER_DB)



def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _fullname_index() -> Dict[tuple, List[str]]:
    """(first initial, folded last name) -> full names in the box-log file the
    grader and the ledger's activity gate key on (the NHL API writes
    'T. Frederic'; the grader needs 'trent frederic')."""
    import nhl_goalies as _ng
    idx: Dict[tuple, List[str]] = {}
    for full in (_load(os.path.join(DATA_DIR, "nhl_player_gamelogs.json")).get("by_name") or {}):
        parts = _ng._fold(full).split()
        if len(parts) >= 2:
            idx.setdefault((parts[0][:1], parts[-1]), []).append(full)
    return idx


def run() -> Dict[str, Any]:
    """2026-11-02: projections from REAL per-player rates (nhl_skaters store:
    every boxscore since 2024-25, EWMA + position-mean shrinkage, hits x
    home/away factor) through the negative binomial whose dispersion was fitted
    on last season. The hand-typed PLAYER_DB above is no longer read: graded on
    real box scores it ran HITS_OVER_2.5 6-15 at ~67% predicted."""
    import nhl_goalies as _ng
    import nhl_skaters as ns
    grown = ns.grow()
    st, cal = ns.load()
    r_h, r_b, r_p = ns.dispersion(cal, "hits"), ns.dispersion(cal, "blocks"), ns.dispersion(cal, "pim")
    names = _fullname_index()
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []
    cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()

    by_team: Dict[str, List[str]] = {}
    for pid, x in st.p.items():
        if x.get("team") and str(x.get("last_date") or "") >= cutoff and x.get("gp", 0) >= 10:
            by_team.setdefault(x["team"], []).append(pid)

    rows: List[Dict[str, Any]] = []
    n_unmapped = 0
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or g.get("state") in ("in", "post"):
            continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away:
            continue
        for side, team in (("home", home), ("away", away)):
            for pid in by_team.get(_ng._team(team), []):
                x = st.p[pid]
                parts = _ng._fold(x.get("name")).replace(".", "").split()
                full = names.get((parts[0][:1], parts[-1])) if len(parts) >= 2 else None
                if not full or len(full) != 1:
                    n_unmapped += 1          # grader can't key him -> never a pick
                    continue
                hits_lam = st.rate(pid, "hits", side)
                blocks_lam = st.rate(pid, "blocks")
                pim_lam = st.rate(pid, "pim")
                p_hits_1 = ns.p_at_least(1, hits_lam, r_h)
                p_hits_2 = ns.p_at_least(2, hits_lam, r_h)
                p_hits_3 = ns.p_at_least(3, hits_lam, r_h)
                p_hits_4 = ns.p_at_least(4, hits_lam, r_h)
                p_blocks_1 = ns.p_at_least(1, blocks_lam, r_b)
                p_blocks_2 = ns.p_at_least(2, blocks_lam, r_b)

                # Same selection bands as before -- now on calibrated probabilities.
                edge_class, best_market = "NONE", None
                if 0.62 <= p_hits_3 <= 0.75:
                    edge_class = "STRONG_HITS_OVER_2_5"
                    best_market = {"market": "HITS_OVER_2.5", "p": round(p_hits_3, 3), "fair_odds": _american(p_hits_3)}
                elif 0.62 <= p_hits_2 <= 0.75:
                    edge_class = "STRONG_HITS_OVER_1_5"
                    best_market = {"market": "HITS_OVER_1.5", "p": round(p_hits_2, 3), "fair_odds": _american(p_hits_2)}
                elif 0.58 <= p_blocks_2 <= 0.72:
                    edge_class = "STRONG_BLOCKS_OVER_1_5"
                    best_market = {"market": "BLOCKS_OVER_1.5", "p": round(p_blocks_2, 3), "fair_odds": _american(p_blocks_2)}

                rows.append({
                    "matchup": f"{away} @ {home}",
                    "player": full[0],
                    "team": team,
                    "side": side,
                    "games_weighted": round(x["gp"], 1),
                    "hits_per_game": round(hits_lam, 3),
                    "blocks_per_game": round(blocks_lam, 3),
                    "pim_per_game": round(pim_lam, 3),
                    "p_hits_1_plus": round(p_hits_1, 3),
                    "p_hits_2_plus": round(p_hits_2, 3),
                    "p_hits_3_plus": round(p_hits_3, 3),
                    "p_hits_4_plus": round(p_hits_4, 3),
                    "p_blocks_1_plus": round(p_blocks_1, 3),
                    "p_blocks_2_plus": round(p_blocks_2, 3),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -(r["hits_per_game"] + r["blocks_per_game"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_unmapped_names": n_unmapped,
        "n_boxscores_added": grown,
        "dispersion": {"hits": r_h, "blocks": r_b, "pim": r_p},
        "method_note": ("Real per-player rates from every NHL boxscore since 2024-25 (EWMA, position-mean "
                        "prior, hits x home/away scorer factor), negative binomial with dispersion fitted on "
                        "last season (calibration in nhl_skater_rates.json). STRONG bands unchanged: hits 3+ "
                        "p 0.62-0.75, hits 2+ p 0.62-0.75, blocks 2+ p 0.58-0.72. Replaced the hand-typed "
                        "PLAYER_DB on 2026-11-02 (it graded 6-15 on hits 3+ at ~67% predicted)."),
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-hits] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
