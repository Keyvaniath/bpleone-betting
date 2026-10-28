"""
EdgeStat -- NHL goalie + rest adjustments for the game-lines desk (2026-10-28).

WHY: the NHL desk's Elo rates a team on its goals, which mixes the skaters with
whoever was in net. The single biggest pre-game swing in an NHL price is the
goalie: when a backup starts, the team is not the team its Elo describes. The
first desk run found NO EDGE over DraftKings for NHL; this module adds the two
inputs the market prices and Elo can't see:

  1. GOALIE -- each goalie's goals saved above average (GSAA) per shot, from
     every NHL boxscore since 2024-25 (api-web.nhle.com, public), shrunk hard
     toward league average (save % is mostly noise under a few thousand shots:
     q = (saves - lg_sv * shots) / (shots + PRIOR_SHOTS)). The adjustment is the
     starter's q MINUS the team's recent-starts average, times league shots per
     game -- Elo already contains the usual goalie, so only the deviation counts.
  2. REST -- second night of a back-to-back, for each side.
  3. SHOTS -- an exponentially weighted shots-on-goal differential per team
     (alpha 0.08, ~12-game memory). Shot share predicts future wins better than
     goals over short windows.

STARTERS (2026-10-28 later): ESPN's scoreboard carries each team's
`probableStartingGoalie` with a status -- "Expected" (beat-reporter / morning
skate read) or "Confirmed". `espn_probables` reads it every run and
`log_probables` keeps the latest pre-game read per game in
data/nhl_starters_log.json, so ESPN's calls get scored against who actually
started. The desk prices a game with the KNOWN-starter model only when both
starters are Confirmed, and only then may it pick (first-in wins in the ledger,
so the logged price is the price at confirmation). Otherwise it shows the
PROJECTED starter: ESPN's Expected goalie at EXPECTED_P, else the team's
primary (most starts in its last 10) with a back-to-back-aware probability.

Data: data/nhl_goalie_games.json (seeded by tools/build_nhl_goalie_seed.py,
grown here each run from the last few days' boxscores; network failures are
non-fatal).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
import urllib.request
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATH = os.path.join(DATA_DIR, "nhl_goalie_games.json")
API = "https://api-web.nhle.com/v1"

# NHL API abbreviations -> the ESPN ones the rest of the desk keys on.
NHL_TO_ESPN = {"TBL": "TB", "NJD": "NJ", "LAK": "LA", "SJS": "SJ", "UTAH": "UTA"}

PRIOR_SHOTS = 3000.0     # shrinkage: a goalie needs ~3,000 shots before his save % means much
LG_SV_PRIOR = 0.900
SHOTS_PER_GAME = 28.5    # league shots on goal per team-game, roughly
PRIMARY_WINDOW = 10      # "primary" = most starts in the team's last 10 games
BASE_WINDOW = 20         # team baseline = average q of the starters in its last 20
SHOT_ALPHA = 0.08        # EWMA weight on the newest game's shot differential
EXPECTED_P = 0.90        # P(ESPN's "Expected" goalie starts); measured in the starters log
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
LOG_PATH = os.path.join(DATA_DIR, "nhl_starters_log.json")


def _team(a: Optional[str]) -> str:
    a = str(a or "").upper()
    return NHL_TO_ESPN.get(a, a)


def _get(url: str) -> Optional[Dict[str, Any]]:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None


def _toi_s(t: Optional[str]) -> int:
    try:
        m, s = str(t).split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def parse_boxscore(b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not b or b.get("gameState") not in ("OFF", "FINAL") or b.get("gameType") not in (2, 3):
        return None
    out = {"nhl_id": b.get("id"), "date": b.get("gameDate"), "game_type": b.get("gameType"),
           "home": _team((b.get("homeTeam") or {}).get("abbrev")),
           "away": _team((b.get("awayTeam") or {}).get("abbrev")),
           "home_score": (b.get("homeTeam") or {}).get("score"),
           "away_score": (b.get("awayTeam") or {}).get("score"),
           "home_sog": (b.get("homeTeam") or {}).get("sog"),
           "away_sog": (b.get("awayTeam") or {}).get("sog"),
           "goalies": {}}
    pbg = b.get("playerByGameStats") or {}
    for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
        rows = []
        for x in (pbg.get(key) or {}).get("goalies") or []:
            toi = _toi_s(x.get("toi"))
            if toi <= 0 and not x.get("starter"):
                continue
            rows.append({"id": x.get("playerId"), "name": (x.get("name") or {}).get("default"),
                         "starter": bool(x.get("starter")), "sa": int(x.get("shotsAgainst") or 0),
                         "sv": int(x.get("saves") or 0), "toi": toi})
        out["goalies"][side] = rows
    if not out["goalies"].get("home") or not out["goalies"].get("away"):
        return None
    return out


def _schedule_ids(start: dt.date, end: dt.date) -> List[Tuple[int, str]]:
    """(game id, date) for every regular-season / playoff game in [start, end],
    one /schedule call per week."""
    ids, day = {}, start
    while day <= end:
        s = _get(f"{API}/schedule/{day:%Y-%m-%d}") or {}
        for wk in s.get("gameWeek") or []:
            d = wk.get("date")
            if not d or not (start.isoformat() <= d <= end.isoformat()):
                continue
            for g in wk.get("games") or []:
                if g.get("gameType") in (2, 3):
                    ids[g["id"]] = d
        day += dt.timedelta(days=7)
    return sorted(ids.items(), key=lambda x: (x[1], x[0]))


def fetch_range(start: dt.date, end: dt.date, have: Dict[str, Any], workers: int = 6) -> int:
    todo = [(gid, d) for gid, d in _schedule_ids(start, end) if str(gid) not in have]

    def one(item):
        gid, _ = item
        return parse_boxscore(_get(f"{API}/gamecenter/{gid}/boxscore") or {})

    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for g in ex.map(one, todo):
            if g:
                have[str(g["nhl_id"])] = g
                n += 1
    return n


def load() -> Dict[str, Any]:
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"games": {}}


def save(doc: Dict[str, Any]) -> None:
    doc["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    doc["n_games"] = len(doc.get("games") or {})
    doc["source"] = "api-web.nhle.com gamecenter boxscores (regular season + playoffs)"
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=0)


def grow(days: int = 5) -> int:
    """Pull the last `days` days of finals into the store. Network failure = 0."""
    doc = load()
    games = doc.setdefault("games", {})
    end = dt.date.today() - dt.timedelta(days=1)
    try:
        n = fetch_range(end - dt.timedelta(days=days), end, games)
    except Exception:
        n = 0
    if n:
        save(doc)
    return n


def ordered_games(doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    doc = doc or load()
    return sorted((doc.get("games") or {}).values(), key=lambda g: (g["date"], g["nhl_id"]))


# ------------------------------------------------------------- features ----
class GoalieState:
    """Walk-forward goalie + team-usage state. Feed games in date order with
    `observe`; ask `features` BEFORE observing a game."""

    def __init__(self):
        self.sa: Dict[Any, float] = defaultdict(float)
        self.sv: Dict[Any, float] = defaultdict(float)
        self.name: Dict[Any, str] = {}
        self.lg_sa, self.lg_sv = 0.0, 0.0
        self.starts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=BASE_WINDOW))
        self.last_date: Dict[str, str] = {}
        self.shot_diff: Dict[str, float] = defaultdict(float)
        # P(primary starts) by back-to-back status: [starts, games]
        self.prim_counts = {True: [0, 0], False: [0, 0]}

    def lg(self) -> float:
        return (self.lg_sv / self.lg_sa) if self.lg_sa > 2000 else LG_SV_PRIOR

    def q(self, gid) -> float:
        sa = self.sa.get(gid, 0.0)
        return (self.sv.get(gid, 0.0) - self.lg() * sa) / (sa + PRIOR_SHOTS)

    def b2b(self, team: str, date: str) -> bool:
        last = self.last_date.get(team)
        if not last:
            return False
        return (dt.date.fromisoformat(date) - dt.date.fromisoformat(last)).days == 1

    def _primary_backup(self, team: str) -> Tuple[Any, Any, float]:
        recent = list(self.starts[team])
        last10 = recent[-PRIMARY_WINDOW:]
        c10 = defaultdict(int)
        for g in last10:
            c10[g] += 1
        if not c10:
            return None, None, 0.0
        # most starts in the last 10; ties go to whoever started more recently
        prim = max(c10, key=lambda g: (c10[g], -recent[::-1].index(g)))
        c20 = defaultdict(int)
        for g in recent:
            if g != prim:
                c20[g] += 1
        backup = max(c20, key=c20.get) if c20 else None
        return prim, backup, c10[prim] / len(last10)

    def p_primary(self, share: float, b2b: bool) -> float:
        """P(the primary starts): his share of the team's last 10 starts,
        scaled by how often primaries start on back-to-backs vs otherwise
        (estimated from every game observed so far, lightly smoothed)."""
        rate = {}
        for k, prior in ((True, 0.35), (False, 0.65)):
            s, n = self.prim_counts[k]
            rate[k] = (s + prior * 50) / (n + 50)
        base = rate[False] * 0.75 + rate[True] * 0.25 or 0.6
        return max(0.05, min(0.97, share * rate[b2b] / base))

    def baseline(self, team: str) -> float:
        recent = list(self.starts[team])
        return sum(self.q(g) for g in recent) / len(recent) if recent else 0.0

    def resolve(self, team: str, short_name: Optional[str]):
        """ESPN short name ('T. Jarry') -> NHL goalie id; prefer goalies who
        have started for this team. None if we've never seen him."""
        if not short_name:
            return None
        nm = short_name.strip().lower()
        ids = [g for g, n in self.name.items() if str(n or "").strip().lower() == nm]
        if not ids:
            last = nm.split()[-1]
            ids = [g for g, n in self.name.items() if str(n or "").strip().lower().split()[-1:] == [last]]
        mine = [g for g in ids if g in self.starts[team]]
        return (mine or ids or [None])[0]

    def known(self, team: str, gid) -> float:
        """Goals-per-game edge of a known starter vs the team's usual; a goalie
        we've never seen counts as league average."""
        if not self.starts[team]:
            return 0.0
        return ((self.q(gid) if gid is not None else 0.0) - self.baseline(team)) * SHOTS_PER_GAME

    def side(self, team: str, date: str, starter=None, expected=None) -> Dict[str, Any]:
        """Goals-per-game edge of this side's goalie vs the team's usual, for a
        known starter (if given) and the projected one. `expected` = the goalie
        id ESPN lists as Expected: he becomes the projection's primary."""
        base = self.baseline(team)
        b2b = self.b2b(team, date)
        prim, backup, share = self._primary_backup(team)
        pp = self.p_primary(share, b2b)
        if expected is not None:
            if expected != prim:
                prim, backup = expected, (prim if prim is not None else backup)
            pp = EXPECTED_P
        if prim is None:
            proj = 0.0
        elif backup is None:
            proj = self.q(prim) - base
        else:
            proj = pp * self.q(prim) + (1 - pp) * self.q(backup) - base
        out = {"b2b": b2b, "proj_goals": proj * SHOTS_PER_GAME,
               "primary": self.name.get(prim), "backup": self.name.get(backup),
               "p_primary": round(pp, 3), "q_primary": round(self.q(prim) * 100, 3) if prim else None}
        if starter is not None:
            out["known_goals"] = (self.q(starter) - base) * SHOTS_PER_GAME if self.starts[team] else 0.0
        return out

    def observe(self, g: Dict[str, Any]) -> None:
        for side in ("home", "away"):
            team = g[side]
            rows = g["goalies"].get(side) or []
            st = next((r for r in rows if r["starter"]), rows[0] if rows else None)
            if st is not None:
                prim, _, _ = self._primary_backup(team)
                if prim is not None:
                    b = self.b2b(team, g["date"])
                    self.prim_counts[b][0] += int(st["id"] == prim)
                    self.prim_counts[b][1] += 1
                self.starts[team].append(st["id"])
            for r in rows:
                self.sa[r["id"]] += r["sa"]
                self.sv[r["id"]] += r["sv"]
                self.name[r["id"]] = r["name"]
                self.lg_sa += r["sa"]
                self.lg_sv += r["sv"]
            self.last_date[team] = g["date"]
        if g.get("home_sog") is not None and g.get("away_sog") is not None:
            d = g["home_sog"] - g["away_sog"]
            h, a = g["home"], g["away"]
            self.shot_diff[h] = (1 - SHOT_ALPHA) * self.shot_diff[h] + SHOT_ALPHA * d
            self.shot_diff[a] = (1 - SHOT_ALPHA) * self.shot_diff[a] - SHOT_ALPHA * d

    def shots(self, home: str, away: str) -> float:
        """Home-minus-away EWMA shot differential, in units of 10 shots."""
        return (self.shot_diff[home] - self.shot_diff[away]) / 10


# ------------------------------------------------------------- starters ----
def _et_date(iso: Optional[str]) -> Optional[str]:
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (t - dt.timedelta(hours=4)).date().isoformat()
    except Exception:
        return None


def espn_probables(dates: List[str]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    """{(et_date, away, home): {"home": {...}, "away": {...}, "state": ...}}
    from ESPN's NHL scoreboard; each side {"name", "full", "status"} with
    status 'confirmed' | 'expected' | None. Network failure = {}."""
    out = {}
    for d in sorted(set(x for x in dates if x)):
        sb = _get(f"{ESPN_SB}?dates={d.replace('-', '')}") or {}
        for ev in sb.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            side = {c.get("homeAway"): c for c in comp.get("competitors") or []}
            if "home" not in side or "away" not in side:
                continue
            row = {"state": ((comp.get("status") or {}).get("type") or {}).get("state"),
                   "espn_event_id": ev.get("id")}
            for hs in ("home", "away"):
                pr = next((x for x in side[hs].get("probables") or []
                           if x.get("name") == "probableStartingGoalie"), None)
                ath = (pr or {}).get("athlete") or {}
                row[hs] = {"name": ath.get("shortName"), "full": ath.get("fullName"),
                           "status": ((pr or {}).get("status") or {}).get("type") if pr else None}
            key = (_et_date(ev.get("date")) or d, _team((side["away"].get("team") or {}).get("abbreviation")),
                   _team((side["home"].get("team") or {}).get("abbreviation")))
            out[key] = row
    return out


def log_probables(probs: Dict[Tuple[str, str, str], Dict[str, Any]]) -> None:
    """Keep the latest PRE-GAME read per game (plus when each side was first
    confirmed) so ESPN's calls can be scored against the boxscore starter."""
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        doc = {"games": {}}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    g = doc.setdefault("games", {})
    for (d, a, h), row in probs.items():
        if row.get("state") != "pre":
            continue
        cur = g.setdefault(f"{d}|{a}|{h}", {"date": d, "away_team": a, "home_team": h})
        for sd in ("home", "away"):
            x = row.get(sd) or {}
            if not x.get("name"):
                continue
            prev = cur.get(sd) or {}
            new = {"name": x["name"], "status": x.get("status"), "at": now,
                   "first_confirmed_at": prev.get("first_confirmed_at")}
            if x.get("status") == "confirmed" and not new["first_confirmed_at"]:
                new["first_confirmed_at"] = now
            cur[sd] = new
    doc["generated_at"] = now
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=0)


def score_probables(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How often ESPN's last pre-game Expected / Confirmed goalie actually
    started (boxscore starter flag)."""
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            log = json.load(f).get("games") or {}
    except Exception:
        return {}
    by = {(g["date"], g["away"], g["home"]): g for g in games}
    tally = {"confirmed": [0, 0], "expected": [0, 0]}
    misses = []
    for k, row in log.items():
        g = by.get((row["date"], row["away_team"], row["home_team"]))
        if not g:
            continue
        for sd in ("home", "away"):
            x = row.get(sd) or {}
            st = x.get("status")
            if st not in tally:
                continue
            rows = g["goalies"].get(sd) or []
            actual = next((r["name"] for r in rows if r["starter"]), None)
            hit = str(actual or "").lower() == str(x.get("name") or "").lower()
            tally[st][0] += int(hit)
            tally[st][1] += 1
            if not hit:
                misses.append({"game": k, "side": sd, "said": x.get("name"), "status": st, "started": actual})
    out = {st: {"n": n, "correct": c, "rate": round(c / n, 3) if n else None} for st, (c, n) in tally.items()}
    out["misses"] = misses[-20:]
    return out


def starter_of(g: Dict[str, Any], side: str):
    rows = g["goalies"].get(side) or []
    st = next((r for r in rows if r["starter"]), rows[0] if rows else None)
    return st["id"] if st else None


def history_features(games: List[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str, str], Dict[str, Any]], GoalieState]:
    """Pre-game features for every stored final, keyed (date, away, home), plus
    the state after the last game (for today's board)."""
    st = GoalieState()
    out = {}
    for g in games:
        h = st.side(g["home"], g["date"], starter_of(g, "home"))
        a = st.side(g["away"], g["date"], starter_of(g, "away"))
        out[(g["date"], g["away"], g["home"])] = {
            "goalie_proj": h["proj_goals"] - a["proj_goals"],
            "goalie_known": h.get("known_goals", 0.0) - a.get("known_goals", 0.0),
            "rest": int(a["b2b"]) - int(h["b2b"]),
            "shots": st.shots(g["home"], g["away"]),
        }
        st.observe(g)
    return out, st


# ------------------------------------------------------------- fitting ----
def fit_logit_offset(rows: List[Tuple[float, List[float], float]], l2: float = 1.0, iters: int = 25) -> List[float]:
    """Logistic regression with a fixed offset (logit of the base probability),
    no intercept, small ridge. rows = (offset, x, y). Newton's method."""
    if not rows:
        return []
    k = len(rows[0][1])
    b = [0.0] * k
    for _ in range(iters):
        g = [-l2 * bi for bi in b]
        H = [[(l2 if i == j else 0.0) for j in range(k)] for i in range(k)]
        for off, x, y in rows:
            z = off + sum(bi * xi for bi, xi in zip(b, x))
            p = 1 / (1 + math.exp(-max(min(z, 30), -30)))
            for i in range(k):
                g[i] += (y - p) * x[i]
                for j in range(k):
                    H[i][j] += p * (1 - p) * x[i] * x[j]
        step = _solve(H, g)
        b = [bi + si for bi, si in zip(b, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return b


def _solve(A: List[List[float]], v: List[float]) -> List[float]:
    n = len(v)
    M = [row[:] + [v[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            return [0.0] * n
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]
