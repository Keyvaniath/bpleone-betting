"""
EdgeStat -- The Board (2026-11-12).

Brandon: "we want to have odds and bets for each sport and game and grade it
and then have our alpha picks which is our 3-5 highest graded scored picks
from each day in addition to being able to sort by sport -- copy the UI of
something similar to an underdog or prizepicks with how easy it is."

One artifact, data/board.json, for board.html:

  games[]   every pre-game NFL / NBA / NHL game on the DraftKings board (MLB
            joins when its season opens): the moneylines, the total and its
            over/under prices, our side, a GRADE and a SCORE, and one plain
            reason. Prices are DraftKings' via ESPN, each with the time it was
            observed; a game with no live quote is not listed as a bet.
  picks[]   the games that carry a bet (grades A, B, C), flat, for the
            pricing guard and the ledger.
  alpha[]   the day's Alpha picks: the 3 to 5 highest-scored bets. Provisional
            until 11:00 ET, then LOCKED (data/board_alpha_log.json, append
            only): a locked pick is never removed or re-priced; if the list
            has fewer than five it can still grow with bets that appear later.

THE GRADE IS THE DESK'S EVIDENCE, NOT A FEELING. It is fixed by rule and was
written down before any result was scored (docs/ODDS-INTEGRITY.md):

  A  85-100  a desk pick from a PROMISING desk (edge outside noise, validated
             out of sample).            score = 85 + min(15, 50 * EV/sigma)
  B  65-80   a desk pick from an UNPROVEN desk (forward test: the blend beats
             the DraftKings close but not yet outside noise).
                                        score = 65 + min(15, 50 * EV/sigma)
             EV/sigma is RISK-ADJUSTED (2026-11-12, Brandon: "not risk adjusted
             rewards?"): expected profit per unit bet divided by the standard
             deviation of that bet's result, at the desk's probability and the
             DraftKings price -- a per-bet Sharpe ratio. Raw EV (the first rule)
             ranked a +440 longshot with 17% EV above a -440 favourite with 9%
             EV; per unit of risk the favourite is three times better. 0.30 or
             more fills the band. Changed before any board bet had settled.
  C  40-60   a model lean: the favourite the model AND DraftKings agree on
             (game_lines_desk.LEAN_RULE). Not an edge -- expected value is the
             book's margin.             score = 40 + 20 * (min(p) - .55) / .25
  D  25/35   NO BET. The model's side is shown for information only: either
             model and market agree but outside the lean rule (35), or they
             disagree (25) -- and betting the model against DraftKings has
             lost this season. Never logged as a pick.
  HOLD       no side: the desk is waiting on a quarterback or a day-to-day
             player. Never logged.

A, B and C are bets: logged in the ledger at the DraftKings price (source
"board_pick"; the add-guard folds it onto the desk's or the lean's own row)
and graded on the final score. Alpha picks are tagged "board_alpha". Neither
is a curated source, and neither counts as calibration evidence for the
moneyline families (prob_calibration.judged).
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional

import play_of_day as pod
import quotes as _q

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUT = os.path.join(DATA_DIR, "board.json")
ALPHA_LOG = os.path.join(DATA_DIR, "board_alpha_log.json")

SPORTS = ("NFL", "NBA", "NHL", "MLB")
ALPHA_MAX, ALPHA_MIN = 5, 3
ALPHA_LOCK_HOUR_ET = 11          # the day's Alpha list locks at the first run at or after 11:00 ET
DAYS_AHEAD = 7
ALPHA_LOG_KEEP_DAYS = 120

GRADE_TEXT = {
    "A": "Validated desk pick: the edge is outside noise and held up out of sample.",
    "B": "Forward-test desk pick: the model beats the DraftKings close this season, not yet outside noise.",
    "C": "Model lean: the favourite the model and DraftKings both favour. Not an edge.",
    "D": "No bet: the model's side, shown for information only.",
    "HOLD": "On hold: the desk is waiting on a lineup question.",
}


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _load_alpha_log():
    """(log, readable). A missing file is an empty log; a file that exists but does not
    parse is NOT -- the caller must not lock or write over it."""
    if not os.path.exists(ALPHA_LOG):
        return {}, True
    try:
        with open(ALPHA_LOG, encoding="utf-8") as f:
            d = json.load(f)
        return (d, True) if isinstance(d, dict) else ({}, False)
    except Exception:
        return {}, False


def _now_et(now: dt.datetime) -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return now - dt.timedelta(hours=5)


def risk(p: Optional[float], american) -> Optional[Dict[str, Any]]:
    """Per-unit numbers for one bet at probability p and an American price: the payout,
    expected value, the standard deviation of the result, EV per unit of risk (a per-bet
    Sharpe ratio) and the Kelly fraction. None if either input is missing."""
    try:
        p, a = float(p), float(american)
    except (TypeError, ValueError):
        return None
    if not 0 < p < 1 or a == 0:
        return None
    d = 1 + a / 100 if a > 0 else 1 + 100 / abs(a)
    ev = p * d - 1
    sigma = d * (p * (1 - p)) ** 0.5
    ra = pod.risk_adj(p, a)                        # one definition, shared with the Play of the Day
    return {"win_prob": round(p, 4), "pays": round(d - 1, 4), "ev_pct": round(ev * 100, 2),
            "sigma": round(sigma, 4), "risk_adj": round(ra, 4) if ra is not None else None,
            "kelly": round(ev / (d - 1), 4), "favorite": a < 0}


RISK_ADJ_FULL = 0.30          # EV/sigma that fills a band (a strong single bet)


def score_pick(kind: str, tier: Optional[int], ev_pct: Optional[float], lean_score: Optional[float],
               risk_adj: Optional[float] = None) -> Dict[str, Any]:
    """Grade and score for a bet. The whole rule; nothing else moves a score.
    Desk picks rank on risk-adjusted EV (EV/sigma); a missing risk number falls back to
    raw EV so a score is never invented."""
    if risk_adj is not None:
        bonus = min(15.0, max(0.0, 15.0 * float(risk_adj) / RISK_ADJ_FULL))
    else:
        bonus = min(15.0, max(0.0, float(ev_pct or 0)))
    if kind == "desk" and tier == 1:
        return {"grade": "A", "score": int(round(85 + bonus))}
    if kind == "desk":
        return {"grade": "B", "score": int(round(65 + bonus))}
    frac = min(1.0, max(0.0, (float(lean_score or 0.55) - 0.55) / 0.25))
    return {"grade": "C", "score": int(round(40 + 20 * frac))}


def _side_names(matchup: str) -> Dict[str, str]:
    parts = [x.strip() for x in str(matchup or "").split("@", 1)]
    return {"away": parts[0], "home": parts[1]} if len(parts) == 2 else {"away": "", "home": ""}


def _no_bet(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Grade D: the model's side on a game with no bet, and why it is not one."""
    pm, pk = row.get("p_home_elo"), row.get("p_home_dk")
    if pm is None or pk is None:
        return None
    names = _side_names(row.get("matchup"))
    side = "home" if pm >= 0.5 else "away"
    mkt_side = "home" if pk >= 0.5 else "away"
    p_side = pm if side == "home" else 1 - pm
    k_side = pk if side == "home" else 1 - pk
    price = row.get("ml_home") if side == "home" else row.get("ml_away")
    if side == mkt_side:
        why = (f"Model ({p_side * 100:.0f}%) and DraftKings ({k_side * 100:.0f}%) both lean {names[side]}, but outside the "
               "lean rule: under 55% on one of them, or priced shorter than -200. No bet.")
        score = 35
    else:
        why = (f"The model makes {names[side]} the favourite ({p_side * 100:.0f}%); DraftKings makes {names[mkt_side]} the "
               f"favourite ({(1 - k_side) * 100:.0f}%). Betting the model against DraftKings has lost this season. No bet.")
        score = 25
    return {"side": side, "team": names[side], "market": f"ML_{side.upper()}", "book_american": price,
            "prob_model": round(p_side, 4), "prob_dk": round(k_side, 4), "agrees_with_market": side == mkt_side,
            "grade": "D", "score": score, "reason": why}


def _reason(c: Dict[str, Any]) -> str:
    p, dk, ev = c.get("model_prob"), c.get("dk_implied"), c.get("ev_pct")
    if c.get("tier") == 4:
        return (f"Model {p * 100:.0f}% and DraftKings {dk * 100:.0f}% both make {c.get('team')} the favourite. "
                f"A lean, not an edge: expected value at this price is about {ev:+.1f}%.")
    lab = "Validated desk pick" if c.get("tier") == 1 else "Forward-test desk pick"
    return (f"{lab}: desk {p * 100:.0f}% vs DraftKings {dk * 100:.0f}%, EV {ev:+.1f}% at the DraftKings price."
            + (" The desk has not yet proven this edge." if c.get("tier") == 2 else ""))


def lineup(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """(2026-11-13) Who is playing, from the desk's own lineup work: the NHL starting goalie
    (confirmed / expected / projected, and whether it is the backup), the NFL starting QB
    (and whether he is the regular), the NBA rotation players on the injury report.
    Display text per side; None when the desk has nothing."""
    out = {}
    g, q, a = r.get("goalies"), r.get("qbs"), r.get("avail")
    if g:
        for side in ("away", "home"):
            x = g.get(side) or {}
            if not x.get("projected"):
                continue
            st = {"confirmed": "confirmed", "expected": "expected"}.get(x.get("status"), "projected")
            # "primary" = the goalie with most of the team's recent starts (not a reputation);
            # names are accent-folded: the store has "Meriläinen", ESPN "Merilainen"
            def _fold(v):
                import unicodedata
                return "".join(c for c in unicodedata.normalize("NFKD", str(v or "")) if not unicodedata.combining(c)).lower()
            backup = bool(x.get("primary")) and \
                _fold(x.get("projected")).split(".")[-1].strip() not in _fold(x.get("primary"))
            out[side] = {"text": f"G {x['projected']} ({st})" + (" · BACKUP" if backup else "") + (" · B2B" if x.get("back_to_back") else ""),
                         "flag": bool(backup)}
        out["kind"] = "goalies"
    elif q:
        for side in ("away", "home"):
            x = q.get(side) or {}
            if not x.get("qb"):
                continue
            notreg = x.get("regular") and x.get("qb") != x.get("regular")
            stt = "" if (x.get("status") or "active") == "active" else f" ({x['status']})"
            out[side] = {"text": f"QB {x['qb']}{stt}" + (f" · not the regular ({x['regular']})" if notreg else "")
                                 + ("" if x.get("certain", True) else " · uncertain"),
                         "flag": bool(notreg or not x.get("certain", True))}
        out["kind"] = "qbs"
    elif a:
        for side in ("away", "home"):
            x = a.get(side) or {}
            ls = [i for i in (x.get("listed") or []) if abs(float(i.get("value") or 0)) >= 1][:3]
            out[side] = {"text": ("Injury list: " + ", ".join(
                f"{i['name']}{' (DTD)' if 'day' in str(i.get('status')).lower() else ''}" for i in ls)) if ls else "no rotation player listed",
                         "flag": bool(ls) and float(x.get("abnormal") or 0) >= 3}
        out["kind"] = "injuries"
    return out if any(k in out for k in ("away", "home")) else None


def hold_pct(ml_a, ml_b) -> Optional[float]:
    """The bookmaker's margin in a two-way price: sum of implied probabilities minus 1."""
    try:
        ps = [(100 / (a + 100)) if a > 0 else (-a / (-a + 100)) for a in (float(ml_a), float(ml_b))]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return round((sum(ps) - 1) * 100, 2)


def _signal_view(s: Optional[Dict[str, Any]], now_home, now_away, names: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """A recorded line-move signal with a side, for the card: the side, the price it was recorded
    at, the model-vs-DraftKings gap at the open, and the current price of that side with the move
    in no-vig points (+ = toward the signal's side). None when the game had no signal."""
    if not s or not s.get("side") or s.get("price") is None:
        return None
    side = s["side"]
    now = now_home if side == "home" else now_away
    out = {"side": side, "team": names.get(side), "price": s.get("price"), "gap_pts": round(abs(float(s.get("gap") or 0)) * 100, 1),
           "seen_at": s.get("seen_at"), "now_price": now, "clv_pts": None}
    try:
        d0 = (1 + float(s["price"]) / 100) if float(s["price"]) > 0 else (1 + 100 / -float(s["price"]))
        d1 = (1 + float(now) / 100) if float(now) > 0 else (1 + 100 / -float(now))
        out["clv_pts"] = round((1 / d1 - 1 / d0) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    if s.get("result"):
        out["result"] = s.get("result")
    return out


def _nv_home(h, a) -> Optional[float]:
    try:
        h, a = float(h), float(a)
        ph = (100 / (h + 100)) if h > 0 else (-h / (-h + 100))
        pa = (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
        return round(ph / (ph + pa), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def price_series(hist: List[Dict[str, Any]], dk_open=None, now_home=None, now_away=None) -> List[List[Any]]:
    """(2026-11-13) The home side's no-vig probability through the day, for the card's line chart:
    DraftKings' opener (no timestamp) first, then every snapshot whose price changed
    (espn_odds odds_history.json), then the current price. [[iso_ts_or_None, p_home], ...]"""
    out: List[List[Any]] = []
    if dk_open and dk_open[0] is not None and dk_open[1] is not None:
        p = _nv_home(*dk_open)
        if p is not None:
            out.append([None, p])
    for s in hist or []:
        p = _nv_home(s.get("ml_home"), s.get("ml_away"))
        if p is not None:
            out.append([s.get("ts"), p])
    p = _nv_home(now_home, now_away)
    if p is not None and (not out or out[-1][1] != p):
        out.append(["now", p])
    return out if len(out) >= 2 else []


def line_move(open_snap: Dict[str, Any], now_home, now_away, dk_open=None,
              dk_open_lines: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Where the moneyline opened and how far the no-vig home probability has moved since, in
    points. + = toward home. (2026-11-13) The open is DraftKings' own opener when ESPN carries it
    (dk_open = (home, away)); else the first snapshot we hold. Our first-seen price is kept
    alongside: it is the first price we could actually have bet (move signals use it)."""
    dko = dk_open if (dk_open and dk_open[0] is not None and dk_open[1] is not None) else None
    if not open_snap and not dko:
        return None
    open_snap = open_snap or {}
    oh, oa = (dko if dko else (open_snap.get("ml_home"), open_snap.get("ml_away")))
    try:
        def nv(h, a):
            ph = (100 / (h + 100)) if h > 0 else (-h / (-h + 100))
            pa = (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
            return ph / (ph + pa)
        move = round((nv(float(now_home), float(now_away)) - nv(float(oh), float(oa))) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return {"open_ml_home": oh, "open_ml_away": oa, "open_at": open_snap.get("at"), "move_home_pts": move,
            "open_source": "draftkings" if dko else "first_seen",
            "first_seen_ml_home": open_snap.get("ml_home"), "first_seen_ml_away": open_snap.get("ml_away"),
            # with DraftKings' opener, the opening total / spread come from the same source (never
            # a DK opening moneyline beside our first-seen spread: NY -130 opened with IND +2.5, not +7.5)
            "open_total": ((dk_open_lines or {}).get("total_open") if dko else open_snap.get("total")),
            "open_spread_home": ((dk_open_lines or {}).get("spread_home_open") if dko else open_snap.get("spread"))}


def build_games(gld: Dict[str, Any], odds: Dict[str, Any], now: dt.datetime, today_et: str) -> List[Dict[str, Any]]:
    # keyed by event id, so the night-before slate (espn_odds.games_next_day) is safe to include
    by_eid = {str(g.get("event_id")): g for g in (list(odds.get("games") or []) + list(odds.get("games_next_day") or []))
              if g.get("event_id")}
    # (2026-11-13) the desk's OPEN logged picks on each game and how they stand against the
    # current DraftKings line (game_lines_desk.forward_test): CLV as it builds, before the close.
    logged: Dict[Any, List[Dict[str, Any]]] = {}
    for _sp, _d in (gld.get("sports") or {}).items():
        for _p in ((_d.get("forward_test") or {}).get("picks") or []):
            if _p.get("close_final") or _p.get("clv_pts") is None:
                continue
            # keyed by event id (2026-11-13 review): the same pairing can meet twice inside the
            # 7-day window; the matchup is only a fallback for rows logged without an id
            logged.setdefault((_sp.upper(), _p.get("event_id") or _p.get("matchup")), []).append(
                {"market": _p.get("market"), "logged_price": _p.get("logged_price"), "now_price": _p.get("close_price"),
                 "clv_pts": _p.get("clv_pts")})
    # (2026-11-13) opening prices: the first DraftKings snapshot the desk recorded for each game
    opens = {}
    for _sp in SPORTS:
        for _eid, _ev in ((_load(f"dk_lines_{_sp.lower()}.json").get("events") or {}).items()):
            opens[(_sp, str(_eid))] = _ev.get("open") or {}
    # the snapshot history per game (sport|matchup|UTC date of the start), for the line chart
    hist = (_load("odds_history.json").get("history") or {})
    # (2026-11-13) line-move signals (game_lines_desk.move_signals): a FORWARD TEST, never a pick.
    # Shown on the card with the price it was recorded at and how that side's price has moved since.
    sigs = (_load("move_signals.json").get("signals") or {})
    cands: Dict[Any, Dict[str, Any]] = {}
    for c in pod._desk_candidates(gld, now) + pod._lean_candidates(gld, now):
        cands[(c["sport"], str(c.get("event_id")))] = c
    last_day = (dt.date.fromisoformat(today_et) + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    games = []
    for sp, d in (gld.get("sports") or {}).items():
        sport = sp.upper()
        if sport not in SPORTS:
            continue
        verdict = str(d.get("verdict") or "").split(":")[0].strip().upper() or "UNKNOWN"
        for r in d.get("board") or []:
            gd = r.get("game_date")
            if not gd or gd < today_et or gd > last_day:
                continue
            eid = str(r.get("event_id"))
            m = (by_eid.get(eid) or {}).get("market") or {}
            names = _side_names(r.get("matchup"))
            pm, pk = r.get("p_home_elo"), r.get("p_home_dk")
            q = r.get("quote") or {}
            # is the game still a live pre-start quote? (any real price will do for the check)
            ok_game, why_game = _q.actionable(dict(q, american=r.get("ml_home")), now=now) if q else (False, "no_quote")
            ok_game, why_game = pod._dk_only(q, ok_game, why_game)       # the board says DraftKings: nothing else is graded
            g = {
                "id": eid, "sport": sport, "date": gd, "start": r.get("commence"),
                "away": names["away"], "home": names["home"], "matchup": r.get("matchup"), "page": pod.SPORT_PAGE.get(sport),
                "odds": {"book": "DraftKings", "ml_away": r.get("ml_away"), "ml_home": r.get("ml_home"),
                         "total": m.get("total"), "over_price": m.get("over_price"), "under_price": m.get("under_price"),
                         "spread_home": m.get("spread"), "observed_at": q.get("observed_at"), "snapshot_id": q.get("snapshot_id"),
                         "hold_pct": hold_pct(r.get("ml_home"), r.get("ml_away")),
                         "spread_home_line": m.get("spread_home_line"), "spread_home_price": m.get("spread_home_price"),
                         "spread_away_line": m.get("spread_away_line"), "spread_away_price": m.get("spread_away_price"),
                         "move": line_move(opens.get((sport, eid)), r.get("ml_home"), r.get("ml_away"),
                                           (m.get("ml_home_open"), m.get("ml_away_open")), m),
                         "series": price_series(hist.get(f"{sport}|{r.get('matchup')}|{str(r.get('commence') or '')[:10]}"),
                                                (m.get("ml_home_open"), m.get("ml_away_open")), r.get("ml_home"), r.get("ml_away"))},
                "model": {"p_home": pm, "p_away": (round(1 - pm, 4) if pm is not None else None)},
                "market": {"p_home_no_vig": pk, "p_away_no_vig": (round(1 - pk, 4) if pk is not None else None)},
                "desk_verdict": verdict, "live_quote": bool(ok_game), "quote_issue": None if ok_game else why_game,
                "desk_logged": [dict(x, team=names["home"] if str(x["market"]).upper().endswith("HOME") else names["away"])
                                for x in (logged.get((sport, eid)) or logged.get((sport, r.get("matchup"))) or [])],
                "pick": None, "model_side": None, "hold": None, "grade": None, "score": None, "reason": None,
                "lineup": lineup(r),
                "signal": _signal_view(sigs.get(f"{sport.lower()}:{eid}"), r.get("ml_home"), r.get("ml_away"), names),
            }
            c = cands.get((sport, eid))
            if not ok_game:
                # no live pre-start quote: say so and grade nothing (a stale price cannot back a bet
                # OR a "no bet" verdict -- the D text below describes today's price, not an old one)
                g.update(reason="No live DraftKings quote for this game right now (" + str(why_game).replace("_", " ")
                                + "). No grade until the price refreshes.")
            elif c and c.get("actionable"):
                kind = "lean" if c.get("tier") == 4 else "desk"
                # risk numbers at the probability the grade rests on: the desk's for a desk pick;
                # DraftKings' own no-vig for a lean (a lean claims no edge, so it is priced at the market)
                rk = risk(c.get("model_prob") if kind == "desk" else c.get("dk_implied"), c.get("book_american"))
                gs = score_pick(kind, c.get("tier"), c.get("ev_pct"), c.get("lean_score"),
                                (rk or {}).get("risk_adj") if kind == "desk" else None)
                g["pick"] = {
                    "kind": kind, "tier": c.get("tier"), "side": c.get("side"), "team": c.get("team"), "market": c.get("market"),
                    "book_american": c.get("book_american"), "fair_american": c.get("fair_american"),
                    "prob_model": c.get("model_prob"), "prob_dk": c.get("dk_implied"), "ev_pct": c.get("ev_pct"),
                    "lean_record": c.get("lean_record"), "risk": rk,
                }
                g.update(grade=gs["grade"], score=gs["score"], reason=_reason(c))
            elif str(r.get("pick_blocked") or "").lower().startswith(("qb uncertain", "availability uncertain")):
                g.update(hold=r.get("pick_blocked"), grade="HOLD",
                         reason="On hold, no side: " + str(r.get("pick_blocked")).split(" -- ", 1)[-1][:160])
            else:
                nb = _no_bet(r)
                if nb:
                    g.update(model_side={k: v for k, v in nb.items() if k not in ("grade", "score", "reason")},
                             grade=nb["grade"], score=nb["score"], reason=nb["reason"])
            games.append(g)
    order = {s: i for i, s in enumerate(SPORTS)}
    games.sort(key=lambda g: (g["date"], str(g.get("start") or ""), order.get(g["sport"], 9), g["matchup"] or ""))
    return games


COLLEGE = ("NCAAF", "NCAAB")
ODDS_ONLY = ("NCAAB",)          # no model yet: DraftKings odds only, clearly labelled


def build_college(odds: Dict[str, Any], now: dt.datetime, today_et: str) -> List[Dict[str, Any]]:
    """(2026-11-13) College football on the board: every FBS game cfb_model rates, with the
    DraftKings odds and the model's side -- FOR INFORMATION, never a bet. cfb_model's own
    benchmark says DraftKings' closing line is sharper than it (2025: Brier 0.187 vs 0.203),
    so under the board's rules a college game is a "no bet" whatever the model says. Its
    experimental edges stay where they are (the Play of the Day's tier 3)."""
    cfb = _load("cfb_model.json")
    if not cfb.get("board_fresh"):
        return []
    by_mu: Dict[Any, Dict[str, Any]] = {}
    for g in odds.get("games") or []:
        if g.get("sport") == "NCAAF" and g.get("status") == "pre":
            by_mu[(g.get("matchup"), str(g.get("commence_time") or "")[:16])] = g
    last_day = (dt.date.fromisoformat(today_et) + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    out = []
    for c in cfb.get("games") or []:
        if c.get("status") != "pre" or not c.get("rated") or c.get("model_p_home") is None:
            continue
        o = by_mu.get((c.get("matchup"), str(c.get("commence_time") or "")[:16])) or {}
        m = o.get("market") or {}
        if m.get("ml_home") is None or m.get("ml_away") is None:
            continue                                   # no DraftKings moneyline: nothing to show
        gd = pod._et_date(c.get("commence_time"))
        if not gd or gd < today_et or gd > last_day:
            continue
        q = {"provenance": "book_snapshot", "book": str(m.get("book") or "draftkings").lower(), "american": m.get("ml_home"),
             "observed_at": odds.get("generated_at"), "scheduled_start": c.get("commence_time"), "event_id": o.get("event_id")}
        ok, why = _q.actionable(q, now=now)
        ok, why = pod._dk_only(q, ok, why)
        pm, pk = c["model_p_home"], gld_no_vig(m.get("ml_home"), m.get("ml_away"))
        g = {"id": str(o.get("event_id") or c.get("matchup")), "sport": "NCAAF", "date": gd, "start": c.get("commence_time"),
             "away": c.get("away"), "home": c.get("home"), "matchup": c.get("matchup"), "page": "ncaaf.html",
             "odds": {"book": "DraftKings", "ml_away": m.get("ml_away"), "ml_home": m.get("ml_home"), "total": m.get("total"),
                      "over_price": m.get("over_price"), "under_price": m.get("under_price"), "spread_home": m.get("spread"),
                      "observed_at": odds.get("generated_at"), "snapshot_id": None,
                      "hold_pct": hold_pct(m.get("ml_home"), m.get("ml_away")),
                      "spread_home_line": m.get("spread_home_line"), "spread_home_price": m.get("spread_home_price"),
                      "spread_away_line": m.get("spread_away_line"), "spread_away_price": m.get("spread_away_price"),
                      "move": None},
             "model": {"p_home": pm, "p_away": round(1 - pm, 4)},
             "market": {"p_home_no_vig": pk, "p_away_no_vig": (round(1 - pk, 4) if pk is not None else None)},
             "desk_verdict": "EXPERIMENTAL", "live_quote": bool(ok), "quote_issue": None if ok else why,
             "desk_logged": [], "lineup": None, "pick": None, "model_side": None, "hold": None,
             "grade": None, "score": None, "reason": None, "college": True,
             "ranks": {"home": c.get("home_rank"), "away": c.get("away_rank")}}
        if not ok:
            g["reason"] = "No live DraftKings quote for this game right now. No grade until the price refreshes."
        elif pk is not None:
            side = "home" if pm >= 0.5 else "away"
            p_side = pm if side == "home" else 1 - pm
            k_side = pk if side == "home" else 1 - pk
            g["model_side"] = {"side": side, "team": c.get(side), "market": f"ML_{side.upper()}",
                               "book_american": m.get("ml_home") if side == "home" else m.get("ml_away"),
                               "prob_model": round(p_side, 4), "prob_dk": round(k_side, 4),
                               "agrees_with_market": (pk >= 0.5) == (pm >= 0.5)}
            g.update(grade="D", score=None,
                     reason=(f"College model {p_side * 100:.0f}% {c.get(side)}, DraftKings {k_side * 100:.0f}%; model spread "
                             f"{c.get('home')} {-(c.get('model_spread_home') or 0):+.1f}. For information only: the closing "
                             "line has been sharper than this model, so no college game is a bet."))
        out.append(g)
    out.sort(key=lambda g: (g["date"], str(g.get("start") or ""), g["matchup"] or ""))
    return out


def build_odds_only(sport: str, odds: Dict[str, Any], now: dt.datetime, today_et: str,
                    gld: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """(2026-11-13) A college sport with DraftKings odds: the prices under its own chip, plus the
    research-only desk's model side when it has one (college basketball v1 Elo). Never a bet."""
    last_day = (dt.date.fromisoformat(today_et) + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    desk = {str(r.get("event_id")): r for r in ((((gld or {}).get("sports") or {}).get(sport.lower()) or {}).get("board") or [])}
    out = []
    for o in odds.get("games") or []:
        m = o.get("market") or {}
        if o.get("sport") != sport or o.get("status") != "pre" or m.get("ml_home") is None or m.get("ml_away") is None:
            continue
        gd = pod._et_date(o.get("commence_time"))
        if not gd or gd < today_et or gd > last_day:
            continue
        q = {"provenance": "book_snapshot", "book": str(m.get("book") or "draftkings").lower(), "american": m.get("ml_home"),
             "observed_at": odds.get("generated_at"), "scheduled_start": o.get("commence_time"), "event_id": o.get("event_id")}
        ok, why = _q.actionable(q, now=now)
        ok, why = pod._dk_only(q, ok, why)
        pk = gld_no_vig(m.get("ml_home"), m.get("ml_away"))
        pm = (desk.get(str(o.get("event_id"))) or {}).get("p_home_elo")
        out.append({
            "id": str(o.get("event_id") or o.get("matchup")), "sport": sport, "date": gd, "start": o.get("commence_time"),
            "away": o.get("away"), "home": o.get("home"), "matchup": o.get("matchup"), "page": pod.SPORT_PAGE.get(sport),
            "odds": {"book": "DraftKings", "ml_away": m.get("ml_away"), "ml_home": m.get("ml_home"), "total": m.get("total"),
                     "over_price": m.get("over_price"), "under_price": m.get("under_price"), "spread_home": m.get("spread"),
                     "observed_at": odds.get("generated_at"), "snapshot_id": None, "hold_pct": hold_pct(m.get("ml_home"), m.get("ml_away")),
                     "spread_home_line": m.get("spread_home_line"), "spread_home_price": m.get("spread_home_price"),
                     "spread_away_line": m.get("spread_away_line"), "spread_away_price": m.get("spread_away_price"), "move": None},
            "model": {"p_home": pm, "p_away": (round(1 - pm, 4) if pm is not None else None)},
            "market": {"p_home_no_vig": pk, "p_away_no_vig": (round(1 - pk, 4) if pk is not None else None)},
            "desk_verdict": "RESEARCH ONLY" if pm is not None else "NO MODEL", "live_quote": bool(ok), "quote_issue": None if ok else why,
            "desk_logged": [], "lineup": None, "pick": None, "model_side": None, "hold": None, "grade": None, "score": None,
            "college": True, "odds_only": pm is None,
            "reason": ("DraftKings odds only: we have no model for this game, so there is no side and no bet." if pm is None else
                       f"Research-only college model: {max(pm, 1 - pm) * 100:.0f}% {o.get('home') if pm >= 0.5 else o.get('away')}"
                       f" vs DraftKings {max(pk or 0, 1 - (pk or 0)) * 100:.0f}% {o.get('home') if (pk or 0) >= 0.5 else o.get('away')}. "
                       "For information only: this desk has no record against DraftKings yet, so no college game is a bet.")})
        if pm is not None and pk is not None and ok:
            side = "home" if pm >= 0.5 else "away"
            out[-1]["model_side"] = {"side": side, "team": o.get(side), "market": f"ML_{side.upper()}",
                                     "book_american": m.get("ml_home") if side == "home" else m.get("ml_away"),
                                     "prob_model": round(pm if side == "home" else 1 - pm, 4),
                                     "prob_dk": round(pk if side == "home" else 1 - pk, 4),
                                     "agrees_with_market": (pk >= 0.5) == (pm >= 0.5)}
            out[-1]["grade"] = "D"
    out.sort(key=lambda g: (g["date"], str(g.get("start") or ""), g["matchup"] or ""))
    return out


def gld_no_vig(h, a):
    try:
        ph = (100 / (h + 100)) if h > 0 else (-h / (-h + 100))
        pa = (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
        return round(ph / (ph + pa), 4)
    except (TypeError, ZeroDivisionError):
        return None


def flat_picks(games: List[Dict[str, Any]], gld: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The bets (A/B/C) as flat rows: what the pricing guard checks and the ledger logs."""
    quotes = {}
    for sp, d in (gld.get("sports") or {}).items():
        for r in d.get("board") or []:
            quotes[(sp.upper(), str(r.get("event_id")))] = r.get("quote") or {}
    out = []
    for g in games:
        pk = g.get("pick")
        if not pk:
            continue
        q = dict(quotes.get((g["sport"], g["id"])) or {}, american=pk["book_american"])
        out.append({
            "sport": g["sport"], "matchup": g["matchup"], "team": pk["team"], "side": pk["side"], "market": pk["market"],
            "book_american": pk["book_american"], "fair_american": pk.get("fair_american"),
            "model_prob": pk.get("prob_model"), "dk_implied": pk.get("prob_dk"), "ev_pct": pk.get("ev_pct"),
            "kind": pk["kind"], "tier": pk.get("tier"), "grade": g["grade"], "score": g["score"], "reason": g["reason"],
            "risk": pk.get("risk"),
            "event_id": g["id"], "game_date": g["date"], "commence_time": g["start"], "page": g.get("page"),
            "odds_observed_at": q.get("observed_at"), "quote": q,
        })
    return out


def _rank(p: Dict[str, Any]):
    major = SPORTS.index(p["sport"]) if p["sport"] in SPORTS else 9
    return (-(p.get("score") or 0), str(p.get("commence_time") or ""), major, p.get("matchup") or "")


def alpha_for_today(picks: List[Dict[str, Any]], today_et: str, now: dt.datetime) -> Dict[str, Any]:
    """Top 3-5 scored bets of the day. Provisional before 11:00 ET; from the first
    run at or after 11:00 ET the list is locked in board_alpha_log.json -- a locked
    pick is never removed or re-priced, and the list only grows (to five) with
    bets that appear later in the day (a line posted late, a hold lifted)."""
    log, log_ok = _load_alpha_log()
    days = log.setdefault("days", {})
    todays = sorted([p for p in picks if p["game_date"] == today_et], key=_rank)
    et = _now_et(now)
    locked = days.get(today_et)
    keep = ("sport", "matchup", "team", "side", "market", "book_american", "model_prob", "dk_implied", "ev_pct", "kind",
            "tier", "grade", "score", "reason", "event_id", "game_date", "commence_time", "odds_observed_at", "quote", "page",
            "risk")
    if not log_ok:
        # FAIL CLOSED (review 2026-11-12): the lock file exists but cannot be read. Locking now
        # would re-price today's list and overwrite every earlier day. Show a provisional list,
        # write nothing, and let the next run (or a human) see the file as it is.
        alpha = [dict({k: p.get(k) for k in keep}, rank=i + 1, locked=False) for i, p in enumerate(todays[:ALPHA_MAX])]
        return {"status": "provisional", "lock_hour_et": ALPHA_LOCK_HOUR_ET, "locked_at": None, "picks": alpha,
                "note": "The Alpha lock file could not be read, so today's list is shown unlocked and nothing was written."}
    if locked is None and et.date().isoformat() == today_et and et.hour >= ALPHA_LOCK_HOUR_ET and todays:
        locked = {"locked_at": now.isoformat(timespec="seconds").replace("+00:00", ""), "picks": []}
        days[today_et] = locked
    if locked is not None:
        have = {(p["sport"], str(p["event_id"])) for p in locked["picks"]}
        for p in todays:
            if len(locked["picks"]) >= ALPHA_MAX:
                break
            if (p["sport"], str(p["event_id"])) in have:
                continue
            locked["picks"].append(dict({k: p.get(k) for k in keep},
                                        added_at=now.isoformat(timespec="seconds").replace("+00:00", "")))
            have.add((p["sport"], str(p["event_id"])))
        # prune old days, write the log
        cut = (dt.date.fromisoformat(today_et) - dt.timedelta(days=ALPHA_LOG_KEEP_DAYS)).isoformat()
        for k in [k for k in days if k < cut]:
            del days[k]
        log["note"] = ("Append-only lock of each day's Alpha picks (the top-scored bets on The Board). A locked pick "
                       "is never removed or re-priced.")
        tmp = ALPHA_LOG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=1)
        os.replace(tmp, ALPHA_LOG)                                   # atomic: never a half-written lock
        alpha = [dict(p, rank=i + 1, locked=True) for i, p in enumerate(locked["picks"])]
        status = "locked"
    else:
        alpha = [dict({k: p.get(k) for k in keep}, rank=i + 1, locked=False) for i, p in enumerate(todays[:ALPHA_MAX])]
        status = "provisional"
    note = None
    if len(alpha) < ALPHA_MIN:
        note = (f"Only {len(alpha)} bet(s) on today's board so far. An Alpha pick must be a graded bet at a live "
                "DraftKings price; the list is not padded.")
    return {"status": status, "lock_hour_et": ALPHA_LOCK_HOUR_ET, "locked_at": (locked or {}).get("locked_at"),
            "picks": alpha, "note": note}


GRADE_WORD = {"A": "validated", "B": "forward test", "C": "lean"}
POST_MAX = 280
SITE_URL = "betting.bpleone.com/board"


def alpha_post(alpha: Dict[str, Any], today_et: str, odds_observed_at: Optional[str]) -> Optional[Dict[str, Any]]:
    """Copy-ready text for the day's Alpha picks. DRAFT ONLY: nothing posts by itself.
    Only a LOCKED list is offered (a provisional list can still change), every pick
    carries its grade, and a list with any grade C says plainly that a lean is not an edge."""
    picks = alpha.get("picks") or []
    if alpha.get("status") != "locked" or not picks:
        return None
    day = pod._day_label(today_et)
    lines = [f"EdgeStat Alpha picks · {day}"]
    for p in picks:
        lines.append(f"{p['rank']}. {p['sport']} {p['team']} ML {pod._amer(p['book_american'])} ({GRADE_WORD.get(p['grade'], p['grade'])})")
    seen = pod._seen_et(alpha.get("locked_at"))
    note = []
    if any(p["grade"] == "C" for p in picks):
        note.append("A lean is not a proven edge.")
    tail = [((f"DraftKings prices, locked {seen}. " if seen else "DraftKings prices. ") + " ".join(note)).strip(),
            "21+ · not betting advice", SITE_URL]
    text = "\n".join(lines + tail)
    while len(text) > POST_MAX and len(lines) > 2:        # drop the lowest-ranked pick rather than any caveat
        lines.pop()
        text = "\n".join(lines + tail)
    return {"text": text, "chars": len(text), "max_chars": POST_MAX, "fits": len(text) <= POST_MAX,
            "n_picks": len(lines) - 1,
            "note": "Draft only. Nothing posts automatically; a person copies this and presses send."}


def recap_post(results: Optional[Dict[str, Any]], today_et: str) -> Optional[Dict[str, Any]]:
    """Copy-ready recap of the most recent fully graded day's Alpha picks (DRAFT ONLY).
    Every pick with its result, the day's Alpha line and the running Alpha record,
    losses included. None until a day is fully graded."""
    if not results:
        return None
    rows = [r for r in (results.get("recent") or []) if r.get("is_alpha") and r.get("date") and r["date"] < today_et]
    days = sorted({r["date"] for r in rows}, reverse=True)
    day = next((d for d in days if all(r["result"] in ("won", "lost", "push") for r in rows if r["date"] == d)), None)
    if not day:
        return None
    picks = [r for r in rows if r["date"] == day]
    dl = ((results.get("by_day") or {}).get(day) or {}).get("alpha") or {}
    tot = results.get("alpha") or {}
    u = lambda x: ("+" if (x or 0) >= 0 else "-") + f"{abs(x or 0):.2f}u"
    mark = {"won": "W", "lost": "L", "push": "P"}
    lines = [f"EdgeStat Alpha results · {pod._day_label(day)}: {dl.get('wins', 0)}-{dl.get('losses', 0)}, {u(dl.get('net_units'))}"]
    for r in picks:
        lines.append(f"{mark.get(r['result'], '?')} {r['sport']} {r['team']} ML {pod._amer(r['book_american'])}"
                     + (f" ({r['final']})" if r.get("final") else ""))
    # (2026-11-13) closing line value: did the locked price beat DraftKings' last pre-start price?
    cl = [float(r["clv_pts"]) for r in picks if r.get("clv_pts") is not None]
    if cl:
        avg = sum(cl) / len(cl)
        lines.append(f"Beat the DraftKings close on {sum(1 for x in cl if x > 0)} of {len(cl)}"
                     f" (avg {'+' if avg >= 0 else '-'}{abs(avg):.1f} pts).")
    if tot.get("n_settled"):
        lines.append(f"Alpha since {results.get('first_date')}: {tot['wins']}-{tot['losses']}, {u(tot.get('net_units'))}, graded at the locked DraftKings price.")
    if all(r.get("grade") == "C" for r in picks):
        lines.append("All were leans, not proven edges.")
    tail = ["21+ · not betting advice", SITE_URL]
    text = "\n".join(lines + tail)
    if len(text) > POST_MAX:
        # never drop a pick (dropping one could hide a loss): shorten every pick to "W MIN -223"
        # on one line, and only then drop the running-record line
        short = " · ".join(f"{mark.get(r['result'], '?')} {r['sport']} {r['team']} {pod._amer(r['book_american'])}" for r in picks)
        lines = [lines[0], short] + lines[1 + len(picks):]
        text = "\n".join(lines + tail)
        if len(text) > POST_MAX:
            lines = [x for x in lines if not x.startswith("Alpha since")]
            text = "\n".join(lines + tail)
        if len(text) > POST_MAX:
            lines = [x for x in lines if not x.startswith("Beat the DraftKings close")]
            text = "\n".join(lines + tail)
    return {"day": day, "text": text, "chars": len(text), "max_chars": POST_MAX, "fits": len(text) <= POST_MAX,
            "note": "Draft only. Nothing posts automatically; a person copies this and presses send."}


def run(now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)
    today_et = pod._today_et()
    gld = _load("game_lines_desk.json")
    odds = _load("espn_odds.json")
    games = build_games(gld, odds, now, today_et)
    picks = flat_picks(games, gld)                     # bets come from the major-sport desks only
    games = games + build_college(odds, now, today_et)
    for _sp in ODDS_ONLY:
        games = games + build_odds_only(_sp, odds, now, today_et, gld)
    alpha = alpha_for_today(picks, today_et, now)
    alpha_ids = {(p["sport"], str(p["event_id"])) for p in alpha["picks"]}
    for g in games:
        g["alpha_rank"] = next((p["rank"] for p in alpha["picks"] if (p["sport"], str(p["event_id"])) == (g["sport"], g["id"])), None)
    for p in picks:
        p["is_alpha"] = (p["sport"], str(p["event_id"])) in alpha_ids and alpha["status"] == "locked"

    sports = {}
    t = _load("today.json")
    for sp in SPORTS:
        d = (gld.get("sports") or {}).get(sp.lower()) or {}
        gs = [g for g in games if g["sport"] == sp and g["date"] == today_et]
        sports[sp] = {
            "games_today": len(gs), "bets_today": sum(1 for g in gs if g.get("pick")),
            "verdict": str(d.get("verdict") or "").split(":")[0].strip().upper() or None,
            "status": ("off-season" if sp == "MLB" and (t.get("no_games") or not (t.get("games") or [])) else
                       ("no games today" if not gs else "on")),
            "page": pod.SPORT_PAGE.get(sp),
        }
    for sp in COLLEGE:
        gs = [g for g in games if g["sport"] == sp and g["date"] == today_et]
        sports[sp] = {"games_today": len(gs), "bets_today": 0,
                      "verdict": ("RESEARCH ONLY" if any(g.get("model", {}).get("p_home") is not None for g in gs) else "NO MODEL")
                      if sp in ODDS_ONLY else "EXPERIMENTAL",
                      "status": "on" if gs else "no games today", "page": pod.SPORT_PAGE.get(sp), "info_only": True}
    # today is always a day on the board, even after its last game has started: the locked
    # Alpha list and the day's results still belong to it
    days = sorted({g["date"] for g in games} | {today_et})
    payload = {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", ""),
        "date_et": today_et,
        "odds_observed_at": odds.get("generated_at"),
        "book": "DraftKings (via ESPN's scoreboard feed)",
        "grades": GRADE_TEXT,
        "grade_rule": ("A = validated desk pick (85 + up to 15 for risk-adjusted EV). B = forward-test desk pick (65 + up to 15 "
                       "for risk-adjusted EV: expected profit per unit of risk, so a longshot's bigger EV is weighed against "
                       "its bigger swings). "
                       "C = model lean, the favourite model and DraftKings agree on (40 to 60, by how strongly they "
                       "agree); not an edge. D = no bet (model side shown for information). HOLD = waiting on a lineup "
                       "question. Only A, B and C are bets; only they are logged and graded."),
        "sports": sports,
        "days": days,
        "alpha": dict(alpha, post=alpha_post(alpha, today_et, odds.get("generated_at"))),
        "games": games,
        "picks": picks,
        # results written by the ledger's previous run: every board bet graded at the price it was logged at
        # the desk's bet hurdle (game_lines_desk.MIN_EDGE): a desk pick is a bet only at >= this EV,
        # so its "playable to" price is (1 + min_edge) / p, not the zero-EV price
        "desk_min_edge": _desk_min_edge(),
        "results": (_load("ledger_summary.json") or {}).get("board"),
        "recap": recap_post((_load("ledger_summary.json") or {}).get("board"), today_et),
        "counts": {"games": len(games), "games_today": sum(1 for g in games if g["date"] == today_et and not g.get("college")),
                   "college_today": sum(1 for g in games if g["date"] == today_et and g.get("college")),
                   "bets": len(picks), "bets_today": sum(1 for p in picks if p["game_date"] == today_et)},
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return payload


def _desk_min_edge() -> float:
    try:
        import game_lines_desk as _gld
        return float(_gld.MIN_EDGE)
    except Exception:
        return 0.04


def refresh_results() -> Optional[Dict[str, Any]]:
    """(2026-11-13) Re-read the ledger summary into an existing board.json, touching nothing else.
    Every workflow runs board.py BEFORE all_picks_tracker.py (the tracker harvests the board's
    bets), so the results block was always one run stale: a morning's grading reached the board
    only on the next run. The workflows call this right after the tracker."""
    board = _load("board.json")
    if not board or not board.get("date_et"):
        return None
    summ = (_load("ledger_summary.json") or {}).get("board")
    board["results"] = summ
    board["recap"] = recap_post(summ, board["date_et"])
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(board, f, indent=1)
    os.replace(tmp, OUT)
    return board


if __name__ == "__main__":
    import sys as _sys
    if "--results-only" in _sys.argv:
        b = refresh_results()
        r = ((b or {}).get("results") or {}).get("all_bets") or {}
        print(f"[board] results refreshed: {r.get('wins')}-{r.get('losses')}, {r.get('n_pending')} pending" if b else "[board] no board.json to refresh")
        _sys.exit(0)
    p = run()
    c = p["counts"]
    print(f"[board] {p['date_et']}: {c['games_today']} games today ({c['games']} listed), {c['bets_today']} bets today; "
          f"alpha {p['alpha']['status']}: " +
          ", ".join(f"#{a['rank']} {a['sport']} {a['team']} {pod._amer(a['book_american'])} ({a['grade']} {a['score']})"
                    for a in p["alpha"]["picks"]))
