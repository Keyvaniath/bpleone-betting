"""
EdgeStat -- daily picks CSV/JSON export.

Aggregates every actionable pick from across the system into a single
downloadable file. Includes:
  - MLB POD + DK + PP top picks
  - Golf POT + parlays + H2H
  - LoL POT + parlays + player props
  - CS POD + map handicap + player props
  - KBO POD + pitcher matchups
  - NBA, NHL, WNBA, MLS, EPL, UCL, NFL, NCAAF, NCAAB, CWS top ML candidates
  - Cross-sport player POT

Output: data/picks_export.csv + data/picks_export.json
"""
from __future__ import annotations
import os, csv, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_PATH = os.path.join(DATA_DIR, "picks_export.csv")
JSON_PATH = os.path.join(DATA_DIR, "picks_export.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _add(pick: Dict[str, Any], picks: List[Dict[str, Any]]):
    """Normalize before add."""
    picks.append({
        "sport": pick.get("sport"),
        "kind": pick.get("kind"),
        "label": pick.get("label"),
        "player_or_team": pick.get("player_or_team"),
        "market": pick.get("market"),
        "play": pick.get("play"),
        "line": pick.get("line"),
        "model_prob": pick.get("model_prob"),
        "fair_american": pick.get("fair_american"),
        "confidence": pick.get("confidence"),
        "quality_score": pick.get("quality_score"),
        "edge_pct": pick.get("edge_pct"),
        "source_file": pick.get("source_file"),
    })


def run() -> Dict[str, Any]:
    picks: List[Dict[str, Any]] = []

    # MLB POD
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pod = today.get("play_of_day") or {}
    if pod:
        _add({
            "sport": "MLB", "kind": "POD",
            "label": f"{pod.get('matchup','')} {pod.get('play','')}",
            "player_or_team": pod.get("matchup"),
            "market": pod.get("market"), "play": pod.get("play"),
            "model_prob": pod.get("model_prob"),
            "fair_american": pod.get("model_price"),
            "confidence": pod.get("confidence"),
            "edge_pct": pod.get("edge_pct"),
            "source_file": "today.json",
        }, picks)

    # Golf POT
    golf_bb = _load(os.path.join(DATA_DIR, "golf_bestbet.json"))
    if golf_bb.get("top_bet"):
        gp = golf_bb["top_bet"]
        _add({
            "sport": "GOLF", "kind": gp.get("type"),
            "label": f"{gp.get('player','')} {gp.get('type','')}",
            "player_or_team": gp.get("player"),
            "market": gp.get("type"), "play": gp.get("type"),
            "model_prob": gp.get("model_prob"),
            "fair_american": gp.get("fair_american"),
            "confidence": gp.get("confidence"),
            "quality_score": gp.get("quality"),
            "source_file": "golf_bestbet.json",
        }, picks)

    # Sport POTs (LoL, CS, KBO)
    for sport, file in (("LOL","lol_bestbet.json"),("CS","cs_bestbet.json"),("KBO","kbo_bestbet.json")):
        bb = _load(os.path.join(DATA_DIR, file))
        if bb.get("top_bet"):
            tb = bb["top_bet"]
            _add({
                "sport": sport, "kind": tb.get("kind", "ML"),
                "label": tb.get("label",""),
                "player_or_team": tb.get("team") or tb.get("player"),
                "market": tb.get("kind", "ML"),
                "play": tb.get("kind", "ML"),
                "line": tb.get("line"),
                "model_prob": tb.get("prob"),
                "fair_american": tb.get("fair_american"),
                "confidence": tb.get("confidence"),
                "quality_score": tb.get("quality"),
                "source_file": file,
            }, picks)

    # Multi-sport top
    mst = _load(os.path.join(DATA_DIR, "multi_sport_top.json"))
    for p in (mst.get("picks") or []):
        _add({
            "sport": p.get("sport"),
            "kind": "MULTI_SPORT_TOP",
            "label": p.get("label", ""),
            "player_or_team": p.get("player_or_team"),
            "market": p.get("play") or "TOP",
            "play": p.get("play"),
            "model_prob": p.get("model_prob"),
            "fair_american": p.get("fair_american"),
            "confidence": p.get("confidence"),
            "source_file": "multi_sport_top.json",
        }, picks)

    # Player POT
    ppot = _load(os.path.join(DATA_DIR, "player_pot.json"))
    for c in (ppot.get("top_5") or []):
        _add({
            "sport": c.get("sport"),
            "kind": "PLAYER_POT",
            "label": c.get("label", ""),
            "player_or_team": c.get("player"),
            "market": c.get("market"),
            "play": c.get("play"),
            "line": c.get("line"),
            "model_prob": c.get("prob"),
            "fair_american": c.get("fair_american"),
            "quality_score": c.get("quality_score"),
            "source_file": "player_pot.json",
        }, picks)

    # Team-sport ML candidates from each ESPN-driven sport (top 3 per sport with edge)
    SPORTS = [("NBA", "nba_state.json"), ("NHL", "nhl_state.json"),
              ("WNBA", "wnba_state.json"), ("MLS", "mls_state.json"),
              ("EPL", "epl_state.json"), ("UCL", "ucl_state.json"),
              ("NFL", "nfl_state.json"), ("NCAAF", "ncaaf_state.json"),
              ("NCAAB", "ncaab_state.json"), ("CWS", "cws_state.json"),
              ("KBO", "kbo_state.json")]
    def _has_signal(g):
        """Skip preseason 0-0 vs 0-0 games where the only edge is HFA (not actionable)."""
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

    for sport, file in SPORTS:
        d = _load(os.path.join(DATA_DIR, file))
        for g in (d.get("games") or [])[:3]:
            if g.get("state") == "post": continue
            if not _has_signal(g): continue   # skip preseason 0-0 teams
            ph = g.get("p_home_win")
            if ph is None: continue
            side = "HOME" if ph >= 0.5 else "AWAY"
            team = g.get("home_team") if side == "HOME" else g.get("away_team")
            opp = g.get("away_team") if side == "HOME" else g.get("home_team")
            fair = g.get("fair_home_american") if side == "HOME" else g.get("fair_away_american")
            prob = ph if side == "HOME" else 1 - ph
            if not (0.50 <= prob <= 0.80):  # skip extreme + coinflip
                continue
            _add({
                "sport": sport, "kind": "ML",
                "label": f"{sport} {team} ML vs {opp}",
                "player_or_team": team,
                "market": f"{sport.lower()}_ml",
                "play": side,
                "model_prob": prob,
                "fair_american": fair,
                "source_file": file,
            }, picks)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_picks": len(picks),
        "by_sport": {s: sum(1 for p in picks if p["sport"] == s) for s in set(p["sport"] for p in picks if p["sport"])},
        "picks": picks,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    # CSV export
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        if picks:
            cols = ["sport", "kind", "label", "player_or_team", "market", "play",
                    "line", "model_prob", "fair_american", "confidence",
                    "quality_score", "edge_pct", "source_file"]
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for p in picks:
                writer.writerow(p)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Picks export: {p['n_picks']} picks")
    print(f"  by sport: {p['by_sport']}")
    print(f"  Wrote: {CSV_PATH}")
    print(f"  Wrote: {JSON_PATH}")
