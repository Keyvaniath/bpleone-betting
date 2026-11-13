"""
EdgeStat -- NBA availability + rest (2026-11-11). The NBA desk beyond Elo.

WHY: the v1 NBA desk was margin-of-victory Elo only. Against DraftKings' close
this season it scored log loss 0.593 vs the market's 0.542 (n=159) -- NO EDGE,
no picks, and every way of betting its disagreements lost (-11% to -43% ROI).
NBA prices move on WHO PLAYS; Elo cannot see that. This module can.

DATA: data/nba_player_games.json -- every player's minutes and Game Score in
every final since 2025-10-21 (ESPN summaries; seed tools/build_nba_avail_seed.py,
grown each run from the dated scoreboard). No paid feed.

MODEL (walk-forward; a game only ever sees games before it):
  player rate  r = decayed Game Score per minute, shrunk toward replacement
                   level with a 100-minute prior
  exp. minutes m = mean of his last 8 appearances
  roster(T)      = players who have appeared for T THIS season and within T's
                   last 45 games
  value missing  L(T) = sum over roster players NOT playing of m * (r - r_repl)
  abnormal absence   = L(T) today - EWMA of L(T) over T's earlier games
                       (Elo has already absorbed the absences it has seen)
  features           = [logit(Elo), abn(away) - abn(home), b2b(away) - b2b(home), 1]
A logistic regression on those, fitted on LAST season only, is the model; this
season is a clean test against the DraftKings close (game_lines_desk.backtest).

BACKTEST vs LIVE: historically "not playing" = did not appear in the box score.
That includes late scratches the close knew about and a morning pipeline did
not -- so the backtest is the model's ceiling at the close. Live, "not playing"
= ESPN's injury report: Out counts fully, Day-To-Day at half; a game where a
Day-To-Day player would move the number materially is BLOCKED from picking
(same discipline as the NFL quarterback gate).
"""
from __future__ import annotations

import datetime as dt
import json
import os
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, Tuple

import espn_box_logs as eb

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
STORE = os.path.join(DATA_DIR, "nba_player_games.json")
BASE = f"{eb.BASE_URL}/basketball/nba"

# The four constants below were CHOSEN ON LAST SEASON ONLY (2025-26, n=1,125):
# a 54-point grid scored by split-half cross-validated log loss of the fitted
# model (best 0.5957). This season was looked at once, after the choice.
R_REPL = 0.26          # Game Score per minute of a replacement-level player (sub-15-minute players measure 0.30)
RATE_PRIOR_MIN = 100.0  # minutes of prior at replacement level
RATE_DECAY = 0.985      # per appearance
MIN_WINDOW = 8          # appearances in the expected-minutes mean
ROSTER_GAMES = 45       # a player unseen for this many team games leaves the roster
L_ALPHA = 0.08          # EWMA of a team's value missing
DTD_WEIGHT = 0.5        # ESPN "Day-To-Day" counts as half out
BLOCK_UNCERTAIN = 2.5   # Game Score points of Day-To-Day value that blocks a pick


def _season(date: str) -> int:
    y, m = int(date[:4]), int(date[5:7])
    return y + 1 if m >= 9 else y


# ------------------------------------------------------------------ store ----
def load() -> Dict[str, Any]:
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"names": {}, "games": {}}


def save(doc: Dict[str, Any]) -> None:
    doc["generated_at"] = dt.datetime.utcnow().isoformat(timespec="seconds")
    doc["n_games"] = len(doc.get("games") or {})
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, STORE)


def _num(x, d=0.0) -> float:
    try:
        return float(str(x).replace("+", ""))
    except Exception:
        return d


def _pair(x) -> Tuple[float, float]:
    try:
        a, b = str(x).split("-")
        return float(a), float(b)
    except Exception:
        return 0.0, 0.0


def game_score(names: List[str], vals: List[str]) -> Tuple[float, float]:
    """(minutes, Hollinger Game Score) from one ESPN stat line."""
    ix = {n: i for i, n in enumerate(names)}
    v = lambda k: vals[ix[k]] if k in ix and ix[k] < len(vals) else 0
    fgm, fga = _pair(v("FG"))
    ftm, fta = _pair(v("FT"))
    mins = _num(v("MIN"))
    gs = (_num(v("PTS")) + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * _num(v("OREB")) + 0.3 * _num(v("DREB"))
          + _num(v("STL")) + 0.7 * _num(v("AST")) + 0.7 * _num(v("BLK")) - 0.4 * _num(v("PF")) - _num(v("TO")))
    return mins, gs


def parse_summary(s: Dict[str, Any], date: str) -> Optional[Dict[str, Any]]:
    """One game -> {"d", "h", "a", "p": [[side, athlete_id, minutes, gs*10]], "names"}."""
    comp = (((s.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or [])
    home = next((c for c in comp if c.get("homeAway") == "home"), None)
    away = next((c for c in comp if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    ab = lambda c: str(((c.get("team") or {}).get("abbreviation")) or "").upper()
    h, a = ab(home), ab(away)
    rows, names = [], {}
    for tb in ((s.get("boxscore") or {}).get("players") or []):
        t = str((tb.get("team") or {}).get("abbreviation") or "").upper()
        side = 1 if t == h else 0
        for sb in (tb.get("statistics") or []):
            nm = [str(n).upper() for n in (sb.get("names") or [])]
            for ath in (sb.get("athletes") or []):
                aid = str((ath.get("athlete") or {}).get("id") or "")
                vals = ath.get("stats") or []
                if not aid or ath.get("didNotPlay") or not vals:
                    continue
                mins, gs = game_score(nm, vals)
                if mins <= 0:
                    continue
                rows.append([side, aid, int(round(mins)), int(round(gs * 10))])
                names[aid] = (ath.get("athlete") or {}).get("displayName") or aid
    if len(rows) < 10:
        return None
    return {"d": date, "h": h, "a": a, "p": rows, "names": names}


def fetch(metas: List[Dict[str, Any]], doc: Dict[str, Any], workers: int = 8) -> int:
    """metas: [{"id", "date"}] not yet in the store."""
    todo = [m for m in metas if m.get("id") and str(m["id"]) not in doc["games"]]

    def one(m):
        s = eb._http(f"{BASE}/summary?event={m['id']}")
        return m, (parse_summary(s, m["date"]) if s else None)

    n = 0
    with ThreadPoolExecutor(workers) as ex:
        for m, g in ex.map(one, todo):
            if not g:
                continue
            doc["names"].update(g.pop("names"))
            doc["games"][str(m["id"])] = g
            n += 1
    return n


def _et_date(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (d - dt.timedelta(hours=5)).date().isoformat()
    except Exception:
        return ""


def scoreboard_finals(day: dt.date) -> List[Dict[str, Any]]:
    sb = eb._http(f"{BASE}/scoreboard?dates={day.strftime('%Y%m%d')}") or {}
    out = []
    for e in sb.get("events") or []:
        st = (((e.get("status") or {}).get("type") or {}).get("state"))
        if st == "post" and e.get("id"):
            out.append({"id": str(e["id"]), "date": day.isoformat()})
    return out


def grow(days: int = 8) -> int:
    """Add the last `days` days of finals. Network fail-soft: returns 0."""
    try:
        doc = load()
        metas = []
        today = dt.datetime.utcnow().date()
        for i in range(days + 1):
            metas.extend(scoreboard_finals(today - dt.timedelta(days=i)))
        n = fetch(metas, doc)
        if n:
            save(doc)
        return n
    except Exception:
        return 0


def ordered_games(doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    doc = doc or load()
    return sorted(({"id": k, **v} for k, v in (doc.get("games") or {}).items()), key=lambda g: (g["d"], g["id"]))


# ------------------------------------------------------------------ state ----
class AvailState:
    def __init__(self) -> None:
        self.p: Dict[str, Dict[str, Any]] = {}
        self.tg: Dict[Tuple[str, int], int] = defaultdict(int)     # (team, season) -> games played
        self.l_ewma: Dict[Tuple[str, int], float] = {}
        self.last_date: Dict[str, str] = {}
        self.names: Dict[str, str] = {}

    def rate(self, aid: str) -> float:
        s = self.p.get(aid)
        if not s:
            return R_REPL
        return (s["sg"] + RATE_PRIOR_MIN * R_REPL) / (s["sm"] + RATE_PRIOR_MIN)

    def exp_min(self, aid: str) -> float:
        s = self.p.get(aid)
        return sum(s["mins"]) / len(s["mins"]) if s and s["mins"] else 0.0

    def value(self, aid: str) -> float:
        """Game Score points per game above a replacement playing the same minutes."""
        return self.exp_min(aid) * (self.rate(aid) - R_REPL)

    def roster(self, team: str, season: int) -> List[str]:
        n = self.tg[(team, season)]
        return [a for a, s in self.p.items()
                if s["team"] == team and s["season"] == season and n - s["idx"] <= ROSTER_GAMES]

    def missing_value(self, team: str, season: int, weights: Dict[str, float]) -> float:
        """weights: athlete_id -> fraction absent (1 = out). Roster members only."""
        ros = set(self.roster(team, season))
        return sum(w * self.value(a) for a, w in weights.items() if a in ros)

    def abnormal(self, team: str, season: int, l_today: float) -> float:
        return l_today - self.l_ewma.get((team, season), l_today)

    def b2b(self, team: str, date: str) -> bool:
        # (2026-11-13 review) a game SCHEDULED the day before counts too (see nhl_goalies.b2b)
        try:
            prev = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
            if prev in (getattr(self, "scheduled", None) or {}).get(team, ()):
                return True
        except Exception:
            pass
        ld = self.last_date.get(team)
        if not ld:
            return False
        try:
            return (dt.date.fromisoformat(date) - dt.date.fromisoformat(ld)).days == 1
        except Exception:
            return False

    def features(self, g: Dict[str, Any]) -> Dict[str, float]:
        """Pre-game features of a FINISHED game, from the players who appeared."""
        season = _season(g["d"])
        played = {0: set(), 1: set()}
        for side, aid, _m, _gs in g["p"]:
            played[side].add(aid)
        out = {}
        for side, team in ((1, g["h"]), (0, g["a"])):
            absent = {a: 1.0 for a in self.roster(team, season) if a not in played[side]}
            l_today = self.missing_value(team, season, absent)
            out[side] = (l_today, self.abnormal(team, season, l_today), self.b2b(team, g["d"]))
        return {"avail": out[0][1] - out[1][1], "rest": float(out[0][2]) - float(out[1][2]),
                "l_home": out[1][0], "l_away": out[0][0]}

    def update(self, g: Dict[str, Any]) -> None:
        season = _season(g["d"])
        played = {0: set(), 1: set()}
        for side, aid, _m, _gs in g["p"]:
            played[side].add(aid)
        # value missing BEFORE this game's stats are learned -> feeds the EWMA
        for side, team in ((1, g["h"]), (0, g["a"])):
            absent = {a: 1.0 for a in self.roster(team, season) if a not in played[side]}
            l_today = self.missing_value(team, season, absent)
            k = (team, season)
            self.l_ewma[k] = l_today if k not in self.l_ewma else (1 - L_ALPHA) * self.l_ewma[k] + L_ALPHA * l_today
            self.tg[k] += 1
            self.last_date[team] = g["d"]
        for side, aid, mins, gs10 in g["p"]:
            team = g["h"] if side == 1 else g["a"]
            s = self.p.setdefault(aid, {"mins": deque(maxlen=MIN_WINDOW), "sg": 0.0, "sm": 0.0,
                                         "team": team, "season": season, "idx": 0})
            s["sg"] = s["sg"] * RATE_DECAY + gs10 / 10.0
            s["sm"] = s["sm"] * RATE_DECAY + mins
            s["mins"].append(mins)
            s["team"], s["season"], s["idx"] = team, season, self.tg[(team, season)]


def history_features(games: List[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str, str], Dict[str, float]], AvailState]:
    st = AvailState()
    feats: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for g in games:
        feats[(g["d"], g["a"], g["h"])] = st.features(g)
        st.update(g)
    return feats, st


def measure_repl(games: Optional[List[Dict[str, Any]]] = None) -> float:
    """Minute-weighted Game Score per minute of players averaging under 15
    minutes (the people who absorb a missing starter's minutes)."""
    games = games or ordered_games()
    tot: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0, 0])
    for g in games:
        for _s, aid, mins, gs10 in g["p"]:
            t = tot[aid]
            t[0] += gs10 / 10.0; t[1] += mins; t[2] += 1
    sg = sum(t[0] for t in tot.values() if t[2] >= 10 and t[1] / t[2] < 15)
    sm = sum(t[1] for t in tot.values() if t[2] >= 10 and t[1] / t[2] < 15)
    return round(sg / sm, 4) if sm else R_REPL


# ------------------------------------------------------------------- live ----
def injuries(event_id: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{TEAM: {athlete_id: {"status", "name"}}} from ESPN's game summary."""
    s = eb._http(f"{BASE}/summary?event={event_id}") or {}
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for b in s.get("injuries") or []:
        t = str((b.get("team") or {}).get("abbreviation") or "").upper()
        for i in b.get("injuries") or []:
            a = i.get("athlete") or {}
            if a.get("id"):
                out.setdefault(t, {})[str(a["id"])] = {"status": str(i.get("status") or ""), "name": a.get("displayName")}
    return out


def project(state: AvailState, team: str, date: str, inj: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Today's value missing for one team from the injury report."""
    season = _season(date)
    ros = set(state.roster(team, season))
    out_w, uncertain, listed = {}, 0.0, []
    for aid, d in (inj or {}).items():
        if aid not in ros:
            continue
        st = d.get("status", "").lower()
        v = state.value(aid)
        if st == "out":
            out_w[aid] = 1.0
        elif "day" in st or "question" in st or "doubt" in st:
            out_w[aid] = DTD_WEIGHT
            uncertain += abs(v) * DTD_WEIGHT
        else:
            continue
        listed.append({"name": d.get("name") or state.names.get(aid) or aid, "status": d.get("status"),
                       "value": round(v, 2), "exp_min": round(state.exp_min(aid), 1)})
    l_today = state.missing_value(team, season, out_w)
    listed.sort(key=lambda x: -abs(x["value"]))
    return {"missing_value": round(l_today, 2), "abnormal": round(state.abnormal(team, season, l_today), 2),
            "usual_missing": round(state.l_ewma.get((team, season), 0.0), 2),
            "b2b": state.b2b(team, date), "uncertain_value": round(uncertain, 2),
            "certain": uncertain < BLOCK_UNCERTAIN, "listed": listed[:6],
            "n_roster": len(ros)}


if __name__ == "__main__":
    n = grow()
    doc = load()
    gms = ordered_games(doc)
    print(f"[nba-avail] {len(gms)} games in the store (+{n} today), {len(doc.get('names') or {})} players; "
          f"measured replacement rate {measure_repl(gms)} GS/min (constant in use {R_REPL})")
