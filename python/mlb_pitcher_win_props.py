"""
EdgeStat -- MLB pitcher win yes/no prop.

Common DK line: "Pitcher to record the win" (typical -110 to +180 each side).
A pitcher gets credited the win if:
  - His team wins
  - He pitches at least 5 innings
  - He leaves the game with his team leading
  - He's the pitcher of record at that lead transition

We approximate:
  P(pitcher_win) = P(team_wins) * P(pitcher_qualifies_for_decision)
                 * P(team_leads_when_pitcher_exits | team_wins)

  P(team_wins) from model.p_home_win / p_away_win
  P(qualify) ~ avg_IP / 6.0 (need at least 5 IP, league avg ~5.5 IP)
                       capped at 0.85 (max realistic chance of going 5+)
  P(team_leads_at_exit | team_wins) ~ 0.65 (most pitcher-of-record wins
                                            come from leading at exit)

  Net: pitcher_win_prob ~ team_p * 0.55 (empirical)

Surface STRONG_YES when our p >= 0.55 (vs -120 book = 54.5% breakeven).

Output: data/mlb_pitcher_win_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_win_props.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    # Index today's model game probabilities
    model_by_key = {}
    for g in (today.get("games") or []):
        k = g.get("matchup") or g.get("gamePk")
        if k: model_by_key[k] = g

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup")
        if not matchup: continue
        model_g = model_by_key.get(matchup) or {}
        nested = model_g.get("model") or {}
        p_home_win = _safe(nested.get("p_home_win") or model_g.get("p_home_win"), None) or 0.5
        if p_home_win == 0.5 and not (nested.get("p_home_win") or model_g.get("p_home_win")):
            continue   # no model probability available
        p_away_win = 1 - p_home_win

        for side, side_team_win_p, sp_field in (
            ("HOME", p_home_win, "home_pitcher"),
            ("AWAY", p_away_win, "away_pitcher"),
        ):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_row = p_by_name.get(sp_name.lower(), {})
            stats = sp_row.get("stats") or {}
            avg_ip = _safe(stats.get("avg_ip"), 5.2)

            # Qualify factor: needs >= 5 IP for decision
            # avg_ip 6.0 -> 0.85 (very likely), 5.0 -> 0.55, 4.5 -> 0.35
            qualify = max(0.20, min(0.90, (avg_ip - 4.0) * 0.35 + 0.20))
            # Lead-at-exit | team wins: ~0.65 empirical
            lead_at_exit = 0.65

            p_pitcher_win = side_team_win_p * qualify * lead_at_exit
            p_no_win = 1 - p_pitcher_win

            edge_class = "NONE"
            best_market = None
            # STRONG_YES at p >= 0.55 (vs -120 book breakeven 54.5%)
            if p_pitcher_win >= 0.55 and p_pitcher_win <= 0.75:
                edge_class = "STRONG_YES"
                best_market = {"market": "PITCHER_WIN_YES", "p": round(p_pitcher_win, 3),
                               "fair_odds": _american(p_pitcher_win)}
            elif p_no_win >= 0.78:
                edge_class = "STRONG_NO"
                best_market = {"market": "PITCHER_WIN_NO", "p": round(p_no_win, 3),
                               "fair_odds": _american(p_no_win)}

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "team_win_prob": round(side_team_win_p, 3),
                "avg_ip": round(avg_ip, 2),
                "qualify_factor": round(qualify, 3),
                "p_pitcher_win": round(p_pitcher_win, 3),
                "p_no_win": round(p_no_win, 3),
                "fair_yes_odds": _american(p_pitcher_win),
                "fair_no_odds": _american(p_no_win),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_pitcher_win"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(pitcher_win) = P(team_wins) x qualify_factor (avg_IP based) "
                       "x 0.65 (lead-at-exit | team wins). STRONG_YES p in [0.55, 0.75], "
                       "STRONG_NO p_no >= 78%.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-win] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong edges -> {OUT}")
