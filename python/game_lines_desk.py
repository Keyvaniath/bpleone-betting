"""
EdgeStat -- NFL + NHL game-lines desk (moneylines vs the DraftKings price).

WHY (2026-10-28): the NFL and NHL "game models" were record-based Elo with no
margin of victory, and NHL's added a flat +10pp home "calibration shift" fitted
on 93 games (Brier 0.313 -- worse than a coin). No NFL/NHL pick had ever been
priced at a real book line; the props desks pay themselves at their own fair
odds. This desk does it the MLB way:

  1. RATINGS -- margin-of-victory Elo over every regular-season + playoff final
     (data/game_finals_<sport>.json seed, last season onward, merged daily with
     the rolling finals files). Season carry-over regresses 1/3 to the mean.
  2. MARKET -- DraftKings' no-vig probability from the live board
     (espn_odds.json); data/dk_lines_<sport>.json keeps every game's open and
     close so the desk can be judged against the market.
  3. BLEND -- logit(p) = logit(p_dk) + w * (logit(p_elo) - logit(p_dk)). w is
     FITTED walk-forward on this season's DK-priced games (minimum log loss); a
     model that adds nothing gets w = 0 and therefore makes no picks.
  4. PICKS -- a moneyline only when p * decimal(DK price) - 1 >= MIN_EDGE, at the
     DK price, graded by the ledger on the final score. Never curated by
     default: the backtest has to earn that (see `verdict`).

Output: data/game_lines_desk.json (board + backtest), dk_lines_* (grown),
game_finals_* (grown).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "game_lines_desk.json")

# Elo parameters per sport. NFL: 538-style (K 20, HFA ~48 Elo, log-MOV
# multiplier with autocorrelation correction). NHL: K 8, HFA ~25 Elo, MOV
# multiplier from 538's hockey model; OT/SO wins count as a one-goal margin.
PARAMS = {
    "nfl": {"k": 20.0, "hfa": 48.0, "carry": 1 / 3},
    "nhl": {"k": 8.0, "hfa": 25.0, "carry": 1 / 3},
}
MIN_EDGE = 0.04          # 4% expected value at the DK price
W_GRID = [i / 20 for i in range(21)]
MIN_BACKTEST_N = 60      # below this, w stays 0 (not enough evidence to lean on)


def _load(p: str) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _dump(p: str, o: Any) -> None:
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, indent=0)


def _dec(a) -> Optional[float]:
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def _american(p: float) -> Optional[int]:
    if p is None or not 0.01 < p < 0.99:
        return None
    return -int(round(100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def _no_vig(ml_home, ml_away) -> Optional[float]:
    dh, da = _dec(ml_home), _dec(ml_away)
    if not dh or not da:
        return None
    ih, ia = 1 / dh, 1 / da
    return ih / (ih + ia)


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _season_key(sport: str, date: str) -> int:
    """NFL season starts in September; NHL in October. Anything before the
    season-start month belongs to the previous season."""
    y, m = int(date[:4]), int(date[5:7])
    start = 8 if sport == "nfl" else 9
    return y if m >= start else y - 1


# ---------------------------------------------------------------- finals ----
_ABBR_ALIAS = {"nhl": {"UTAH": "UTA", "LA": "LA", "SJ": "SJ", "TB": "TB", "NJ": "NJ"},
               "nfl": {"WSH": "WSH", "LAR": "LAR", "JAX": "JAX"}}


def _norm_team(sport: str, t: Optional[str]) -> str:
    t = str(t or "").upper().strip()
    return _ABBR_ALIAS.get(sport, {}).get(t, t)


def load_finals(sport: str) -> List[Dict[str, Any]]:
    """Seed finals + the rolling daily finals file, deduped by (date, away, home)."""
    seed = _load(os.path.join(DATA_DIR, f"game_finals_{sport}.json")).get("games") or []
    by: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for g in seed:
        k = (g["date"], _norm_team(sport, g["away"]), _norm_team(sport, g["home"]))
        by[k] = dict(g, home=k[2], away=k[1])
    roll = _load(os.path.join(DATA_DIR, f"{sport}_historical.json")).get("games") or []
    added = 0
    for g in roll:
        if g.get("home_score") is None or g.get("away_score") is None:
            continue
        d = str(g.get("date") or "")[:10]
        k = (d, _norm_team(sport, g.get("away_abbrev")), _norm_team(sport, g.get("home_abbrev")))
        if not all(k) or k in by:
            continue
        hp, ap = g.get("home_periods") or [], g.get("away_periods") or []
        by[k] = {"id": None, "date": d, "season": None, "season_type": 2, "neutral": False,
                 "home": k[2], "away": k[1], "home_score": int(g["home_score"]),
                 "away_score": int(g["away_score"]),
                 "ot": max(len(hp), len(ap)) > (4 if sport == "nfl" else 3)}
        added += 1
    games = sorted(by.values(), key=lambda g: (g["date"], g["home"]))
    if added:
        _dump(os.path.join(DATA_DIR, f"game_finals_{sport}.json"),
              {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "sport": sport,
               "source": "ESPN finals (seed + daily rolling merge)", "n_games": len(games), "games": games})
    return games


# ------------------------------------------------------------------- elo ----
class Elo:
    def __init__(self, sport: str, k: float, hfa: float, carry: float):
        self.sport, self.k, self.hfa, self.carry = sport, k, hfa, carry
        self.r: Dict[str, float] = {}
        self.season: Optional[int] = None

    def _rating(self, t: str) -> float:
        return self.r.get(t, 1500.0)

    def p_home(self, home: str, away: str, neutral: bool = False) -> float:
        diff = self._rating(home) - self._rating(away) + (0 if neutral else self.hfa)
        return 1 / (1 + 10 ** (-diff / 400))

    def new_season(self, s: int) -> None:
        if self.season is not None and s != self.season:
            self.r = {t: 1500 + (v - 1500) * (1 - self.carry) for t, v in self.r.items()}
        self.season = s

    def update(self, g: Dict[str, Any]) -> None:
        h, a = g["home"], g["away"]
        hs, as_ = g["home_score"], g["away_score"]
        if hs == as_:
            res, mov = 0.5, 0
        else:
            res = 1.0 if hs > as_ else 0.0
            mov = 1 if g.get("ot") else abs(hs - as_)
        p = self.p_home(h, a, g.get("neutral"))
        diff_w = (self._rating(h) - self._rating(a) + (0 if g.get("neutral") else self.hfa)) * (1 if res == 1 else -1)
        if self.sport == "nfl":
            mult = math.log(mov + 1) * (2.2 / (diff_w * 0.001 + 2.2)) if mov else 1.0
        else:
            mult = (0.6686 * math.log(mov) + 0.8048) if mov >= 1 else 1.0
        delta = self.k * mult * (res - p)
        self.r[h] = self._rating(h) + delta
        self.r[a] = self._rating(a) - delta


def replay(sport: str, finals: List[Dict[str, Any]], params: Dict[str, float],
           stop_before: Optional[str] = None) -> Elo:
    e = Elo(sport, params["k"], params["hfa"], params["carry"])
    for g in finals:
        if stop_before and g["date"] >= stop_before:
            break
        e.new_season(_season_key(sport, g["date"]))
        e.update(g)
    return e


# --------------------------------------------------------------- backtest ----
def _ll(p: float, y: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def backtest(sport: str, finals: List[Dict[str, Any]], lines: Dict[str, Any],
             params: Dict[str, float]) -> Dict[str, Any]:
    """Walk-forward over this season's DK-priced games: before each game date,
    rate with every earlier final; compare log loss of Elo, DK no-vig, and the
    blend at each w; simulate the pick rule at the DK close."""
    fin = {(g["date"], g["away"], g["home"]): g for g in finals}
    rows = []
    for eid, ev in lines.items():
        c = ev.get("close") or {}
        p_mkt = _no_vig(c.get("ml_home"), c.get("ml_away"))
        try:
            ct = dt.datetime.fromisoformat(str(ev.get("commence")).replace("Z", "+00:00"))
        except Exception:
            continue
        d = (ct - dt.timedelta(hours=4)).date().isoformat()
        k = (d, _norm_team(sport, ev.get("away")), _norm_team(sport, ev.get("home")))
        g = fin.get(k)
        if p_mkt is None or not g or g["home_score"] == g["away_score"]:
            continue
        rows.append((d, k, g, p_mkt, c))
    rows.sort(key=lambda r: r[0])
    out = []
    elo, cursor = Elo(sport, params["k"], params["hfa"], params["carry"]), 0
    for d, k, g, p_mkt, c in rows:
        while cursor < len(finals) and finals[cursor]["date"] < d:
            elo.new_season(_season_key(sport, finals[cursor]["date"]))
            elo.update(finals[cursor])
            cursor += 1
        elo.new_season(_season_key(sport, d))
        out.append({"date": d, "matchup": f"{k[1]} @ {k[2]}", "y": 1.0 if g["home_score"] > g["away_score"] else 0.0,
                    "p_elo": elo.p_home(k[2], k[1], g.get("neutral")), "p_mkt": p_mkt,
                    "ml_home": c.get("ml_home"), "ml_away": c.get("ml_away")})
    n = len(out)
    if not n:
        return {"n": 0}
    ll_mkt = sum(_ll(r["p_mkt"], r["y"]) for r in out) / n
    ll_elo = sum(_ll(r["p_elo"], r["y"]) for r in out) / n
    by_w = {}
    for w in W_GRID:
        by_w[w] = sum(_ll(_sig(_logit(r["p_mkt"]) + w * (_logit(r["p_elo"]) - _logit(r["p_mkt"]))), r["y"])
                      for r in out) / n
    w_best = min(by_w, key=by_w.get)

    def sim(w: float, edge: float) -> Dict[str, Any]:
        bets, units, wins = 0, 0.0, 0
        for r in out:
            p = _sig(_logit(r["p_mkt"]) + w * (_logit(r["p_elo"]) - _logit(r["p_mkt"])))
            for side, pp, px in (("home", p, r["ml_home"]), ("away", 1 - p, r["ml_away"])):
                dd = _dec(px)
                if dd and pp * dd - 1 >= edge:
                    won = (r["y"] == 1.0) == (side == "home")
                    bets += 1
                    wins += won
                    units += (dd - 1) if won else -1.0
        return {"bets": bets, "wins": wins, "units": round(units, 2),
                "roi_pct": round(units / bets * 100, 1) if bets else None}

    # w is FITTED, so its in-sample sim flatters it. Report the honest
    # out-of-sample number too: w fitted on the first half, applied to the second.
    half = n // 2
    first, second = out[:half], out[half:]
    w_first = min(W_GRID, key=lambda w: sum(_ll(_sig(_logit(r["p_mkt"]) + w * (_logit(r["p_elo"]) - _logit(r["p_mkt"]))), r["y"]) for r in first)) if first else 0.0
    keep = out
    out = second
    oos = sim(w_first, MIN_EDGE)
    out = keep
    # Paired bootstrap of the log-loss gain over the market at the fitted w
    # (1,000 resamples, fixed seed): is the improvement distinguishable from 0?
    import random
    rng = random.Random(7)
    gains = [_ll(r["p_mkt"], r["y"]) - _ll(_sig(_logit(r["p_mkt"]) + w_best * (_logit(r["p_elo"]) - _logit(r["p_mkt"]))), r["y"])
             for r in out]
    boots = sorted(sum(gains[rng.randrange(n)] for _ in range(n)) / n for _ in range(1000))
    ci = (round(boots[50], 4), round(boots[949], 4))
    return {"n": n, "first_date": out[0]["date"], "last_date": out[-1]["date"],
            "logloss_gain_vs_market": round(sum(gains) / n, 4), "logloss_gain_ci90": ci,
            "logloss_market": round(ll_mkt, 4), "logloss_elo": round(ll_elo, 4),
            "logloss_by_w": {str(w): round(v, 4) for w, v in by_w.items()},
            "w_fitted": w_best, "logloss_blend": round(by_w[w_best], 4),
            "sim_in_sample": sim(w_best, MIN_EDGE),
            "sim_out_of_sample": dict(oos, w_from_first_half=w_first, n_games=len(second)),
            "home_win_rate": round(sum(r["y"] for r in out) / n, 3)}


def fit_params(sport: str, finals: List[Dict[str, Any]], season_start: str) -> Dict[str, float]:
    """Pick K / HFA by walk-forward log loss on LAST season only (no peeking at
    the season being judged)."""
    base = PARAMS[sport]
    ks = [base["k"] * f for f in (0.5, 0.75, 1.0, 1.25, 1.5)]
    hs = [base["hfa"] * f for f in (0.0, 0.5, 1.0, 1.5, 2.0)]
    prior = [g for g in finals if g["date"] < season_start]
    best, best_ll = dict(base), None
    for k in ks:
        for h in hs:
            e = Elo(sport, k, h, base["carry"])
            ll, n, first_season = 0.0, 0, None
            for g in prior:
                s = _season_key(sport, g["date"])
                first_season = first_season or s
                e.new_season(s)
                # score only after a burn-in (first 1/4 of the prior season)
                if g["home_score"] != g["away_score"] and n >= 0:
                    ll += _ll(e.p_home(g["home"], g["away"], g.get("neutral")),
                              1.0 if g["home_score"] > g["away_score"] else 0.0)
                    n += 1
                e.update(g)
            if n and (best_ll is None or ll / n < best_ll):
                best_ll, best = ll / n, {"k": k, "hfa": h, "carry": base["carry"]}
    best["prior_logloss"] = round(best_ll, 4) if best_ll else None
    return best


# ------------------------------------------------------------------ lines ----
def grow_lines(sport: str) -> Dict[str, Any]:
    """Merge today's DK pre-game snapshots into dk_lines_<sport>.json."""
    p = os.path.join(DATA_DIR, f"dk_lines_{sport}.json")
    doc = _load(p) or {"sport": sport.upper(), "events": {}}
    ev = doc.setdefault("events", {})
    odds = _load(os.path.join(DATA_DIR, "espn_odds.json"))
    ga = str(odds.get("generated_at"))[:19]
    n = 0
    for g in odds.get("games") or []:
        m = g.get("market") or {}
        if g.get("sport") != sport.upper() or g.get("status") != "pre" or not g.get("event_id") or m.get("ml_home") is None:
            continue
        snap = {k: m.get(k) for k in ("ml_home", "ml_away", "total", "over_price", "under_price", "spread")}
        snap["at"] = ga
        row = ev.setdefault(str(g["event_id"]), {"matchup": g.get("matchup"), "home": g.get("home"),
                                                  "away": g.get("away"), "commence": g.get("commence_time"),
                                                  "open": snap})
        row["close"] = snap
        row["commence"] = g.get("commence_time") or row.get("commence")
        n += 1
    doc["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    doc["n_events"] = len(ev)
    _dump(p, doc)
    return ev


# ------------------------------------------------------------------- run ----
def run_sport(sport: str) -> Dict[str, Any]:
    finals = load_finals(sport)
    lines = grow_lines(sport)
    today = dt.date.today()
    season_start = {"nfl": f"{_season_key('nfl', today.isoformat())}-08-01",
                    "nhl": f"{_season_key('nhl', today.isoformat())}-09-01"}[sport]
    params = fit_params(sport, finals, season_start)
    bt = backtest(sport, finals, lines, params)
    w = bt.get("w_fitted", 0.0) if bt.get("n", 0) >= MIN_BACKTEST_N else 0.0
    oos = bt.get("sim_out_of_sample") or {}
    beats_market = bool(bt.get("n", 0) >= MIN_BACKTEST_N and bt.get("logloss_blend", 9) < bt.get("logloss_market", 0))
    ci_lo = (bt.get("logloss_gain_ci90") or (0, 0))[0]
    proven = beats_market and ci_lo > 0 and (oos.get("bets") or 0) >= 50 and (oos.get("roi_pct") or -1) > 0
    if not beats_market:
        verdict = ("NO EDGE: the model adds nothing to DraftKings' price on this season's games (fitted "
                   "weight 0) -- no picks")
    elif not proven:
        verdict = ("UNPROVEN: the blend edges the DK close on this season's games, but the gain's 90% interval "
                   f"includes zero or the out-of-sample test is under 50 bets ({oos.get('bets') or 0}). Picks are "
                   "logged at the DK price as a forward test -- NOT curated")
    else:
        verdict = ("PROMISING: the gain over the DK close is outside noise and the out-of-sample half is "
                   "profitable over 50+ bets -- curated only on Brandon's call")
    elo = replay(sport, finals, params)
    board = []
    odds = _load(os.path.join(DATA_DIR, "espn_odds.json"))
    for g in odds.get("games") or []:
        m = g.get("market") or {}
        if g.get("sport") != sport.upper() or g.get("status") != "pre" or m.get("ml_home") is None:
            continue
        h, a = _norm_team(sport, g.get("home")), _norm_team(sport, g.get("away"))
        p_elo = elo.p_home(h, a, g.get("neutral"))
        p_mkt = _no_vig(m.get("ml_home"), m.get("ml_away"))
        if p_mkt is None:
            continue
        p = _sig(_logit(p_mkt) + w * (_logit(p_elo) - _logit(p_mkt)))
        row = {"event_id": g.get("event_id"), "matchup": f"{a} @ {h}", "commence": g.get("commence_time"),
               "p_home_elo": round(p_elo, 4), "p_home_dk": round(p_mkt, 4), "p_home": round(p, 4),
               "ml_home": m.get("ml_home"), "ml_away": m.get("ml_away"), "pick": None}
        best = None
        for side, pp, px in (("home", p, m.get("ml_home")), ("away", 1 - p, m.get("ml_away"))):
            dd = _dec(px)
            if dd and w > 0:
                ev = pp * dd - 1
                if ev >= MIN_EDGE and (best is None or ev > best["ev"]):
                    best = {"side": side, "market": f"ML_{side.upper()}", "team": h if side == "home" else a,
                            "prob": round(pp, 4), "book_american": px, "fair_american": _american(pp),
                            "ev": round(ev, 4)}
        row["pick"] = best
        try:
            ct = dt.datetime.fromisoformat(str(g.get("commence_time")).replace("Z", "+00:00"))
            row["game_date"] = (ct - dt.timedelta(hours=4)).date().isoformat()
        except Exception:
            row["game_date"] = None
        board.append(row)
    return {"params": params, "w_used": w, "backtest": bt, "beats_market": beats_market, "proven": proven,
            "verdict": verdict, "ratings": {t: round(v, 1) for t, v in sorted(elo.r.items(), key=lambda x: -x[1])},
            "board": board, "n_picks": sum(1 for r in board if r["pick"])}


def run() -> Dict[str, Any]:
    out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
           "method": ("Margin-of-victory Elo (K/HFA fitted on last season), blended toward the DraftKings "
                      "no-vig price by a walk-forward-fitted weight; picks only at >= "
                      f"{int(MIN_EDGE * 100)}% EV at the DK price."),
           "sports": {}}
    for s in ("nfl", "nhl"):
        try:
            out["sports"][s] = run_sport(s)
        except Exception as e:   # a desk failure must not take the other down
            out["sports"][s] = {"error": repr(e), "board": [], "n_picks": 0}
    _dump(OUT, out)
    return out


if __name__ == "__main__":
    o = run()
    for s, d in o["sports"].items():
        bt = d.get("backtest") or {}
        print(f"{s.upper()}: params {d.get('params')} | backtest n={bt.get('n')} "
              f"LL mkt {bt.get('logloss_market')} elo {bt.get('logloss_elo')} blend {bt.get('logloss_blend')} "
              f"gain {bt.get('logloss_gain_vs_market')} ci90 {bt.get('logloss_gain_ci90')} "
              f"(w={bt.get('w_fitted')}) | in-sample {bt.get('sim_in_sample')} | OOS {bt.get('sim_out_of_sample')}")
        print(f"   w used {d.get('w_used')} -> {d.get('n_picks')} picks today | {d.get('verdict')}")
