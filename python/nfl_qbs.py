"""
EdgeStat -- NFL quarterback adjustments for the game-lines desk (2026-10-29).

WHY: the NFL desk's Elo rates a team on its scores, which mixes the roster
with whoever played QB. The QB is the biggest single swing in an NFL price.
On 10/28 the desk logged PHI +195 at WSH with Jalen Hurts out (Tanner McKee
started PHI's last game) -- the "edge" was the market pricing the backup.
This module is the NFL analogue of nhl_goalies.py:

  1. QB VALUE -- adjusted net yards per dropback (ANY/A: pass yds + 20*TD
     - 45*INT - sack yds, over attempts + sacks) from every ESPN boxscore since
     last season, shrunk toward REPLACEMENT level (league ANY/A - REPL_GAP)
     with a PRIOR_DB-dropback prior: an unknown backup is a backup, not an
     average starter. Seasons carry over at SEASON_CARRY.
  2. EDGE -- starter value minus the team's last-8-starts average, times
     dropbacks per game: Elo already contains the usual QB, only the change
     counts.
  3. WHO STARTS -- the team's last starter / regular (most starts in its last
     8) checked against ESPN's injury report (game summary `injuries`). A QB
     listed Out / Doubtful / IR doesn't start; a Questionable starter, or a
     regular-vs-last-starter conflict the report can't settle, makes the game
     UNCERTAIN and the desk won't pick it.

Data: data/nfl_qb_games.json (seeded by tools/build_nfl_qb_seed.py, grown
each run from the last week's finals; network failures are non-fatal).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATH = os.path.join(DATA_DIR, "nfl_qb_games.json")
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

PRIOR_DB = 250.0         # dropbacks of prior: ANY/A is noisy over a few games
REPL_GAP = 1.0           # prior mean = league ANY/A - 1.0 (replacement-level QB)
LG_ANYA_PRIOR = 6.0
DB_PER_GAME = 35.0       # dropbacks per team-game, roughly
BASE_WINDOW = 8          # team baseline = average value of its last 8 starters
SEASON_CARRY = 0.6       # accumulated QB evidence kept across a season break
OUT_STATUSES = ("out", "doubtful", "injured reserve", "ir", "suspension", "pup")


def _get(url: str) -> Optional[Dict[str, Any]]:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None


def _int(x, default=0) -> int:
    try:
        return int(str(x).strip())
    except Exception:
        return default


def parse_summary(s: Dict[str, Any], meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Passing lines per side from an ESPN NFL game summary."""
    box = (s or {}).get("boxscore") or {}
    out = {"espn_id": str(meta["id"]), "date": meta["date"], "home": meta["home"], "away": meta["away"],
           "season_type": meta.get("season_type"), "qbs": {}}
    side_of = {meta["home"]: "home", meta["away"]: "away"}
    for tm in box.get("players") or []:
        ab = ((tm.get("team") or {}).get("abbreviation") or "").upper()
        side = side_of.get(ab)
        if not side:
            continue
        rows = []
        for st in tm.get("statistics") or []:
            if st.get("name") != "passing":
                continue
            lab = st.get("labels") or []
            for a in st.get("athletes") or []:
                v = dict(zip(lab, a.get("stats") or []))
                cmp_att = str(v.get("C/ATT") or "0/0").split("/")
                sacks = str(v.get("SACKS") or "0-0").split("-")
                rows.append({"id": str((a.get("athlete") or {}).get("id")),
                             "name": (a.get("athlete") or {}).get("displayName"),
                             "att": _int(cmp_att[-1]), "cmp": _int(cmp_att[0]), "yds": _int(v.get("YDS")),
                             "td": _int(v.get("TD")), "int": _int(v.get("INT")),
                             "sacks": _int(sacks[0]), "sack_yds": _int(sacks[-1]) if len(sacks) > 1 else 0})
        out["qbs"][side] = rows
    if not out["qbs"].get("home") or not out["qbs"].get("away"):
        return None
    return out


def load() -> Dict[str, Any]:
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"games": {}}


def save(doc: Dict[str, Any]) -> None:
    doc["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    doc["n_games"] = len(doc.get("games") or {})
    doc["source"] = "ESPN NFL game summaries (boxscore passing lines)"
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=0)


def fetch(metas: List[Dict[str, Any]], have: Dict[str, Any], workers: int = 6) -> int:
    todo = [m for m in metas if m.get("id") and str(m["id"]) not in have]

    def one(m):
        return parse_summary(_get(f"{SITE}/summary?event={m['id']}") or {}, m)

    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for g in ex.map(one, todo):
            if g:
                have[g["espn_id"]] = g
                n += 1
    return n


def _recent_finals(days: int) -> List[Dict[str, Any]]:
    """Completed regular/post-season games over the last `days` days, from the
    dated ESPN scoreboard (the rolling finals file carries no event ids)."""
    out = []
    end = dt.date.today()
    for i in range(days + 1):
        d = end - dt.timedelta(days=i)
        sb = _get(f"{SITE}/scoreboard?dates={d:%Y%m%d}") or {}
        for ev in sb.get("events") or []:
            st = ((ev.get("status") or {}).get("type") or {})
            if not st.get("completed") or ((ev.get("season") or {}).get("type")) not in (2, 3):
                continue
            comp = (ev.get("competitions") or [{}])[0]
            side = {c.get("homeAway"): c for c in comp.get("competitors") or []}
            if "home" in side and "away" in side:
                out.append({"id": ev.get("id"), "date": d.isoformat(), "season_type": (ev.get("season") or {}).get("type"),
                            "home": ((side["home"].get("team") or {}).get("abbreviation") or "").upper(),
                            "away": ((side["away"].get("team") or {}).get("abbreviation") or "").upper()})
    return out


def grow(days: int = 8) -> int:
    doc = load()
    games = doc.setdefault("games", {})
    try:
        n = fetch(_recent_finals(days), games)
    except Exception:
        n = 0
    if n:
        save(doc)
    return n


def ordered_games(doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    doc = doc or load()
    return sorted((doc.get("games") or {}).values(), key=lambda g: (g["date"], g["espn_id"]))


def _season(date: str) -> int:
    y, m = int(date[:4]), int(date[5:7])
    return y if m >= 8 else y - 1


# ------------------------------------------------------------- features ----
class QBState:
    """Walk-forward QB value + team-usage state. Ask `edge`/`side` BEFORE
    `observe`-ing a game."""

    def __init__(self):
        self.db: Dict[str, float] = defaultdict(float)
        self.val: Dict[str, float] = defaultdict(float)
        self.name: Dict[str, str] = {}
        self.team_of: Dict[str, str] = {}
        self.lg_db, self.lg_val = 0.0, 0.0
        self.starts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=BASE_WINDOW))
        self.season: Optional[int] = None

    def lg(self) -> float:
        return self.lg_val / self.lg_db if self.lg_db > 3000 else LG_ANYA_PRIOR

    def q(self, qid: Optional[str]) -> float:
        """Shrunk ANY/A above league average (yards per dropback)."""
        lg = self.lg()
        db, val = self.db.get(qid, 0.0), self.val.get(qid, 0.0)
        return (val + PRIOR_DB * (lg - REPL_GAP)) / (db + PRIOR_DB) - lg

    def baseline(self, team: str) -> float:
        r = list(self.starts[team])
        return sum(self.q(x) for x in r) / len(r) if r else 0.0

    def edge(self, team: str, qid: Optional[str]) -> float:
        """Starter vs the team's usual, in yards per game / 10."""
        if not self.starts[team]:
            return 0.0
        return (self.q(qid) - self.baseline(team)) * DB_PER_GAME / 10

    def regular(self, team: str) -> Optional[str]:
        r = list(self.starts[team])
        if not r:
            return None
        c = defaultdict(int)
        for x in r:
            c[x] += 1
        return max(c, key=lambda x: (c[x], -r[::-1].index(x)))

    def last_starter(self, team: str) -> Optional[str]:
        r = self.starts[team]
        return r[-1] if r else None

    def team_qbs(self, team: str) -> List[str]:
        """Every QB who has thrown for this team, most dropbacks first."""
        ids = [q for q, t in self.team_of.items() if t == team]
        return sorted(ids, key=lambda q: -self.db.get(q, 0.0))

    def resolve(self, team: str, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        nm = name.strip().lower()
        hit = [q for q, n in self.name.items() if str(n or "").lower() == nm]
        mine = [q for q in hit if self.team_of.get(q) == team]
        return (mine or hit or [None])[0]

    def observe(self, g: Dict[str, Any]) -> None:
        s = _season(g["date"])
        if self.season is not None and s != self.season:
            for k in list(self.db):
                self.db[k] *= SEASON_CARRY
                self.val[k] *= SEASON_CARRY
        self.season = s
        for side in ("home", "away"):
            team, rows = g[side], g["qbs"].get(side) or []
            if not rows:
                continue
            st = max(rows, key=lambda r: r["att"] + r["sacks"])
            self.starts[team].append(st["id"])
            for r in rows:
                d = r["att"] + r["sacks"]
                v = r["yds"] + 20 * r["td"] - 45 * r["int"] - r["sack_yds"]
                self.db[r["id"]] += d
                self.val[r["id"]] += v
                self.name[r["id"]] = r["name"]
                self.team_of[r["id"]] = team
                self.lg_db += d
                self.lg_val += v


def starter_of(g: Dict[str, Any], side: str) -> Optional[str]:
    rows = g["qbs"].get(side) or []
    return max(rows, key=lambda r: r["att"] + r["sacks"])["id"] if rows else None


def history_features(games: List[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str, str], Dict[str, float]], QBState]:
    """Known-starter QB edge for every stored final, keyed (date, away, home)."""
    st = QBState()
    out = {}
    for g in games:
        h, a = g["home"], g["away"]
        out[(g["date"], a, h)] = {"qb": st.edge(h, starter_of(g, "home")) - st.edge(a, starter_of(g, "away"))}
        st.observe(g)
    return out, st


# ------------------------------------------------------------ projection ----
def injuries(event_id: str) -> Dict[str, Dict[str, str]]:
    """{team_abbrev: {qb full name (lower): status (lower)}} from ESPN's game
    summary injury report. {} on failure."""
    s = _get(f"{SITE}/summary?event={event_id}") or {}
    out: Dict[str, Dict[str, str]] = {}
    for tm in s.get("injuries") or []:
        ab = ((tm.get("team") or {}).get("abbreviation") or "").upper()
        for i in tm.get("injuries") or []:
            ath = i.get("athlete") or {}
            if ((ath.get("position") or {}).get("abbreviation")) != "QB":
                continue
            out.setdefault(ab, {})[str(ath.get("displayName") or "").lower()] = str(i.get("status") or "").lower()
    return out


def project(state: QBState, team: str, inj: Dict[str, str]) -> Dict[str, Any]:
    """Who starts for `team`, given its QB injury lines. Returns the projected
    starter, his edge, and whether the situation is settled enough to bet."""
    last, reg = state.last_starter(team), state.regular(team)
    status = lambda q: inj.get(str(state.name.get(q) or "").lower(), "")
    out_ = lambda q: any(status(q).startswith(s) for s in OUT_STATUSES)
    why, certain = "", True
    cands = [x for x in (reg, last) if x]
    pick = None
    for q in cands:
        if not out_(q):
            pick = q
            break
    if pick is None:
        nxt = [q for q in state.team_qbs(team) if q not in cands and not out_(q)]
        pick = nxt[0] if nxt else None
        why = "regular + last starter both out -> next QB on the team's passing history"
    if reg and last and reg != last and not out_(reg) and not out_(last):
        certain, why = False, (f"{state.name.get(reg)} (regular) vs {state.name.get(last)} (last start): "
                               "injury report doesn't settle it")
    if pick and status(pick).startswith("questionable"):
        certain, why = False, f"{state.name.get(pick)} questionable"
    if pick is None:
        certain, why = False, "no QB on record"
    return {"qb": state.name.get(pick), "qb_id": pick, "status": status(pick) or "active",
            "edge": round(state.edge(team, pick), 3), "certain": certain, "note": why,
            "regular": state.name.get(reg), "last_start": state.name.get(last),
            "injured_qbs": {k: v for k, v in inj.items()}}
