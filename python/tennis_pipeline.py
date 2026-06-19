"""
EdgeStat -- TENNIS pipeline (the missing input feed).

The tennis desk has 12 prop modules (match-win, aces, double-faults, set score,
tiebreak, breaks, 1st-set, dominance/upset alerts, confluence) -- ALL of which
read data/tennis_state.json for the upcoming slate. But nothing ever WROTE that
file, so every board came up empty. ESPN already serves a free tennis scoreboard
(it's where tennis_results.json comes from); this pulls the UPCOMING ATP/WTA
matches from the same endpoint and writes tennis_state.json, lighting up the
whole desk.

ESPN nests matches under events[].groupings[].competitions[] with a per-match
status.type.state of pre / in / post. We keep pre + in (upcoming/live), pull both
players from competitors[].athlete.displayName, and infer the surface from the
tournament name (ESPN exposes no surface field).

Output: data/tennis_state.json
  { generated_at, data_source, n_matches, tours, matches: [
      {match_id, tour, tournament, surface, round, player1, player2,
       state, status, start_time} ] }
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "tennis_state.json")
SB = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={d}"
TOURS = ["atp", "wta"]

# Surface inference from tournament name -- ESPN carries no surface field. Covers
# the current calendar's events; anything unmatched defaults to hard.
GRASS = ("halle", "terra wortmann", "queen", "cinch", "hsbc championships",
         "berlin", "eastbourne", "mallorca", "bad homburg", "hertogenbosch",
         "libema", "rosmalen", "stuttgart", "nottingham", "wimbledon")
CLAY = ("roland garros", "french open", "madrid", "rome", "internazionali",
        "monte", "barcelona", "hamburg", "kitzbuhel", "gstaad", "bastad",
        "umag", "bucharest", "estoril", "munich", "geneva", "lyon")


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def _surface(tournament: Optional[str]) -> str:
    t = (tournament or "").lower()
    if any(g in t for g in GRASS):
        return "grass"
    if any(c in t for c in CLAY):
        return "clay"
    return "hard"


def _pull(day: dt.date) -> List[Dict[str, Any]]:
    ds = day.strftime("%Y%m%d")
    out: List[Dict[str, Any]] = []
    for tour in TOURS:
        j = _http(SB.format(tour=tour, d=ds))
        if not j:
            continue
        for e in (j.get("events") or []):
            tourn = e.get("name")
            surf = _surface(tourn)
            for g in (e.get("groupings") or []):
                for c in (g.get("competitions") or []):
                    typ = (c.get("status") or {}).get("type") or {}
                    st = (typ.get("state") or "").lower()
                    if st not in ("pre", "in"):       # upcoming / live only -- no lookahead on finals
                        continue
                    names = [((x.get("athlete") or {}).get("displayName") or "").strip()
                             for x in (c.get("competitors") or [])]
                    names = [n for n in names if n]
                    if len(names) != 2:               # singles only (skip doubles/TBD)
                        continue
                    out.append({
                        "match_id": str(c.get("id") or ""),
                        "tour": tour.upper(),
                        "tournament": tourn,
                        "surface": surf,
                        "round": typ.get("shortDetail") or e.get("shortName"),
                        "player1": names[0],
                        "player2": names[1],
                        "state": "in" if st == "in" else "pre",
                        "status": st,
                        "start_time": c.get("date"),
                    })
    return out


def run() -> Dict[str, Any]:
    today = dt.date.today()
    # ESPN's tennis scoreboard is tournament-scoped (returns the whole bracket),
    # but query today + the next two days so a tournament that flips its calendar
    # day mid-window is still captured. Dedup by ESPN competition id.
    seen: set = set()
    matches: List[Dict[str, Any]] = []
    for off in (0, 1, 2):
        for m in _pull(today + dt.timedelta(days=off)):
            k = m["match_id"] or f'{m["player1"]}|{m["player2"]}|{m["start_time"]}'
            if k in seen:
                continue
            seen.add(k)
            matches.append(m)

    matches.sort(key=lambda m: (m.get("start_time") or ""))
    tours = sorted({m["tour"] for m in matches})
    tournaments = sorted({m["tournament"] for m in matches if m.get("tournament")})

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "data_source": "espn_tennis" if matches else "espn_tennis (no upcoming matches)",
        "n_matches": len(matches),
        "tours": tours,
        "tournaments": tournaments,
        "matches": matches,
        "note": (f"{len(matches)} upcoming ATP/WTA matches across {len(tournaments)} "
                 f"event(s) from ESPN." if matches else
                 "No upcoming ATP/WTA matches on the ESPN board (between tournaments)."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[tennis-pipeline] {p['n_matches']} upcoming matches "
          f"({', '.join(p['tours']) or '-'}) across {len(p['tournaments'])} events -> {OUT_PATH}")
    for m in p["matches"][:8]:
        print(f"  {m['tour']} {m['surface']:5s} {m['player1']} vs {m['player2']}  ({m.get('tournament')})")
