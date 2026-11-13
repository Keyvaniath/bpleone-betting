"""
EdgeStat -- today's status, per sport (2026-11-03, P2 website honesty).

One small, always-true file for the homepage: for each sport, how many games
are on the DraftKings board, how many carry a live price, what was picked and
why nothing was -- read from files the pipeline already writes. No new
numbers are made here; every figure is a count of something on disk.

Output: data/today_status.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "today_status.json")
SPORTS = ("NFL", "NBA", "NHL", "MLB")


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _verdict_word(v: str) -> str:
    return (v or "").split(":")[0].strip() or "n/a"


# (2026-11-13) what a held-back game is waiting on, per sport (NBA said "starting goalie")
HOLD_WHY = {"NFL": "QB", "NHL": "starting goalie", "NBA": "day-to-day player"}


def run() -> Dict[str, Any]:
    odds = _load("espn_odds.json")
    desk = (_load("game_lines_desk.json").get("sports") or {})
    today = _load("today.json")
    top = _load("todays_top_plays.json")
    apod = _load("alpha_pick_of_day.json")

    rows = []
    for sp in SPORTS:
        games = [g for g in (odds.get("games") or []) if g.get("sport") == sp and g.get("status") == "pre"]
        priced = [g for g in games if (g.get("market") or {}).get("ml_home") is not None]
        d = desk.get(sp.lower()) or {}
        # (2026-11-13 review) only the games on today's slate: the desk's board also carries the
        # night-before NBA/NHL games (espn_odds.games_next_day), which are not today's
        ids = {str(g.get("event_id")) for g in games}
        board = [r for r in (d.get("board") or []) if str(r.get("event_id")) in ids]
        picks = [r for r in board if r.get("pick")]
        blocked = [r for r in board if r.get("pick_blocked")]
        row = {"sport": sp, "games_on_board": len(games), "games_priced": len(priced),
               "desk_verdict": _verdict_word(d.get("verdict")) if d else None,
               "picks": len(picks), "held_back": len(blocked), "curated": bool(d.get("proven")),
               "next_game": min((g.get("commence_time") for g in games if g.get("commence_time")), default=None)}
        if not games:
            if sp == "MLB" and today.get("no_games"):
                row["status"] = "Off-season -- no MLB games on the board."
            else:
                row["status"] = f"No {sp} games on the DraftKings board right now."
        elif not d:
            row["status"] = f"{len(priced)} games priced; no game-lines model for {sp} yet."
        elif picks:
            row["status"] = (f"{len(priced)} games priced at DraftKings · {len(picks)} pick(s) at the DK price"
                             + (" (forward test -- not in the curated record)" if not d.get("proven") else "")
                             + (f" · {len(blocked)} held back ({HOLD_WHY.get(sp, 'lineup')} not settled)" if blocked else ""))
        else:
            vw = _verdict_word(d.get("verdict"))
            why = ("the model doesn't beat DraftKings' price on this season's games" if vw == "NO EDGE"
                   else "nothing cleared the 4% value bar at the DK price")
            leans = sum(1 for r in board if r.get("lean") and not r.get("pick"))
            row["status"] = (f"{len(priced)} games priced at DraftKings · no picks -- {why}"
                             + (f" · {len(blocked)} held back ({HOLD_WHY.get(sp, 'lineup')} not settled)" if blocked else "")
                             + (f" · {leans} model lean(s) on The Board (not an edge)" if leans else ""))
            row["leans"] = leans
        rows.append(row)

    fun = top.get("funnel") or {}
    rej = fun.get("rejected") or {}
    alpha = apod.get("alpha_pick")
    if alpha:
        alpha_state = {"has_pick": True, "label": f"{alpha.get('player_or_matchup')} {alpha.get('market')}"}
    else:
        n_in = fun.get("n_input") or 0
        n_props = rej.get("unsupported_market") or 0
        n_noq = rej.get("no_quote") or 0
        reason = ("No Alpha Pick today -- nothing qualified at a live sportsbook price."
                  + (f" Of {n_in} candidates, {n_props} were player props (no sportsbook prop prices are "
                     f"available to us) and {n_noq} were game lines without a current DraftKings quote." if n_in else ""))
        alpha_state = {"has_pick": False, "reason": reason}

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "odds_snapshot_at": odds.get("generated_at"),
        "odds_source": "DraftKings via ESPN",
        "sports": rows,
        "alpha": alpha_state,
        "candidate_funnel": fun,
        "props_note": ("Player props are shown as model projections only: none of our odds sources carry "
                       "sportsbook prop prices, so a prop is never a recommended bet."),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    o = run()
    for r in o["sports"]:
        print(f"{r['sport']}: {r['status']}")
    print("Alpha:", o["alpha"].get("label") or o["alpha"].get("reason"))
