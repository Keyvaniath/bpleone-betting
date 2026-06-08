"""
EdgeStat -- per-game MLB cards (powers the clickable game.html detail view).

Unifies, for EACH game on today's slate, everything the model says about it into
one object the front-end can render on click:
  - the matchup header (teams, time, park, weather, starters)
  - the model LINE (fair ML + total + win probs) vs the live market (Bovada) + edge
  - the game RECOMMENDATIONS (the actual plays: edge %, Kelly, confidence)
  - every PLAYER PROP prediction we generated for that game (pitcher + batter),
    grouped and sorted by conviction
Live score / inning / in-game win-prob are overlaid client-side from
live_state.json + live_game.json (which the in-progress poller refreshes), so the
page ticks during the game.

Source of truth for the game line is today.json (model + market + recommendations
already per game); starters come from matchups.json; props are joined by the
"AWAY @ HOME" matchup key shared across every prediction file.

Output: data/mlb_game_cards.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_cards.json")

# abbrev -> MLB StatsAPI full name, so game.html can join the live poller
# (live_state.json keys games by full team name, not abbrev).
TEAM_FULL_NAME = {
    "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves", "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox", "CHC": "Chicago Cubs", "CWS": "Chicago White Sox",
    "CHW": "Chicago White Sox", "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies", "DET": "Detroit Tigers", "HOU": "Houston Astros",
    "KC": "Kansas City Royals", "KCR": "Kansas City Royals", "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers", "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins", "NYM": "New York Mets", "NYY": "New York Yankees",
    "OAK": "Athletics", "ATH": "Athletics", "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates", "SD": "San Diego Padres", "SDP": "San Diego Padres",
    "SF": "San Francisco Giants", "SFG": "San Francisco Giants", "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals", "TB": "Tampa Bay Rays", "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
    "WSN": "Washington Nationals",
}

# (filename, family, short stat label). Empty/missing files are skipped.
PROP_FILES = [
    ("mlb_pitcher_strikeouts_props.json", "pitcher", "Strikeouts"),
    ("mlb_pitcher_er_props.json", "pitcher", "Earned runs"),
    ("mlb_pitcher_hits_allowed_props.json", "pitcher", "Hits allowed"),
    ("mlb_pitcher_outs_props.json", "pitcher", "Outs"),
    ("mlb_pitcher_walks_props.json", "pitcher", "Walks"),
    ("mlb_pitcher_quality_start_props.json", "pitcher", "Quality start"),
    ("mlb_pitcher_win_props.json", "pitcher", "Win"),
    ("mlb_batter_strikeout_props.json", "batter", "Strikeouts"),
    ("mlb_batter_walks_props.json", "batter", "Walks"),
    ("mlb_total_bases_props.json", "batter", "Total bases"),
    ("mlb_hrr_props.json", "batter", "Hits+Runs+RBI"),
    ("mlb_doubles_props.json", "batter", "XBH"),
    ("mlb_batter_2plus_hits_props.json", "batter", "2+ hits"),
    ("mlb_batter_3plus_tb_props.json", "batter", "3+ TB"),
    ("mlb_batter_rbi_props.json", "batter", "RBI"),
    ("mlb_steal_props.json", "batter", "Stolen base"),
    ("mlb_to_hit_hr_yn.json", "batter", "Home run"),
    ("mlb_to_record_hit_yn.json", "batter", "To record a hit"),
    ("mlb_run_line_props.json", "game", "Run line"),
    ("mlb_game_total_alt_props.json", "game", "Total (alt)"),
    ("mlb_game_run_diff_props.json", "game", "Run differential"),
    ("mlb_team_sb_total_props.json", "game", "Team steals"),
    ("nrfi.json", "game", "NRFI / YRFI"),
    ("mlb_game_first_inning_hit_yn.json", "game", "1st-inning hit"),
]


def _load(name: str) -> Any:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _rows(j: Any) -> List[Dict[str, Any]]:
    if isinstance(j, list):
        return [r for r in j if isinstance(r, dict)]
    if not isinstance(j, dict):
        return []
    for k in ("rows", "strong_edges", "starters", "props", "players", "edges"):
        v = j.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    # fall back to the longest list-of-dicts value
    best: List[Dict[str, Any]] = []
    for v in j.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and len(v) > len(best):
            best = v
    return best


def _num(x) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def _normalize(r: Dict[str, Any], family: str, stat: str) -> Optional[Dict[str, Any]]:
    """Pull a uniform (subject, market, prob, fair_odds, edge) out of a prop row."""
    bm = r.get("best_market") or {}
    prob = _num(bm.get("p") if bm.get("p") is not None else r.get("prob") or r.get("p")
                or r.get("p_scores") or r.get("p_yes") or r.get("p_over_2_5"))
    if prob is None:
        return None
    subject = (r.get("player") or r.get("pitcher") or r.get("batter") or r.get("name")
               or r.get("team") or r.get("matchup") or "")
    market = bm.get("market") or r.get("market") or stat
    fair = (bm.get("fair_odds") if bm.get("fair_odds") is not None
            else r.get("fair_odds") or r.get("fair_american") or r.get("fair_yes"))
    edge = r.get("edge_class") or r.get("edge_pct")
    return {
        "family": family, "stat": stat, "subject": subject,
        "market": market, "prob": round(prob, 3),
        "fair_odds": fair, "edge": edge,
    }


def run() -> Dict[str, Any]:
    today = _load("today.json")
    games = today.get("games") or []
    matchups = _load("matchups.json")
    mu_by_key = {(g.get("matchup") or ""): g for g in (matchups.get("games") or [])}

    # join all player/game props by matchup
    preds_by_mu: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for fname, family, stat in PROP_FILES:
        for r in _rows(_load(fname)):
            mk = r.get("matchup")
            if not isinstance(mk, str) or " @ " not in mk:
                continue
            p = _normalize(r, family, stat)
            if p:
                preds_by_mu[mk].append(p)

    # ---- trend indexes (team form / ATS / pitcher form / bullpen / hot-cold) ----
    tf = (_load("team_form.json").get("teams") or {})
    form_by_abbr = {(v.get("abbr") or "").upper(): v for v in tf.values() if isinstance(v, dict)}
    ats = _load("ats_tracker_mlb.json")
    ats_by_name = {}
    for key in ("model_underrates_top5", "model_overrates_top5", "rows", "teams"):
        for r in (ats.get(key) or []):
            if isinstance(r, dict) and r.get("name"):
                ats_by_name[r["name"]] = r
    pform = {}  # (matchup, SIDE) -> row, merged from form tracker + recent-form index
    for r in _rows(_load("mlb_pitcher_form_tracker.json")):
        pform[(r.get("matchup"), (r.get("side") or "").upper())] = dict(r)
    for r in _rows(_load("mlb_starter_recent_form_index.json")):
        # merge trend/tier/form_index onto the matching pitcher row (match by matchup+pitcher)
        for k, v in pform.items():
            if k[0] == r.get("matchup") and v.get("pitcher") and v.get("pitcher") == r.get("pitcher"):
                v.update({"trend": r.get("trend"), "tier": r.get("tier"), "form_index": r.get("form_index")})
    pen_by_mu = {g.get("matchup"): g for g in _rows(_load("mlb_bullpen_fatigue_index.json"))}
    hot = _load("hot_streaks.json")
    hotcold_by_team = defaultdict(list)
    for kind, key in (("hot", "hot_batters"), ("cold", "cold_batters")):
        for p in (hot.get(key) or []):
            t = (p.get("team") or "").upper()
            if t:
                hotcold_by_team[t].append({
                    "name": p.get("name"), "team": t, "kind": kind,
                    "heat": p.get("heat"), "recent_ops": p.get("recent_ops"),
                    "season_ops": p.get("season_ops"), "order": p.get("lineup_order"),
                })

    # head-to-head: season series record + recent meetings (historical_mlb) +
    # current-series standing (series_context, already keyed by matchup).
    hist = [g for g in (_load("historical_mlb.json").get("games") or []) if isinstance(g, dict)]
    sctx_by_mu = {g.get("matchup"): g for g in (_load("series_context.json").get("games") or [])
                  if isinstance(g, dict)}

    def _h2h(away, home, mk):
        a, h = away.upper(), home.upper()
        meetings = [g for g in hist
                    if {(g.get("home_abbrev") or "").upper(), (g.get("away_abbrev") or "").upper()} == {a, h}
                    and g.get("home_score") is not None]
        meetings.sort(key=lambda g: g.get("date") or "", reverse=True)
        aw = hw = 0
        for g in meetings:
            win_ab = (g.get("home_abbrev") if (g.get("home_score") or 0) > (g.get("away_score") or 0)
                      else g.get("away_abbrev"))
            if (win_ab or "").upper() == a:
                aw += 1
            elif (win_ab or "").upper() == h:
                hw += 1
        sctx = sctx_by_mu.get(mk) or {}
        return {
            "season_series": {"away": a, "away_wins": aw, "home": h, "home_wins": hw, "n": len(meetings)},
            "recent_meetings": [{"date": g.get("date"), "away": g.get("away_abbrev"),
                                 "away_score": g.get("away_score"), "home": g.get("home_abbrev"),
                                 "home_score": g.get("home_score")} for g in meetings[:5]],
            "current_series": ({"series_number": sctx.get("series_number"),
                                "prior_results": sctx.get("prior_results"),
                                "note": sctx.get("note")} if sctx else None),
        }

    def _trends(mk, away, home, away_full, home_full):
        pf = lambda side: pform.get((mk, side)) or {}
        slim_form = lambda v: ({k: v.get(k) for k in
                                ("wins", "losses", "run_diff", "runs_pg", "runs_allowed_pg",
                                 "streak", "games_in_sample")} if v else None)
        slim_ats = lambda v: ({k: v.get(k) for k in ("ats_record", "cover_pct", "signal")} if v else None)
        slim_pf = lambda v: ({k: v.get(k) for k in
                              ("pitcher", "status", "trend", "tier", "k9_delta", "era_delta",
                               "recent_k_per_9_l3", "recent_era_l3", "form_index", "leans")} if v else None)
        pen = pen_by_mu.get(mk) or {}
        form = lambda ab, full: form_by_abbr.get((ab or "").upper()) or tf.get(full or "")
        return {
            "team_form": {"away": slim_form(form(away, away_full)),
                          "home": slim_form(form(home, home_full))},
            "ats": {"away": slim_ats(ats_by_name.get(away_full)),
                    "home": slim_ats(ats_by_name.get(home_full))},
            "pitcher_form": {"away": slim_pf(pf("AWAY")), "home": slim_pf(pf("HOME"))},
            "bullpen": {"away_pen": pen.get("away_pen"), "home_pen": pen.get("home_pen"),
                        "leans": pen.get("leans")} if pen else None,
            "hot_cold": sorted(hotcold_by_team.get(away.upper(), []) + hotcold_by_team.get(home.upper(), []),
                               key=lambda p: -(p.get("heat") or 0))[:12],
        }

    cards: List[Dict[str, Any]] = []
    for g in games:
        mk = g.get("matchup") or ""
        if " @ " not in mk:
            continue
        away, home = [s.strip() for s in mk.split(" @ ", 1)]
        mu = mu_by_key.get(mk, {})

        def _starter(side):
            sp = mu.get(f"{side}_pitcher")
            if isinstance(sp, str):
                return {"name": sp}
            sp = sp or {}
            season = sp.get("season") or {}
            return {"name": sp.get("name"), "hand": sp.get("hand"),
                    "era": season.get("era"), "whip": season.get("whip"),
                    "k9": season.get("k9")}

        preds = sorted(preds_by_mu.get(mk, []), key=lambda p: -(p["prob"] or 0))
        cards.append({
            "matchup": mk, "away": away, "home": home,
            "away_full": TEAM_FULL_NAME.get(away), "home_full": TEAM_FULL_NAME.get(home),
            "time": g.get("time"), "park": g.get("park"),
            "weather": g.get("weather"), "umpire": g.get("umpire"),
            "model": g.get("model"), "market": g.get("market"),
            "recommendations": g.get("recommendations") or [],
            "pitchers": {"away": _starter("away"), "home": _starter("home")},
            "trends": _trends(mk, away, home, TEAM_FULL_NAME.get(away), TEAM_FULL_NAME.get(home)),
            "h2h": _h2h(away, home, mk),
            "n_predictions": len(preds),
            "predictions": preds,
        })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "date": today.get("date"),
        "n_games": len(cards),
        "method_note": "Per-game unified card: today.json model+market+recs joined with "
                       "every per-matchup player/game prop. Live score/win-prob overlaid "
                       "client-side from live_state.json + live_game.json.",
        "games": cards,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    tot = sum(c["n_predictions"] for c in o["games"])
    print(f"[game-cards] {o['n_games']} games, {tot} predictions joined -> {OUT}")
