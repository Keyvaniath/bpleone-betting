"""
EdgeStat -- ESPN results feed for INDIVIDUAL / MATCH sports (golf, tennis, UFC).

The grading adapter's box-score layer (espn_box_logs) handles team sports with
per-player stat lines. Golf / tennis / UFC settle on a different shape -- a
tournament finish position, a match winner, a fight result -- so their picks sat
pending and voided. This produces those simple outcomes so they settle + learn.

Outputs:
  data/golf_results.json   -> {tournaments: [{name, start_date, end_date,
                               results: {player: {position, made_cut, to_par}}}]}
  data/tennis_results.json -> {matches: [{date, p1, p2, winner, total_games, sets}]}
  data/ufc_results.json    -> {fights: [{date, f1, f2, winner, method, round}]}

position is tie-aware (re-ranked by to-par among players who completed all rounds;
cut/withdrawn -> 999). All free ESPN public endpoints, no auth.
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GOLF_SB = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
UFC_SB = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
TENNIS_SB = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
TENNIS_TOURS = ["atp", "wta"]
F1_SB = "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"
SOCCER_SB = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard"
# ESPN league codes. EPL/MLS/UCL carry picks today; the big-5 + Europa are
# fetched too so the feed is ready the moment those generators surface picks.
SOCCER_LEAGUES = ["eng.1", "usa.1", "uefa.champions", "uefa.europa",
                  "esp.1", "ita.1", "ger.1", "fra.1",
                  "fifa.world"]  # 2026 World Cup (June 11 - July 19)


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _dates(days_back: int, anchor: dt.date) -> List[str]:
    return [(anchor - dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(days_back + 1)]


def _to_par(s: Any) -> Optional[int]:
    """'-13' -> -13, '+2' -> 2, 'E'/'EVEN' -> 0, else None."""
    t = str(s or "").strip().upper()
    if t in ("E", "EVEN", "0"):
        return 0
    try:
        return int(t.replace("+", ""))
    except Exception:
        return None


def _name(ath: Dict[str, Any]) -> str:
    return (ath.get("fullName") or ath.get("displayName") or ath.get("shortName") or "").strip()


# ---------------------------------------------------------------- GOLF --------
def _golf_results_for_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Tie-aware finish positions from a completed tournament's competitors."""
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    field = []
    for c in competitors:
        nm = _name(c.get("athlete") or {})
        if not nm:
            continue
        # Count only real 18-hole rounds (score >= 50). ESPN appends playoff-hole
        # rows (value ~3) and null padding to the leaders' linescores, so a raw
        # len() over-counts and would mark made-cut players as unfinished.
        ls = c.get("linescores") or []
        real_rounds = sum(1 for x in ls
                          if isinstance(x.get("value"), (int, float)) and x.get("value") >= 50)
        field.append({"name": nm, "to_par": _to_par(c.get("score")), "rounds": real_rounds})
    max_rounds = max((f["rounds"] for f in field), default=0)
    finished = [f for f in field if f["rounds"] >= max_rounds and f["to_par"] is not None and max_rounds > 0]
    results: Dict[str, Any] = {}
    for f in field:
        if f in finished:
            pos = 1 + sum(1 for o in finished if o["to_par"] < f["to_par"])  # tie-aware
            results[f["name"].lower()] = {"player": f["name"], "position": pos,
                                          "made_cut": True, "to_par": f["to_par"]}
        else:
            results[f["name"].lower()] = {"player": f["name"], "position": 999,
                                          "made_cut": False, "to_par": f["to_par"]}
    return results


def fetch_golf(days_back: int = 16, anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    anchor = anchor or dt.date.today()
    seen: Dict[str, Dict[str, Any]] = {}
    for d in _dates(days_back, anchor):
        lb = _http(f"{GOLF_SB}?dates={d}")
        for ev in ((lb or {}).get("events") or []):
            st = (ev.get("status") or {}).get("type", {})
            if not st.get("completed"):
                continue
            name = ev.get("name") or ev.get("shortName") or ""
            if not name or name in seen:
                continue
            res = _golf_results_for_event(ev)
            if res:
                seen[name] = {"name": name, "start_date": (ev.get("date") or "")[:10],
                              "end_date": (ev.get("endDate") or ev.get("date") or "")[:10],
                              "n_players": len(res), "results": res}
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "n_tournaments": len(seen), "tournaments": list(seen.values())}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "golf_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


# -------------------------------------------------------------- TENNIS --------
def fetch_tennis(days_back: int = 4, anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    anchor = anchor or dt.date.today()
    # ESPN returns a tournament's whole completed draw regardless of the date
    # param, so floor to the settle window to keep the feed lean + relevant.
    min_date = (anchor - dt.timedelta(days=days_back)).isoformat()
    matches: List[Dict[str, Any]] = []
    seen = set()
    for tour in TENNIS_TOURS:
        for d in _dates(days_back, anchor):
            lb = _http(TENNIS_SB.format(tour=tour) + f"?dates={d}")
            for ev in ((lb or {}).get("events") or []):
                # Tennis nests matches under events[].groupings[].competitions[]
                # (one event = a tournament; each grouping = a draw / round).
                comps = []
                for grp in (ev.get("groupings") or []):
                    comps.extend(grp.get("competitions") or [])
                comps.extend(ev.get("competitions") or [])
                for comp in comps:
                    st = (comp.get("status") or {}).get("type", {})
                    if not st.get("completed"):
                        continue
                    cs = comp.get("competitors") or []
                    if len(cs) != 2:        # singles only (doubles have team entries)
                        continue
                    a, b = cs[0], cs[1]
                    na, nb = _name(a.get("athlete") or {}), _name(b.get("athlete") or {})
                    if not na or not nb:
                        continue
                    mdate = (comp.get("date") or ev.get("date") or "")[:10]
                    if mdate and mdate < min_date:
                        continue
                    key = (tour, mdate, na.lower(), nb.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    winner = na if a.get("winner") is True else nb if b.get("winner") is True else None
                    games_a = sum(int(x.get("value") or 0) for x in (a.get("linescores") or []))
                    games_b = sum(int(x.get("value") or 0) for x in (b.get("linescores") or []))
                    sets_a = sum(1 for x, y in zip(a.get("linescores") or [], b.get("linescores") or [])
                                 if (x.get("value") or 0) > (y.get("value") or 0))
                    sets_b = sum(1 for x, y in zip(a.get("linescores") or [], b.get("linescores") or [])
                                 if (y.get("value") or 0) > (x.get("value") or 0))
                    matches.append({"date": mdate, "tour": tour.upper(),
                                    "p1": na, "p2": nb, "winner": (winner or "").lower(),
                                    "winner_name": winner, "total_games": games_a + games_b,
                                    "sets": f"{sets_a}-{sets_b}", "sets_won_by_winner": max(sets_a, sets_b)})
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "n_matches": len(matches), "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "tennis_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


# ----------------------------------------------------------------- UFC --------
def fetch_ufc(days_back: int = 10, anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    anchor = anchor or dt.date.today()
    fights: List[Dict[str, Any]] = []
    seen = set()
    for d in _dates(days_back, anchor):
        lb = _http(f"{UFC_SB}?dates={d}")
        for ev in ((lb or {}).get("events") or []):
            for comp in (ev.get("competitions") or []):
                st = (comp.get("status") or {}).get("type", {})
                if not st.get("completed"):
                    continue
                cs = comp.get("competitors") or []
                if len(cs) != 2:
                    continue
                a, b = cs[0], cs[1]
                na, nb = _name(a.get("athlete") or {}), _name(b.get("athlete") or {})
                if not na or not nb:
                    continue
                date = (comp.get("date") or ev.get("date") or "")[:10]
                key = (date, na.lower(), nb.lower())
                if key in seen:
                    continue
                seen.add(key)
                winner = na if a.get("winner") is True else nb if b.get("winner") is True else None
                # method / round live on the status detail.
                stat = comp.get("status") or {}
                method = (stat.get("type") or {}).get("description") or stat.get("result")
                rnd = stat.get("period")
                fights.append({"date": date, "f1": na, "f2": nb,
                               "winner": (winner or "").lower(), "winner_name": winner,
                               "method": method, "round": rnd})
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "n_fights": len(fights), "fights": fights}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "ufc_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


# ----------------------------------------------------------------- F1 ---------
def _f1_positions(comp: Dict[str, Any]) -> Dict[str, Any]:
    """driver -> finishing order from an F1 session's competitors (order 1 = P1)."""
    res: Dict[str, Any] = {}
    for c in (comp.get("competitors") or []):
        nm = _name(c.get("athlete") or {})
        pos = c.get("order")
        if nm and pos is not None:
            try:
                res[nm.lower()] = {"driver": nm, "position": int(pos)}
            except Exception:
                pass
    return res


def fetch_f1(days_back: int = 14, anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    anchor = anchor or dt.date.today()
    seen: Dict[str, Dict[str, Any]] = {}
    for d in _dates(days_back, anchor):
        lb = _http(f"{F1_SB}?dates={d}")
        for ev in ((lb or {}).get("events") or []):
            name = ev.get("name") or ev.get("shortName") or ""
            if not name or name in seen:
                continue
            qual, race, qdate, rdate = {}, {}, "", ""
            for c in (ev.get("competitions") or []):
                t = (c.get("type") or {}).get("abbreviation")
                if not ((c.get("status") or {}).get("type", {}).get("completed")):
                    continue
                if t == "Qual":
                    qual, qdate = _f1_positions(c), (c.get("date") or "")[:10]
                elif t == "Race":
                    race, rdate = _f1_positions(c), (c.get("date") or "")[:10]
            if qual or race:
                seen[name] = {"name": name, "event_date": (ev.get("date") or "")[:10],
                              "qual_date": qdate, "race_date": rdate, "qual": qual, "race": race}
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "n_events": len(seen), "events": list(seen.values())}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "f1_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


# --------------------------------------------------------------- SOCCER -------
def _soccer_match(comp: Dict[str, Any], league: str, date: str) -> Optional[Dict[str, Any]]:
    """Final score + goal scorers + total cards from a completed match. ESPN's
    competition.details lists every goal (scoringPlay, athletesInvolved) and every
    booking (type 'Yellow/Red Card') -- verified complete (detail-goals == score)."""
    cs = comp.get("competitors") or []
    home = next((c for c in cs if c.get("homeAway") == "home"), None)
    away = next((c for c in cs if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    def _nm(c):
        return ((c.get("team") or {}).get("displayName") or "").strip()

    def _sc(c):
        try:
            return int(c.get("score") or 0)
        except Exception:
            return 0

    scorers: List[str] = []
    cards = 0
    for d in (comp.get("details") or []):
        ttype = ((d.get("type") or {}).get("text") or "").lower()
        if "card" in ttype:
            cards += 1
        elif d.get("scoringPlay") and "own" not in ttype:   # own goals don't count for a scorer
            for a in (d.get("athletesInvolved") or []):
                nm = (a.get("displayName") or "").strip()
                if nm:
                    scorers.append(nm.lower())
    hn, an = _nm(home), _nm(away)
    if not hn or not an:
        return None
    return {"date": date, "league": league, "home": hn, "away": an,
            "home_score": _sc(home), "away_score": _sc(away),
            "total_goals": _sc(home) + _sc(away), "total_cards": cards,
            "scorers": scorers}


def fetch_soccer(days_back: int = 6, anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    anchor = anchor or dt.date.today()
    matches: List[Dict[str, Any]] = []
    seen = set()
    for lg in SOCCER_LEAGUES:
        for d in _dates(days_back, anchor):
            lb = _http(SOCCER_SB.format(lg=lg) + f"?dates={d}")
            for ev in ((lb or {}).get("events") or []):
                comp = (ev.get("competitions") or [{}])[0]
                if not (comp.get("status") or {}).get("type", {}).get("completed"):
                    continue
                mdate = (comp.get("date") or ev.get("date") or "")[:10]
                m = _soccer_match(comp, lg, mdate)
                if not m:
                    continue
                key = (mdate, m["home"].lower(), m["away"].lower())
                if key in seen:
                    continue
                seen.add(key)
                matches.append(m)
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
           "n_matches": len(matches), "matches": matches}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "soccer_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


def run_all(anchor: Optional[dt.date] = None) -> Dict[str, Any]:
    g = fetch_golf(anchor=anchor)
    t = fetch_tennis(anchor=anchor)
    u = fetch_ufc(anchor=anchor)
    f = fetch_f1(anchor=anchor)
    s = fetch_soccer(anchor=anchor)
    return {"golf_tournaments": g["n_tournaments"], "tennis_matches": t["n_matches"],
            "ufc_fights": u["n_fights"], "f1_events": f["n_events"],
            "soccer_matches": s["n_matches"]}


if __name__ == "__main__":
    import sys
    which = (sys.argv[1].lower() if len(sys.argv) > 1 else "all")
    anchor = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    if which == "golf":
        r = fetch_golf(anchor=anchor); print(f"[golf] {r['n_tournaments']} tournaments -> golf_results.json")
    elif which == "tennis":
        r = fetch_tennis(anchor=anchor); print(f"[tennis] {r['n_matches']} matches -> tennis_results.json")
    elif which == "ufc":
        r = fetch_ufc(anchor=anchor); print(f"[ufc] {r['n_fights']} fights -> ufc_results.json")
    elif which == "f1":
        r = fetch_f1(anchor=anchor); print(f"[f1] {r['n_events']} events -> f1_results.json")
    elif which == "soccer":
        r = fetch_soccer(anchor=anchor); print(f"[soccer] {r['n_matches']} matches -> soccer_results.json")
    else:
        r = run_all(anchor=anchor); print(f"[event-results] {r}")
