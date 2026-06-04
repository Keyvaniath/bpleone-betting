"""
EdgeStat -- NFL player-prop projections (the model side for football).

Closes the football loop: GENERATE -> settle -> learn. The grader
(all_picks_tracker._grade_nfl_pick) and the box-score feed (espn_box_logs nfl)
are already live; this is what produces the picks they grade. Model-conviction
(odds-independent), the same shape as the cross-sport Model Conviction board:
for each player on today's NFL slate we project a per-game distribution and
surface the standard line the model is most confident over/under.

Markets: QB passing yards, rushing yards, receiving yards, receptions, and
anytime touchdown (P(>=1 rush/rec TD), Poisson).

  pass/rush/rec yds, receptions ~ Normal(mean = season per-game x opp factor,
                                          sigma = stat-specific CV) -> P(over line)
  anytime TD: lambda = TD/game x opp factor -> P(yes) = 1 - exp(-lambda)

Player bases are 2025 per-game numbers (refreshed in-season from
nfl_player_gamelogs.json when present). Off-season the slate is empty -> 0 picks;
it auto-activates Week 1. Output: data/nfl_player_props.json.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


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
    raw = table.get(opp, 1.0)
    return 1.0 + _DEF_DAMP * (raw - 1.0)


def _blend(recent: Optional[float], season: float) -> float:
    """Weight recent gamelog form over the season prior when we have it."""
    return round(0.65 * recent + 0.35 * season, 2) if recent is not None else season


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


def _recent_base(gamelogs_by_name, name, field):
    """In-season: average the player's recent gamelog for `field` (else None)."""
    prec = gamelogs_by_name.get(name)
    if not prec: return None
    vals = [g.get(field) for g in (prec.get("games") or []) if g.get(field) is not None]
    return sum(vals) / len(vals) if vals else None


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


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nfl_state.json"))
    games = state.get("games") or state.get("events") or []
    gl = _load(os.path.join(DATA_DIR, "nfl_player_gamelogs.json")).get("by_name") or {}

    today = dt.date.today()
    horizon = today + dt.timedelta(days=HORIZON_DAYS)

    rows: List[Dict[str, Any]] = []
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
        gd = (g.get("date") or g.get("start") or "")[:10]
        try:
            gdate = dt.date.fromisoformat(gd) if gd else None
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
        for name, info in NFL_PLAYER_DB.items():
            if info["team"] not in (home, away):
                continue
            opp = away if info["team"] == home else home
            pass_f = _opp_factor(PASS_DEF, opp)   # opponent pass defense
            rush_f = _opp_factor(RUSH_DEF, opp)   # opponent rush defense
            # Continuous-yardage / receptions markets (opponent-adjusted + recent form).
            for stat, prefix in (("pass_yds", "PASS_YDS"), ("rush_yds", "RUSH_YDS"),
                                 ("rec_yds", "REC_YDS"), ("rec", "REC")):
                base = info.get(stat)
                if base is None:
                    continue
                opp_f = rush_f if stat == "rush_yds" else pass_f
                mean = _blend(_recent_base(gl, name, stat), base) * opp_f
                floor, cv = SIGMA[stat]
                sigma = max(floor, cv * mean)
                bm = _best_line(mean, sigma, stat, prefix)
                if bm:
                    rows.append({"matchup": matchup, "game_date": game_date,
                                 "player": name, "team": info["team"],
                                 "opp_team": opp, "stat_type": stat,
                                 "opp_factor": round(opp_f, 3),
                                 "projection": round(mean, 1), "sigma": round(sigma, 1),
                                 "edge_class": f"MODEL_{bm['side']}", "best_market": bm})
            # Anytime TD (Poisson on rush+rec TD rate).
            lam = info.get("td_rate")
            if lam:
                p_yes = 1 - math.exp(-lam)
                if p_yes >= 0.50:
                    bm = {"market": "ANYTIME_TD_YES", "p": round(p_yes, 3),
                          "fair_odds": _american(p_yes), "line": 0.5, "side": "YES"}
                    rows.append({"matchup": matchup, "game_date": game_date,
                                 "player": name, "team": info["team"],
                                 "opp_team": opp, "stat_type": "anytime_td",
                                 "projection": round(lam, 2), "edge_class": "MODEL_TD",
                                 "best_market": bm})
            # Passing TDs (QB): Poisson on the season TD rate, opponent-adjusted.
            ptd = info.get("pass_td")
            if ptd:
                lam = ptd * pass_f
                for line in (1.5, 2.5):
                    k = int(line)   # over 1.5 -> 2+ passing TDs
                    p_over = 1 - sum(math.exp(-lam) * lam ** i / math.factorial(i)
                                     for i in range(k + 1))
                    side, p = ("OVER", p_over) if p_over >= 0.5 else ("UNDER", 1 - p_over)
                    if 0.58 <= p <= 0.80:
                        bm = {"market": f"PASS_TD_{side}_{line}", "p": round(p, 3),
                              "fair_odds": _american(p), "line": line, "side": side}
                        rows.append({"matchup": matchup, "game_date": game_date,
                                     "player": name, "team": info["team"],
                                     "opp_team": opp, "stat_type": "pass_td",
                                     "opp_factor": round(pass_f, 3),
                                     "projection": round(lam, 2),
                                     "edge_class": f"MODEL_{side}", "best_market": bm})
                        break

    rows.sort(key=lambda r: -(r["best_market"]["p"]))
    strong = [r for r in rows if r.get("best_market")]
    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_props": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(NFL_PLAYER_DB),
        "method_note": ("NFL model-conviction props (odds-independent). Per-game "
                        "projection (season base, refreshed from gamelogs in-season) "
                        "-> Normal CDF for yds/receptions, Poisson for anytime TD. "
                        "Surfaces the standard line the model leans on (p in "
                        "[0.58,0.80]). Empty off-season; auto-activates Week 1."),
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
