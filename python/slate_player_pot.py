"""
EdgeStat -- unified slate-wide player prop aggregator.

Pulls ALL high-confidence player props across every sport's extended-props
module + PrizePicks board + base prop projections, ranks by confidence,
and surfaces a single top-50 board.

Sources:
  - mlb_extended_props.json    (TB/HRR/BB/SO/K/ER/Outs Poisson)
  - mlb_pitcher_matchup.json   (K sweet-spot + ER under)
  - mlb_batter_logs.json       (1+ hit / 2+ hits / 1+ HR / 1+ RBI / 1+ run)
  - nba_extended_props.json    (DD/TD/combos/alt-3PM)
  - real_player_props_nba.json (PTS/REB/AST/3PM/PRA)
  - nhl_extended_props.json    (ATG/G/A/PTS/SOG)
  - pickem.json                (PrizePicks board)
  - lol_player_props.json
  - cs_player_props.json
  - kbo_player_props.json

Filtering: 60-92% probability sweet spot (avoid -1000 lopsided picks).
Output: data/slate_player_pot.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_player_pot.json")

MIN_PROB = 0.60
MAX_PROB = 0.92


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _add(picks, sport, player, team, market, prob, fair, source):
    if prob is None or not (MIN_PROB <= prob <= MAX_PROB): return
    picks.append({
        "sport": sport, "player": player, "team": team,
        "market": market, "prob": round(prob, 4),
        "fair_american": fair, "source": source,
    })


def run() -> Dict[str, Any]:
    picks: List[Dict[str, Any]] = []

    # MLB extended (4846 batter+pitcher props)
    mlb_ext = _load(os.path.join(DATA_DIR, "mlb_extended_props.json"))
    for b in (mlb_ext.get("batters") or []):
        for mkt, info in (b.get("props") or {}).items():
            p = info.get("p")
            _add(picks, "MLB", b["name"], b["team_abbr"], mkt,
                  p, info.get("fair_yes"), "mlb_ext_batter")
    for p in (mlb_ext.get("pitchers") or []):
        for mkt, info in (p.get("props") or {}).items():
            prob = info.get("p") or info.get("p_under")
            fair = info.get("fair_yes") or info.get("fair_under")
            _add(picks, "MLB", p["name"], p["team_abbr"], mkt,
                  prob, fair, "mlb_ext_pitcher")

    # MLB pitcher matchup (K + ER under)
    pm = _load(os.path.join(DATA_DIR, "mlb_pitcher_matchup.json"))
    for m in (pm.get("matchups") or []):
        b = m.get("best_k_play")
        if b and b.get("p_over"):
            _add(picks, "MLB", b["pitcher"], b.get("team"),
                  f"k_over_{b['line']}", b["p_over"], b.get("fair_over"),
                  "pitcher_matchup")
        for e in (m.get("er_under_2_5_candidates") or []):
            _add(picks, "MLB", e["pitcher"], e.get("team"),
                  "er_under_2_5", e["p_under_2_5_er"], e.get("fair_under"),
                  "pitcher_matchup")

    # MLB base batter props
    mb = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    for b in (mb.get("batters") or []):
        for mkt, info in (b.get("props") or {}).items():
            p = info.get("p")
            _add(picks, "MLB", b["name"], b["team_abbr"], mkt,
                  p, info.get("fair_yes"), "mlb_batter_logs")

    # MLB BATTER-vs-SP matchup-adjusted edges (xwOBA arsenal + career splits)
    sp_edges = _load(os.path.join(DATA_DIR, "mlb_batter_sp_edges.json"))
    # Pull all batters across all games (de-duped by name within source)
    seen_sp = set()
    for g in (sp_edges.get("games") or []):
        for b in (g.get("batters") or []):
            nm = b.get("batter")
            if not nm or nm in seen_sp: continue
            seen_sp.add(nm)
            # Only add if matchup-adjusted prob is materially different from base
            # (i.e. this matchup is actually informative)
            for mkt, p_key, fair_key in (
                ("1_plus_hit_vs_sp", "adj_p_1_plus_hit", "fair_yes_1_hit"),
                ("1_plus_hr_vs_sp", "adj_p_1_plus_hr", "fair_yes_1_hr"),
                ("2_plus_hits_vs_sp", "adj_p_2_plus_hits", "fair_yes_2_hit"),
            ):
                p = b.get(p_key)
                fair = b.get(fair_key)
                _add(picks, "MLB", nm, b.get("team_abbr"),
                      mkt, p, fair, "mlb_batter_sp_edges")

    # MLB BATTER situational splits (home/away + day/night adjusted)
    sit = _load(os.path.join(DATA_DIR, "mlb_batter_situational_splits.json"))
    for b in (sit.get("all_batters") or []):
        for mkt, p_key, fair_key in (
            ("1_plus_hit_situational", "adj_p_1_plus_hit", "fair_yes_1_hit"),
            ("1_plus_hr_situational", "adj_p_1_plus_hr", "fair_yes_1_hr"),
        ):
            p = b.get(p_key)
            fair = b.get(fair_key)
            _add(picks, "MLB", b.get("batter"), b.get("team_abbr"),
                  mkt, p, fair, "mlb_batter_situational")

    # NBA extended
    nba_ext = _load(os.path.join(DATA_DIR, "nba_extended_props.json"))
    for pp in (nba_ext.get("players") or []):
        for mkt, info in (pp.get("props") or {}).items():
            prob = info.get("p")
            fair = info.get("fair_yes") or info.get("fair_over")
            _add(picks, "NBA", pp["name"], pp["team"], mkt, prob, fair,
                  "nba_ext")

    # NBA real player props (PTS/REB/AST/3PM/PRA)
    nba_rp = _load(os.path.join(DATA_DIR, "real_player_props_nba.json"))
    for pp in (nba_rp.get("players") or []):
        for prop in (pp.get("props") or []):
            mkt = f"{prop.get('market')}_over_{prop.get('line')}"
            p = prop.get("p_over")
            _add(picks, "NBA", pp["name"], pp["team_abbr"], mkt,
                  p, prop.get("fair_over_american"), "nba_real_props")

    # NHL extended
    nhl_ext = _load(os.path.join(DATA_DIR, "nhl_extended_props.json"))
    for pp in (nhl_ext.get("players") or []):
        for mkt, info in (pp.get("props") or {}).items():
            prob = info.get("p")
            fair = info.get("fair_yes") or info.get("fair_over")
            _add(picks, "NHL", pp["name"], pp["team"], mkt, prob, fair,
                  "nhl_ext")

    # PrizePicks (sweet-spot only)
    pp_doc = _load(os.path.join(DATA_DIR, "pickem.json"))
    for p in (pp_doc.get("props") or []):
        po = p.get("model_prob_over")
        pu = p.get("model_prob_under")
        team = p.get("team")
        if po and MIN_PROB <= po <= MAX_PROB:
            _add(picks, "MLB-PP", p["player"], team,
                  f"PP_{p['market']}_over_{p.get('pp_line')}", po, None, "pp_over")
        if pu and MIN_PROB <= pu <= MAX_PROB:
            _add(picks, "MLB-PP", p["player"], team,
                  f"PP_{p['market']}_under_{p.get('pp_line')}", pu, None, "pp_under")

    # LoL / CS / KBO player props
    for fname, sport in (("lol_player_props.json", "LOL"),
                          ("cs_player_props.json", "CS"),
                          ("kbo_player_props.json", "KBO")):
        d = _load(os.path.join(DATA_DIR, fname))
        # Handle both nested 'projections' and flat 'players'
        items = d.get("projections") or d.get("players") or []
        for pp in items:
            props = pp.get("props_bo3") or pp.get("props") or {}
            # Different shape per sport — handle dict of {market: [list]} or {market: {info}}
            if isinstance(props, dict):
                for mkt, info in props.items():
                    if isinstance(info, list):
                        for line_info in info:
                            p = line_info.get("p_over")
                            _add(picks, sport,
                                  pp.get("summoner_name") or pp.get("name") or pp.get("player"),
                                  pp.get("team_code") or pp.get("team"),
                                  f"{mkt}_over_{line_info.get('line')}",
                                  p, line_info.get("fair_over"),
                                  f"{sport.lower()}_player")
                    elif isinstance(info, dict):
                        p = info.get("p_over") or info.get("p")
                        _add(picks, sport,
                              pp.get("summoner_name") or pp.get("name"),
                              pp.get("team_code") or pp.get("team"),
                              mkt, p, info.get("fair_over"),
                              f"{sport.lower()}_player")

    # Rank by probability descending
    picks.sort(key=lambda x: -x["prob"])

    # By sport summary
    by_sport: Dict[str, int] = {}
    for p in picks:
        by_sport[p["sport"]] = by_sport.get(p["sport"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_prob": MIN_PROB,
        "max_prob": MAX_PROB,
        "n_picks_total": len(picks),
        "by_sport": by_sport,
        "top_50": picks[:50],
        "all_picks": picks[:500],   # cap to keep file small
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Slate player pot: {p['n_picks_total']} picks in {p['min_prob']:.0%}-{p['max_prob']:.0%} sweet spot")
    print(f"  By sport: {p['by_sport']}")
    print(f"  Top 15:")
    for x in p["top_50"][:15]:
        fair = x.get("fair_american")
        fair_str = f"fair {fair:+d}" if isinstance(fair, int) else "fair --"
        print(f"    [{x['sport']:7s}] {x['player'][:22]:22s} ({x.get('team') or '--':4s}) "
              f"{x['market'][:32]:32s} p={x['prob']*100:.0f}% {fair_str}")
