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
            "time": g.get("time"), "park": g.get("park"),
            "weather": g.get("weather"), "umpire": g.get("umpire"),
            "model": g.get("model"), "market": g.get("market"),
            "recommendations": g.get("recommendations") or [],
            "pitchers": {"away": _starter("away"), "home": _starter("home")},
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
