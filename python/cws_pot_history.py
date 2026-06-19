"""
EdgeStat -- NCAA Baseball (College World Series) pick history + settlement.

The cws desk prices each game (cws_state.games carries p_home_win + fair odds)
but nothing settled, so it never tracked a record. This snapshots the model's
moneyline lean per game and settles it from ESPN's free college-baseball feed --
fetched by EVENT ID (so a finished game never drops off the daily scoreboard the
way a date-based fetch would). Flat 1u per pick, exactly what was modeled.

Output: data/cws_pot_history.json  (sport_coverage reads this -> CWS shows a
record instead of "no outcome feed yet").
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE = os.path.join(DATA_DIR, "cws_state.json")
OUT = os.path.join(DATA_DIR, "cws_pot_history.json")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/summary?event={id}"
UA = {"User-Agent": "Mozilla/5.0"}
MAX_HISTORY = 400


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def _amer_to_dec(a) -> Optional[float]:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return None
    return 1 + a / 100 if a >= 0 else 1 + 100 / abs(a)


def _result(game_id: str) -> Optional[Dict[str, Any]]:
    """Final from ESPN by event id, or None if not completed yet."""
    d = _http(SUMMARY.format(id=game_id))
    if not d:
        return None
    comp = (((d.get("header") or {}).get("competitions")) or [{}])[0]
    st = ((comp.get("status") or {}).get("type") or {})
    if not st.get("completed"):
        return None
    cs = comp.get("competitors") or []
    home = next((c for c in cs if c.get("homeAway") == "home"), {})
    away = next((c for c in cs if c.get("homeAway") == "away"), {})
    try:
        hs, as_ = int(home.get("score") or 0), int(away.get("score") or 0)
    except (TypeError, ValueError):
        return None
    winner = "home" if hs > as_ else ("away" if as_ > hs else "push")
    return {"winner": winner, "home_score": hs, "away_score": as_}


def run() -> Dict[str, Any]:
    state = _load(STATE)
    hist: List[Dict[str, Any]] = _load(OUT).get("history") or []
    seen = {str(h.get("game_id")) for h in hist}

    # Snapshot each priced game's moneyline lean (once per game id).
    for g in (state.get("games") or []):
        gid = str(g.get("id") or "")
        if not gid or gid in seen:
            continue
        ph = g.get("p_home_win")
        if ph is None:
            continue
        side = "home" if ph >= 0.5 else "away"
        fair = g.get("fair_home_american") if side == "home" else g.get("fair_away_american")
        team = g.get("home_abbrev") if side == "home" else g.get("away_abbrev")
        hist.append({
            "game_id": gid, "date": (g.get("date") or "")[:10], "matchup": g.get("matchup"),
            "side": side, "team": team,
            "prob": round(ph if side == "home" else 1 - ph, 4),
            "fair_american": fair,
            "settled": False, "outcome": "PENDING",
            "added_at": dt.datetime.now().isoformat(timespec="seconds"),
        })
        seen.add(gid)

    # Settle pending picks from ESPN (by id).
    n_settled_run = 0
    for e in hist:
        if e.get("settled"):
            continue
        r = _result(e["game_id"])
        if not r:
            continue
        if r["winner"] == "push":
            e.update(settled=True, outcome="PUSH", pl_units=0.0)
        else:
            won = r["winner"] == e["side"]
            dec = _amer_to_dec(e.get("fair_american")) or 1.91
            e.update(settled=True, outcome="WIN" if won else "LOSS",
                     pl_units=round((dec - 1) if won else -1.0, 3),
                     actual=f"{r['away_score']}-{r['home_score']}",
                     settled_at=dt.datetime.now().isoformat(timespec="seconds"))
        n_settled_run += 1

    hist = hist[-MAX_HISTORY:]
    settled = [h for h in hist if h.get("settled")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    losses = sum(1 for h in settled if h.get("outcome") == "LOSS")
    net = round(sum(h.get("pl_units", 0) for h in settled), 2)
    decided = wins + losses

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": "NCAA Baseball",
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "n_settled_this_run": n_settled_run,
        "wins": wins, "losses": losses,
        "record": f"{wins}-{losses}" if decided else None,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(net / decided * 100, 2) if decided else None,
        "stake_assumption": "1u flat per game (model ML lean), settled off ESPN finals by id",
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[cws-history] {p['total_pots']} picks, {p['n_settled']} settled, {p['n_pending']} pending "
          f"(+{p['n_settled_this_run']} this run)")
    if p["record"]:
        print(f"  Record {p['record']} ({(p['hit_rate'] or 0)*100:.0f}%) net {p['net_units']:+.2f}u ROI {p['roi_pct']:+.1f}%")
    for h in p["history"][:5]:
        print(f"    {h['date']} {h.get('matchup','')[:34]:34s} {h['team']} ML -> {h['outcome']}")
