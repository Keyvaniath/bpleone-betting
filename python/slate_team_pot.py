"""
EdgeStat -- unified slate-wide TEAM-LEVEL market aggregator.

Companion to slate_player_pot.py (which is player props).
This one consolidates team/game-level markets across every sport:

  - MLB: ML, totals (today.json + matchups.json)
  - NBA / NHL / WNBA / MLS / EPL / UCL / NFL / NCAAF / NCAAB / CWS: ML
  - Soccer extended: totals, BTTS, clean sheet, team to score 2+
  - NHL team props: totals, BTTS, 1st period, each-team-over
  - Golf: top winner per region (regional top picks)
  - LoL / CS / KBO: match ML
  - UFC: fight ML + method-of-victory

Output: data/slate_team_pot.json (ranked top picks across all team markets)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_team_pot.json")

MIN_PROB = 0.55
MAX_PROB = 0.92


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _add(picks, sport, matchup, market, prob, fair, source):
    if prob is None or not (MIN_PROB <= prob <= MAX_PROB): return
    picks.append({
        "sport": sport, "matchup": matchup,
        "market": market, "prob": round(prob, 4),
        "fair_american": fair, "source": source,
    })


def run() -> Dict[str, Any]:
    picks: List[Dict[str, Any]] = []

    # MLB game lines (today.json)
    mlb_today = _load(os.path.join(DATA_DIR, "today.json"))
    for g in (mlb_today.get("games") or []):
        m = g.get("model") or {}
        mkt = g.get("market") or {}
        mu = g.get("matchup")
        # P_home / P_away  (now propagating REAL market ML as fair_american
        # so downstream shrinkage can anchor to market-implied probability)
        ph = m.get("p_home_win")
        pa = m.get("p_away_win") or (1 - ph if ph else None)
        if ph: _add(picks, "MLB", mu, "ML_HOME", ph, mkt.get("home_ml"), "today")
        if pa: _add(picks, "MLB", mu, "ML_AWAY", pa, mkt.get("away_ml"), "today")
        # Total over/under from model fair_total
        for rec in (g.get("recommendations") or []):
            p = rec.get("model_prob")
            _add(picks, "MLB", mu, rec.get("label","?"), p,
                  rec.get("market_price"), "today_reco")

    # MLB team-total over/under edges (decomposed from fair_total)
    mlb_tt = _load(os.path.join(DATA_DIR, "mlb_team_total_edges.json"))
    for x in (mlb_tt.get("top_picks") or []):
        _add(picks, "MLB", x.get("matchup"), x.get("market"),
              x.get("prob"), x.get("fair"), "mlb_team_total")

    # MLB run-line (spread -1.5/+1.5) edges via Poisson convolution
    mlb_rl = _load(os.path.join(DATA_DIR, "mlb_run_line_edges.json"))
    for x in (mlb_rl.get("top_picks") or []):
        _add(picks, "MLB", x.get("matchup"), x.get("market"),
              x.get("prob"), x.get("fair"), "mlb_run_line")

    # NHL goalie-matchup team totals + shutout markets (playoff goalie analysis)
    nhl_g = _load(os.path.join(DATA_DIR, "nhl_goalie_matchup.json"))
    for x in (nhl_g.get("top_picks") or []):
        _add(picks, "NHL", x.get("matchup"), x.get("market"),
              x.get("prob"), x.get("fair"), "nhl_goalie")

    # F1 driver win/podium/points projections
    f1 = _load(os.path.join(DATA_DIR, "f1_driver_projections.json"))
    race_name = f1.get("upcoming_race") or "F1 Race"
    for d in (f1.get("drivers") or []):
        nm = d.get("name")
        if not nm: continue
        # Only surface top-tier picks (P(podium) > 0.55 or P(top10) > 0.85)
        if d.get("p_podium", 0) > 0.55:
            _add(picks, "F1", f"{nm} ({race_name})", "PODIUM_top3",
                  d.get("p_podium"), d.get("fair_podium_american"), "f1_driver")
        if d.get("p_points_top10", 0) > 0.85:
            _add(picks, "F1", f"{nm} ({race_name})", "POINTS_top10",
                  d.get("p_points_top10"), d.get("fair_points_american"), "f1_driver")
        if d.get("p_win", 0) > 0.10:
            _add(picks, "F1", f"{nm} ({race_name})", "WIN",
                  d.get("p_win"), d.get("fair_win_american"), "f1_driver")

    # ESPN-driven sports (state files have p_home_win + fair odds)
    def _has_signal(g):
        """Skip preseason 0-0 vs 0-0 games (only edge is HFA, not actionable)."""
        def _wins(rec):
            if not rec or not isinstance(rec, str): return 0
            try: return int(rec.split("-")[0])
            except Exception: return 0
        def _losses(rec):
            if not rec or not isinstance(rec, str): return 0
            try: return int(rec.split("-")[1])
            except Exception: return 0
        return (_wins(g.get("home_record")) + _losses(g.get("home_record")) +
                _wins(g.get("away_record")) + _losses(g.get("away_record"))) > 0

    for sport, sf in (
        ("NBA", "nba_state.json"), ("NHL", "nhl_state.json"),
        ("WNBA", "wnba_state.json"), ("MLS", "mls_state.json"),
        ("EPL", "epl_state.json"), ("UCL", "ucl_state.json"),
        ("NFL", "nfl_state.json"), ("NCAAF", "ncaaf_state.json"),
        ("NCAAB", "ncaab_state.json"), ("CWS", "cws_state.json"),
        ("NCAA_SOFTBALL", "ncaa_softball_state.json")
    ):
        d = _load(os.path.join(DATA_DIR, sf))
        for g in (d.get("games") or []):
            if g.get("state") == "post": continue
            if not _has_signal(g): continue   # skip preseason 0-0 games
            mu = g.get("matchup")
            ph = g.get("p_home_win")
            if ph:
                _add(picks, sport, mu, "ML_HOME", ph,
                      g.get("fair_home_american"), sf)
                _add(picks, sport, mu, "ML_AWAY", 1 - ph,
                      g.get("fair_away_american"), sf)

    # NHL team props (already loaded above)
    nhl_team = _load(os.path.join(DATA_DIR, "nhl_team_props.json"))
    for g in (nhl_team.get("games") or []):
        mu = g.get("matchup")
        for line, info in (g.get("totals") or {}).items():
            _add(picks, "NHL", mu, f"total_{line}", info.get("p"),
                  info.get("fair_over"), "nhl_team")
        btts = g.get("btts") or {}
        if btts.get("yes"):
            _add(picks, "NHL", mu, "BTTS_yes", btts["yes"],
                  btts.get("fair_yes"), "nhl_team")
        if btts.get("no"):
            _add(picks, "NHL", mu, "BTTS_no", btts["no"],
                  btts.get("fair_no"), "nhl_team")
        for key in ("home_team_over_2_5", "away_team_over_2_5",
                     "first_period_over_0_5", "first_period_over_1_5"):
            info = g.get(key) or {}
            _add(picks, "NHL", mu, key, info.get("p"),
                  info.get("fair_yes"), "nhl_team")

    # Soccer extended (EPL/MLS/UCL totals + BTTS)
    soccer = _load(os.path.join(DATA_DIR, "soccer_extended_props.json"))
    for g in (soccer.get("games") or []):
        mu = g.get("matchup")
        league = g.get("league") or "SOC"
        for line, info in (g.get("totals") or {}).items():
            _add(picks, league, mu, f"total_{line}", info.get("p"),
                  info.get("fair_over"), "soccer_ext")
        btts = g.get("btts") or {}
        if btts.get("yes"):
            _add(picks, league, mu, "BTTS_yes", btts["yes"],
                  btts.get("fair_yes"), "soccer_ext")
        if btts.get("no"):
            _add(picks, league, mu, "BTTS_no", btts["no"],
                  btts.get("fair_no"), "soccer_ext")
        for key in ("clean_sheet_home", "clean_sheet_away",
                      "team_to_score_2_plus_home", "team_to_score_2_plus_away"):
            info = g.get(key) or {}
            _add(picks, league, mu, key, info.get("p"),
                  info.get("fair_yes"), "soccer_ext")

    # LoL / CS / KBO match MLs
    for fname, sport in (("lol_bestbet.json", "LOL"),
                          ("cs_bestbet.json", "CS"),
                          ("kbo_bestbet.json", "KBO")):
        d = _load(os.path.join(DATA_DIR, fname))
        # Different shapes per file; try common keys
        candidates = d.get("candidates") or d.get("plays") or []
        for c in candidates:
            mu = c.get("matchup") or c.get("label")
            prob = c.get("model_prob") or c.get("p")
            fair = c.get("fair_american")
            _add(picks, sport, mu, c.get("play","ML"), prob, fair,
                  fname.replace(".json",""))

    # UFC fights
    ufc = _load(os.path.join(DATA_DIR, "ufc_matchup.json"))
    for f in (ufc.get("fights") or []):
        mu = f"{f.get('fighter_a','?')} vs {f.get('fighter_b','?')}"
        # Favorite ML
        fa_p = f.get("p_fighter_a_wins")
        fb_p = f.get("p_fighter_b_wins")
        if fa_p:
            _add(picks, "UFC", mu, f"ML_{f.get('fighter_a')}",
                  fa_p, f.get("fair_favorite_american") if fa_p >= 0.5 else f.get("fair_underdog_american"),
                  "ufc_matchup")
        if fb_p:
            _add(picks, "UFC", mu, f"ML_{f.get('fighter_b')}",
                  fb_p, f.get("fair_favorite_american") if fb_p >= 0.5 else f.get("fair_underdog_american"),
                  "ufc_matchup")
    # UFC method-of-victory (fight goes the distance markets)
    ufc_mov = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    for f in (ufc_mov.get("fights") or []):
        mu = f"{f.get('fighter_a','?')} vs {f.get('fighter_b','?')}"
        _add(picks, "UFC", mu, "fight_no_distance", f.get("p_finish"),
              f.get("fair_distance_no"), "ufc_mov")
        _add(picks, "UFC", mu, "fight_distance", f.get("p_decision"),
              f.get("fair_distance_yes"), "ufc_mov")

    # Sort by prob desc
    picks.sort(key=lambda x: -x["prob"])
    by_sport: Dict[str, int] = {}
    for p in picks: by_sport[p["sport"]] = by_sport.get(p["sport"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_prob": MIN_PROB,
        "max_prob": MAX_PROB,
        "n_picks_total": len(picks),
        "by_sport": by_sport,
        "top_30": picks[:30],
        "all_picks": picks[:500],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Slate TEAM pot: {p['n_picks_total']} picks in {p['min_prob']:.0%}-{p['max_prob']:.0%} sweet spot")
    print(f"  By sport: {p['by_sport']}")
    print(f"  Top 15:")
    for x in p["top_30"][:15]:
        fair = x.get("fair_american")
        fair_str = f"{fair:+d}" if isinstance(fair, int) else "--"
        print(f"    [{x['sport']:5s}] {(x['matchup'] or '?')[:50]:50s} {(x['market'] or '?')[:30]:30s} "
              f"p={x['prob']*100:.0f}% fair={fair_str}")
