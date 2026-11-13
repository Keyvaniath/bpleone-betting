"""
EdgeStat -- pre-game alert system (last-hour high-confidence signal feed).

Walks every sport's state file and surfaces games starting within the
next ~90 minutes that have:
  - Quality-weighted P(home) in sweet spot (55-75% favorite or 25-45% dog)
  - Form alignment: team's L10 record agrees with our model favorite
  - No drift alerts on the pair (model is stable on this matchup)

Output: data/pregame_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "pregame_alerts.json")

SPORTS_TO_SCAN = [
    "nba", "nhl", "wnba", "mls", "epl", "ucl", "nfl",
    "ncaaf", "ncaab", "cws", "kbo",
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _team_form(sport: str, team: str) -> Dict[str, Any]:
    """Return L10 form for a team, or empty if missing."""
    tf = _load(os.path.join(DATA_DIR, f"team_form_{sport}.json"))
    return ((tf.get("teams") or {}).get(team) or {})


_BLOCKED_VERDICTS = ("NO EDGE", "NO_EDGE", "UNPROVEN", "RESEARCH ONLY", "")


def _parse(ts):
    try:
        t = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def run() -> Dict[str, Any]:
    """(2026-11-03) FAIL CLOSED. The old feed read {sport}_state p_home_win with
    `or 0.5`, flagged NCAAB/NCAAF games at the default Elo (1500 vs 1500), and
    printed a model fair price as if it were the line ("HIGH UCLA -179" while DK
    had UCLA +180). An alert is emitted ONLY when the game's probability comes
    from the game-lines desk (p_source == "game_lines_desk"), that desk's verdict
    is not NO EDGE / UNPROVEN, the game is pre-game and not started, and a real
    DraftKings price exists -- shown with its observed time. Otherwise nothing is
    emitted and `reasons` says why."""
    now = dt.datetime.now(dt.timezone.utc)
    alerts: List[Dict[str, Any]] = []
    reasons: Dict[str, Dict[str, int]] = {}

    def _skip(sport, why):
        reasons.setdefault(sport.upper(), {})
        reasons[sport.upper()][why] = reasons[sport.upper()].get(why, 0) + 1

    for sport in SPORTS_TO_SCAN:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        for g in (state.get("games") or []):
            if g.get("state") != "pre":
                _skip(sport, "not pre-game"); continue
            st = _parse(g.get("date"))
            if st is None or st <= now:
                _skip(sport, "started or no start time"); continue
            if g.get("p_source") != "game_lines_desk":
                _skip(sport, "no validated model probability (not from the game-lines desk)"); continue
            verdict = str(g.get("desk_verdict") or "").upper()
            if verdict in _BLOCKED_VERDICTS:
                _skip(sport, f"desk verdict {verdict or 'missing'}"); continue
            ph = g.get("p_home_display")
            if ph is None:
                _skip(sport, "no desk probability"); continue
            ph = float(ph)
            side = "HOME" if ph >= 0.5 else "AWAY"
            dk = g.get("dk_ml_home") if side == "HOME" else g.get("dk_ml_away")
            if dk is None:
                _skip(sport, "no DraftKings price"); continue
            home, away = g.get("home_team"), g.get("away_team")
            team, opp = (home, away) if side == "HOME" else (away, home)
            prob = ph if side == "HOME" else 1 - ph
            home_form = _team_form(sport, home)
            away_form = _team_form(sport, away)
            alerts.append({
                "sport": sport.upper(),
                "matchup": g.get("matchup"),
                "game_time": g.get("date"),
                "side": side,
                "team": team,
                "opponent": opp,
                "p_pick_side": round(prob, 4),
                "p_source": "game_lines_desk",
                "desk_verdict": g.get("desk_verdict"),
                "dk_american": int(dk),
                "odds_observed_at": g.get("odds_observed_at"),
                "team_l10": (home_form.get("L10") or {}).get("record") if side == "HOME"
                            else (away_form.get("L10") or {}).get("record"),
            })

    alerts.sort(key=lambda a: -a["p_pick_side"])
    by_sport: Dict[str, int] = {}
    for a in alerts:
        by_sport[a["sport"]] = (by_sport.get(a["sport"]) or 0) + 1

    note = None
    if not alerts:
        top = []
        for sp, rs in reasons.items():
            k, v = max(rs.items(), key=lambda kv: kv[1])
            top.append(f"{sp}: {v} {k}")
        note = ("No pre-game alerts: an alert needs a game-lines-desk probability whose verdict "
                "passed (not NO EDGE / UNPROVEN) and a DraftKings price. " + "; ".join(top))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "rule": "game-lines desk probability + passing desk verdict + DraftKings price, pre-game only",
        "n_alerts": len(alerts),
        "by_confidence": {},
        "by_sport": by_sport,
        "reasons": reasons,
        "note": note,
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Pre-game alerts: {p['n_alerts']} total")
    if p["note"]:
        print("  " + p["note"])
    for a in p["alerts"][:10]:
        print(f"  {a['sport']:5} {a['team']} {a['side']} P={a['p_pick_side']*100:.1f}% DK {a['dk_american']:+d} ({a['desk_verdict']})")
