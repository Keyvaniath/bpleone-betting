"""
EdgeStat -- NHL skater rate store (hits / blocks / shots / PIM) from real
boxscores (2026-11-02).

WHY: nhl_skater_hits_blocks_props.py priced from a HAND-TYPED table of
"2024-25" per-game rates (Trent Frederic 3.5 hits/g; stale teams) through a
Poisson. Graded on real box scores it was badly overconfident: HITS_OVER_2.5
6-15 (29%) at a predicted ~67%, BLOCKS_OVER_1.5 15-20 (43%) at ~64%.

This store replays every NHL boxscore since 2024-25 (api-web.nhle.com) in date
order and keeps, per skater, exponentially weighted per-game rates (alpha
EW_ALPHA) plus games played; a query shrinks toward the position mean with
SHRINK_GP games of prior. Hits carry a home/away factor (home-arena scorers
log more hits). While replaying, every skater-game is first PREDICTED from the
state before it, and the negative-binomial dispersion per stat is chosen on
last season by log loss (`calibration` in the output) -- so the probabilities
are fitted, not asserted.

Goals and points ride along (2026-11-02): the anytime-goal module's hand table
ran ANYTIME_GOAL_NO 71% at 87% predicted.

Output: data/nhl_skater_rates.json (players + calibration); grown daily.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import nhl_goalies as ng

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATH = os.path.join(DATA_DIR, "nhl_skater_rates.json")
STATS = ("hits", "blocks", "sog", "pim", "goals", "points")
EW_ALPHA = 0.08          # weight of the newest game in a player's rate (~12-game memory)
SHRINK_GP = 8.0          # games of position-mean prior
SEASON_CARRY_GP = 0.5    # games-played credit kept across a season break
DISP_GRID = [1.0, 2.0, 3.0, 5.0, 8.0, 15.0, 40.0, 1e9]   # NB r (1e9 = Poisson)
CAL_TARGETS = {"hits": [1, 2, 3], "blocks": [1, 2], "sog": [2, 3, 4], "pim": [1], "goals": [1], "points": [1, 2]}


# ------------------------------------------------------------- probability ----
def p_at_least(k: int, mean: float, r: float) -> float:
    """P(X >= k) for a negative binomial with this mean and dispersion r
    (var = mean + mean^2 / r); r -> inf is Poisson."""
    if mean <= 0:
        return 0.0 if k > 0 else 1.0
    if r >= 1e8:
        cdf = sum(math.exp(i * math.log(mean) - mean - math.lgamma(i + 1)) for i in range(k))
    else:
        p = r / (r + mean)
        cdf = sum(math.exp(math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1)
                           + r * math.log(p) + i * math.log(1 - p)) for i in range(k))
    return max(0.0, min(1.0, 1.0 - cdf))


# -------------------------------------------------------------------- data ----
def parse_skaters(b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not b or b.get("gameState") not in ("OFF", "FINAL") or b.get("gameType") not in (2, 3):
        return None
    out = {"id": b.get("id"), "date": b.get("gameDate"),
           "home": ng._team((b.get("homeTeam") or {}).get("abbrev")),
           "away": ng._team((b.get("awayTeam") or {}).get("abbrev")), "rows": []}
    pbg = b.get("playerByGameStats") or {}
    for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
        for grp, pos in (("forwards", "F"), ("defense", "D")):
            for x in (pbg.get(key) or {}).get(grp) or []:
                toi = ng._toi_s(x.get("toi"))
                if toi <= 0:
                    continue
                out["rows"].append({"pid": x.get("playerId"), "name": (x.get("name") or {}).get("default"),
                                    "side": side, "pos": pos, "toi": toi,
                                    "hits": int(x.get("hits") or 0), "blocks": int(x.get("blockedShots") or 0),
                                    "sog": int(x.get("sog") or 0), "pim": int(x.get("pim") or 0),
                                    "goals": int(x.get("goals") or 0), "points": int(x.get("points") or 0)})
    return out if out["rows"] else None


class SkaterState:
    def __init__(self, doc: Optional[Dict[str, Any]] = None):
        doc = doc or {}
        self.p: Dict[str, Dict[str, Any]] = doc.get("players") or {}
        self.pos_sum = doc.get("pos_sum") or {"F": {s: 0.0 for s in STATS + ("n",)}, "D": {s: 0.0 for s in STATS + ("n",)}}
        self.venue = doc.get("venue") or {"home": 0.0, "away": 0.0, "nh": 0.0, "na": 0.0}
        self.processed = set(doc.get("processed") or [])
        self.season = doc.get("season")

    def pos_mean(self, pos: str, stat: str) -> float:
        s = self.pos_sum.get(pos) or {}
        return (s.get(stat, 0.0) / s["n"]) if s.get("n") else {"hits": 1.2, "blocks": 0.8, "sog": 1.8, "pim": 0.5,
                                                                "goals": 0.15, "points": 0.45}[stat]

    def hit_factor(self, side: str) -> float:
        v = self.venue
        if not v["nh"] or not v["na"]:
            return 1.0
        h, a = v["home"] / v["nh"], v["away"] / v["na"]
        avg = (h + a) / 2
        return (h if side == "home" else a) / avg if avg else 1.0

    def rate(self, pid: str, stat: str, side: Optional[str] = None) -> Optional[float]:
        x = self.p.get(str(pid))
        if not x:
            return None
        gp = x["gp"]
        m = (gp * x["ew"][stat] + SHRINK_GP * self.pos_mean(x["pos"], stat)) / (gp + SHRINK_GP)
        if stat == "hits" and side:
            m *= self.hit_factor(side)
        return m

    def observe(self, g: Dict[str, Any]) -> None:
        s = int(g["date"][:4]) if int(g["date"][5:7]) >= 9 else int(g["date"][:4]) - 1
        if self.season is not None and s != self.season:
            for x in self.p.values():
                x["gp"] *= SEASON_CARRY_GP
        self.season = s
        for r in g["rows"]:
            pid = str(r["pid"])
            x = self.p.get(pid)
            if x is None:
                x = self.p[pid] = {"name": r["name"], "pos": r["pos"], "gp": 0.0,
                                   "ew": {st: self.pos_mean(r["pos"], st) for st in STATS}}
            for st in STATS:
                x["ew"][st] = (1 - EW_ALPHA) * x["ew"][st] + EW_ALPHA * r[st]
            x["gp"] += 1
            x["team"] = g[r["side"]]
            x["last_date"] = g["date"]
            x["name"] = r["name"]
            ps = self.pos_sum[r["pos"]]
            for st in STATS:
                ps[st] += r[st]
            ps["n"] += 1
            self.venue[r["side"]] += r["hits"]
            self.venue["nh" if r["side"] == "home" else "na"] += 1
        self.processed.add(str(g["id"]))

    def dump(self, calibration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "source": "api-web.nhle.com boxscores (skaters), replayed in date order",
                "method": f"EWMA alpha {EW_ALPHA}, {SHRINK_GP}-game position-mean prior, hits x home/away factor",
                "season": self.season, "n_players": len(self.p), "players": self.p, "pos_sum": self.pos_sum,
                "venue": self.venue, "processed": sorted(self.processed), "calibration": calibration}


def load() -> Tuple[SkaterState, Dict[str, Any]]:
    try:
        with open(PATH, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        doc = {}
    return SkaterState(doc), (doc.get("calibration") or {})


def save(st: SkaterState, calibration: Dict[str, Any]) -> None:
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(st.dump(calibration), f, indent=0)


def fetch_games(ids: List[Tuple[Any, str]], workers: int = 6) -> List[Dict[str, Any]]:
    def one(item):
        return parse_skaters(ng._get(f"{ng.API}/gamecenter/{item[0]}/boxscore") or {})
    with ThreadPoolExecutor(max_workers=workers) as ex:
        got = [g for g in ex.map(one, ids) if g]
    return sorted(got, key=lambda g: (g["date"], g["id"]))


def replay(games: List[Dict[str, Any]], st: SkaterState, cal_from: Optional[str] = None,
           cal_to: Optional[str] = None) -> Dict[str, Any]:
    """Feed games in order; for games in [cal_from, cal_to) score the
    pre-game prediction of every established skater (gp >= 10) under each
    dispersion in DISP_GRID. Returns {stat: {r: logloss}} + reliability."""
    ll = {st_: {r: [0.0, 0] for r in DISP_GRID} for st_ in STATS}
    rel = defaultdict(lambda: [0.0, 0.0, 0])   # (stat, k, r, bin) -> [sum p, sum y, n]
    for g in games:
        if str(g["id"]) in st.processed:
            continue
        if cal_from and cal_from <= g["date"] < (cal_to or "9999"):
            for r in g["rows"]:
                x = st.p.get(str(r["pid"]))
                if not x or x["gp"] < 10:
                    continue
                for stat, ks in CAL_TARGETS.items():
                    m = st.rate(r["pid"], stat, r["side"])
                    for k in ks:
                        y = 1.0 if r[stat] >= k else 0.0
                        for disp in DISP_GRID:
                            p = min(max(p_at_least(k, m, disp), 1e-4), 1 - 1e-4)
                            cell = ll[stat][disp]
                            cell[0] += -(y * math.log(p) + (1 - y) * math.log(1 - p))
                            cell[1] += 1
                            b = rel[(stat, k, disp, min(int(p * 10), 9))]
                            b[0] += p
                            b[1] += y
                            b[2] += 1
        st.observe(g)
    cal = {}
    for stat in STATS:
        if not any(c[1] for c in ll[stat].values()):
            continue
        scores = {r: c[0] / c[1] for r, c in ll[stat].items() if c[1]}
        best = min(scores, key=scores.get)
        bins = []
        for k in CAL_TARGETS[stat]:
            for bi in range(10):
                b = rel.get((stat, k, best, bi))
                if b and b[2] >= 30:
                    bins.append({"k": k, "bin": bi / 10, "n": b[2], "pred": round(b[0] / b[2], 3),
                                 "actual": round(b[1] / b[2], 3)})
        cal[stat] = {"dispersion_r": best, "logloss_by_r": {str(r): round(v, 4) for r, v in scores.items()},
                     "reliability": bins, "window": [cal_from, cal_to]}
    return cal


def grow(days: int = 5) -> int:
    """Replay the last few days' boxscores into the store (network fail-soft)."""
    st, cal = load()
    if not st.p:
        return 0
    end = dt.date.today() - dt.timedelta(days=1)
    try:
        ids = [(gid, d) for gid, d in ng._schedule_ids(end - dt.timedelta(days=days), end)
               if str(gid) not in st.processed]
        games = fetch_games(ids)
    except Exception:
        return 0
    if games:
        replay(games, st)
        save(st, cal)
    return len(games)


def dispersion(cal: Dict[str, Any], stat: str) -> float:
    return float(((cal or {}).get(stat) or {}).get("dispersion_r") or 1e9)
