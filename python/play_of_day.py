"""
EdgeStat -- Play of the Day, cross-sport (2026-11-05).

Brandon: "Play of the day can be from any sport -- we prefer it comes from one
of the major 4: NBA or hockey in the fall, football on Saturday / Sunday."

The rule does not change: a play needs a live DraftKings price (quotes.actionable)
and must come from a desk that publishes its validation. What changes is the
pool -- every game-lines desk, not just the MLB slate. One play a day, the best
EV at the DK price, major-4 sports before college. Each play carries the desk's
verdict, which decides its TIER:

  0  MLB Play of the Day from today.json (the original flagship; its own record)
  1  VALIDATED    a desk pick under a PROMISING verdict
  2  FORWARD TEST a desk pick under an UNPROVEN verdict (logged at the DK price,
                  graded like any other pick, never curated) -- the NFL today
  3  EXPERIMENTAL the college-football model-vs-book edge (the close is sharper;
                  tracked, not featured) -- Saturdays with no NFL play
  4  MODEL LEAN   (2026-11-11, Brandon: "a play of the day for each of the 4
                  sports when they play") the desk's lean on a day it has no EV
                  pick: the favourite the model AND DraftKings agree on
                  (game_lines_desk.LEAN_RULE). Not an edge -- expected value at
                  the price is the book's margin -- and labelled that way with
                  its walk-forward record. Ledger source "sport_lean", never
                  curated, never counted in the Play of the Day record.

`sport_plays` = the best play for each major sport that plays today (any tier).
`play` = the single featured play: the best of them, lower tier first, so a
lean is featured only when no desk pick qualifies anywhere.

A desk whose verdict is NO EDGE (NBA, NHL today) makes no picks by rule, so it
cannot produce a play; the page says so rather than inventing one. When nothing
plays TODAY (ET), the next dated desk pick is shown as "next play".

Output: data/play_of_day.json  {play | null, next_play | null, by_sport, ...}
Ledger: all_picks_tracker harvests `play` as source "pod" (the add-guard folds
it onto the desk's own row with also_sources=pod); pod_pl_tracker grades it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional

import quotes as _q

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUT = os.path.join(DATA_DIR, "play_of_day.json")

MAJOR_4 = ("NFL", "NBA", "NHL", "MLB")
SPORT_PAGE = {"NFL": "nfl.html", "NBA": "nba.html", "NHL": "nhl.html", "MLB": "mlb.html",
              "NCAAF": "ncaaf.html", "NCAAB": "ncaab.html"}
TIER_LABEL = {0: "MLB Play of the Day", 1: "validated desk pick", 2: "forward-test play (desk unproven)",
              3: "experimental (college model; the close is sharper)",
              4: "model lean (no proven edge)"}


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (dt.datetime.utcnow() - dt.timedelta(hours=4)).date().isoformat()


def _et_date(iso) -> str:
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        try:
            from zoneinfo import ZoneInfo
            return d.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        except Exception:
            return (d - dt.timedelta(hours=4)).date().isoformat()
    except Exception:
        return ""


def _side_team(matchup: str, side: str) -> str:
    parts = [x.strip() for x in str(matchup or "").split("@", 1)]
    if len(parts) != 2:
        return ""
    return parts[1] if side == "home" else parts[0]


def _desk_candidates(gld: Dict[str, Any], now: dt.datetime) -> List[Dict[str, Any]]:
    out = []
    for sp, d in (gld.get("sports") or {}).items():
        sport = sp.upper()
        verdict = str(d.get("verdict") or "")
        vkey = verdict.split(":")[0].strip().upper() or "UNKNOWN"
        for r in (d.get("board") or []):
            pk = r.get("pick")
            if not pk or not r.get("game_date"):
                continue
            side = pk.get("side") or ("home" if str(pk.get("market", "")).upper().endswith("HOME") else "away")
            price = pk.get("book_american") if pk.get("book_american") is not None else (r.get("ml_home") if side == "home" else r.get("ml_away"))
            # the desk stores the snapshot stamp without the side's price; attach it so the quote is a full one
            q = dict(r.get("quote") or {}, american=price) if r.get("quote") else {}
            ok, why = _q.actionable(q, now=now) if q else (False, "no_quote")
            implied = _q.no_vig_two_way(r.get("ml_home"), r.get("ml_away"))
            p_side = (r.get("p_home") if side == "home" else (1 - r["p_home"] if r.get("p_home") is not None else None))
            if pk.get("prob") is not None:
                p_side = pk["prob"]
            dk_side = implied if side == "home" else (1 - implied if implied is not None else None)
            out.append({
                "sport": sport, "page": SPORT_PAGE.get(sport, "index.html"),
                "matchup": r.get("matchup"), "team": pk.get("team") or _side_team(r.get("matchup"), side),
                "side": side, "market": pk.get("market"),
                "model_prob": p_side, "dk_implied": dk_side,
                "book_american": pk.get("book_american") if pk.get("book_american") is not None else
                                 (r.get("ml_home") if side == "home" else r.get("ml_away")),
                "fair_american": pk.get("fair_american"),
                "ev_pct": round(float(pk.get("ev") or 0) * 100, 2),
                "event_id": r.get("event_id"), "game_date": r.get("game_date"),
                "commence_time": r.get("commence") or q.get("scheduled_start"),
                "odds_observed_at": q.get("observed_at"), "quote": q or None,
                "desk_verdict": vkey, "desk_verdict_text": verdict,
                "desk_model": d.get("model_version"),
                "tier": 1 if d.get("proven") else 2,
                "actionable": bool(ok), "not_actionable_reason": None if ok else why,
                "qb_note": (r.get("qbs") or {}).get(side, {}).get("note") if r.get("qbs") else None,
            })
    return out


def _lean_candidates(gld: Dict[str, Any], now: dt.datetime) -> List[Dict[str, Any]]:
    """Tier 4: the desk's lean on a game it has no EV pick on (the desk writes
    `lean` on the board row under game_lines_desk.LEAN_RULE). Same quote rules
    as any other play: a live, pre-start DraftKings price or it is not shown."""
    out = []
    for sp, d in (gld.get("sports") or {}).items():
        sport = sp.upper()
        verdict = str(d.get("verdict") or "")
        vkey = verdict.split(":")[0].strip().upper() or "UNKNOWN"
        ld = d.get("lean") or {}
        rec = ld.get("backtest") or {}
        for r in (d.get("board") or []):
            ln = r.get("lean")
            if not ln or r.get("pick") or not r.get("game_date") or ln.get("book_american") is None:
                continue
            q = dict(r.get("quote") or {}, american=ln["book_american"]) if r.get("quote") else {}
            ok, why = _q.actionable(q, now=now) if q else (False, "no_quote")
            out.append({
                "sport": sport, "page": SPORT_PAGE.get(sport, "index.html"),
                "matchup": r.get("matchup"), "team": ln.get("team") or _side_team(r.get("matchup"), ln.get("side")),
                "side": ln.get("side"), "market": ln.get("market"),
                "model_prob": ln.get("prob_model"), "dk_implied": ln.get("prob_dk"),
                "book_american": ln.get("book_american"), "fair_american": ln.get("fair_american"),
                # EV at DraftKings' own no-vig probability: the book's margin, negative by construction
                "ev_pct": round(float(ln.get("ev_at_dk_no_vig") or 0) * 100, 2),
                "lean_score": ln.get("score"),
                "event_id": r.get("event_id"), "game_date": r.get("game_date"),
                "commence_time": r.get("commence") or q.get("scheduled_start"),
                "odds_observed_at": q.get("observed_at"), "quote": q or None,
                "desk_verdict": vkey, "desk_verdict_text": verdict, "desk_model": d.get("model_version"),
                "tier": 4, "is_lean": True, "lean_rule": ld.get("rule_text"),
                "lean_record": {k: rec.get(k) for k in ("n", "wins", "losses", "units", "roi_pct",
                                                        "expected_roi_pct_at_no_vig", "first_date", "last_date")},
                "actionable": bool(ok), "not_actionable_reason": None if ok else why, "qb_note": None,
            })
    return out


def _cfb_candidates(now: dt.datetime) -> List[Dict[str, Any]]:
    d = _load("cfb_model.json")
    if not d.get("board_fresh"):
        return []
    out = []
    for e in d.get("edges") or []:
        q = {"provenance": "book_snapshot", "american": e.get("book_american"),
             "observed_at": e.get("odds_observed_at"), "scheduled_start": e.get("commence_time"),
             "event_status": "pre"}
        ok, why = _q.actionable(q, now=now)
        out.append({
            "sport": "NCAAF", "page": "ncaaf.html", "matchup": e.get("matchup"), "team": e.get("team"),
            "side": str(e.get("side") or "").lower(), "market": e.get("market"),
            "model_prob": e.get("calibrated_prob"), "dk_implied": e.get("book_implied_devig"),
            "book_american": e.get("book_american"), "fair_american": e.get("fair_american"),
            "ev_pct": e.get("edge_pct"), "event_id": e.get("event_id"), "game_date": e.get("game_date"),
            "commence_time": e.get("commence_time"), "odds_observed_at": e.get("odds_observed_at"),
            "quote": q, "desk_verdict": "EXPERIMENTAL",
            "desk_verdict_text": "college model-vs-book gap; the closing line is sharper than this model",
            "desk_model": "cfb_model", "tier": 3,
            "actionable": bool(ok), "not_actionable_reason": None if ok else why, "qb_note": None,
        })
    return out


def _rank_key(c: Dict[str, Any]):
    major = 0 if c["sport"] in MAJOR_4 else 1
    # a lean has no positive EV to rank on: rank leans by how strongly model and market agree
    third = -(c.get("lean_score") or 0) if c.get("tier") == 4 else -(c.get("ev_pct") or 0)
    return (c["tier"], major, third)


def _mlb_pod(today: Dict[str, Any], today_et: str) -> Optional[Dict[str, Any]]:
    pod = today.get("play_of_day")
    if not pod or today.get("is_demo") or today.get("no_games"):
        return None
    if pod.get("market_price") is None:
        return None
    return {
        "sport": "MLB", "page": "play-of-day.html", "matchup": pod.get("matchup"),
        "team": None, "side": None, "market": pod.get("label"),
        "model_prob": pod.get("model_prob"), "dk_implied": None,
        "book_american": pod.get("market_price"), "fair_american": None,
        "ev_pct": pod.get("edge_pct"), "event_id": None, "game_date": today.get("date") or today_et,
        "commence_time": pod.get("commence_time"), "odds_observed_at": pod.get("odds_observed_at"),
        "quote": None, "desk_verdict": "MLB", "desk_verdict_text": "MLB game-line model (its own public record)",
        "desk_model": "mlb_model", "tier": 0, "actionable": True, "not_actionable_reason": None, "qb_note": None,
    }


def _amer(a) -> str:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return "n/a"
    return f"+{a}" if a >= 0 else str(a)


def _why(c: Dict[str, Any]) -> str:
    """One-line reason. Display text: never raises on a missing number."""
    p, dk, ev = c.get("model_prob"), c.get("dk_implied"), c.get("ev_pct")
    mk = str(c.get("market") or "")
    mk_h = "moneyline" if mk.upper().startswith("ML") or mk.lower().endswith(("_ml_home", "_ml_away")) else mk.replace("_", " ").lower()
    bits = [f"{c.get('sport') or ''} {c.get('team') or ''} {mk_h} ({c.get('matchup') or ''})".strip()]
    px = _amer(c.get("book_american"))
    if c.get("tier") == 4:
        if isinstance(p, (int, float)) and isinstance(dk, (int, float)):
            bits.append(f"model {p * 100:.1f}% and DraftKings' no-vig {dk * 100:.1f}% both make them the favourite at {px}")
        bits.append("model lean, not a proven edge" + (f": expected value at this price is about {ev:+.1f}% (the book's margin)"
                                                        if isinstance(ev, (int, float)) else ""))
        return " · ".join(b for b in bits if b)
    if isinstance(p, (int, float)) and isinstance(dk, (int, float)):
        bits.append(f"desk {p * 100:.1f}% vs DraftKings' no-vig {dk * 100:.1f}% at {px}")
    elif isinstance(p, (int, float)):
        bits.append(f"model {p * 100:.1f}% at {px}")
    if isinstance(ev, (int, float)):
        bits.append(f"EV {ev:+.1f}% at the DK price")
    bits.append(TIER_LABEL.get(c.get("tier"), ""))
    return " · ".join(b for b in bits if b)


# ---------------------------------------------------------------- share text ----
SITE_URL = "betting.bpleone.com/play-of-day"
POST_MAX = 280


def _day_label(date_et: str) -> str:
    try:
        d = dt.date.fromisoformat(date_et)
        return f"{d.strftime('%a')} {d.month}/{d.day}"
    except Exception:
        return str(date_et or "")


def _seen_et(iso) -> str:
    """'2026-11-05T16:59:46' (UTC, as espn_odds stamps it) -> '11:59 AM ET'."""
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        from zoneinfo import ZoneInfo
        e = d.astimezone(ZoneInfo("America/New_York"))
        return f"{e.hour % 12 or 12}:{e.minute:02d} {'AM' if e.hour < 12 else 'PM'} ET"
    except Exception:
        return ""


_POST_TIER = {0: "MLB model pick.", 1: "Validated desk pick.",
              2: "Forward test: this desk has not proven an edge.",
              3: "Experimental: the closing line is sharper than this model.",
              4: "Model lean, not a proven edge."}
_POST_TAG = {0: "MLB model", 1: "validated", 2: "forward test", 3: "experimental", 4: "lean"}


def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    """(2026-11-11) A copy-ready post for the day's card -- DRAFT ONLY. Nothing
    here sends anything: a person copies it and presses post. A price appears
    only for today's play (which is actionable by construction: a live,
    pre-start DraftKings quote) and always with the time it was observed and
    the desk's tier. The next play is named without a price -- its quote is
    not today's. A no-play day says so and why, in one breath."""
    day = _day_label(payload.get("date_et"))
    play, nxt, by = payload.get("play"), payload.get("next_play"), payload.get("by_sport") or {}
    tail = ["21+ · not betting advice", SITE_URL]
    plays = [x for x in (payload.get("sport_plays") or []) if x.get("book_american") is not None]
    if len(plays) >= 2:
        # one line per sport, each with its tier; the prices are today's live DraftKings quotes
        lines = [f"EdgeStat plays · {day}"]
        for x in plays:
            mk = "moneyline" if str(x.get("market", "")).upper().startswith("ML") else str(x.get("market", "")).replace("_", " ").lower()
            lines.append(f"{x.get('sport')}: {x.get('team') or x.get('matchup')} {mk} {_amer(x.get('book_american'))} ({_POST_TAG.get(x.get('tier'), '')})")
        seen = _seen_et(max((str(x.get("odds_observed_at") or "") for x in plays), default=""))
        notes = []
        if any(x.get("tier") == 4 for x in plays):
            notes.append("A lean is not a proven edge.")
        if any(x.get("tier") == 2 for x in plays):
            notes.append("Forward test = desk unproven.")
        lines.append((f"DraftKings prices seen {seen}. " if seen else "DraftKings prices. ") + " ".join(notes))
        optional = []
        kind = "plays"
    elif play:
        mk = "moneyline" if str(play.get("market", "")).upper().startswith("ML") else str(play.get("market", "")).replace("_", " ").lower()
        lines = [f"EdgeStat Play of the Day · {day}",
                 f"{play.get('sport')}: {play.get('team')} {mk} {_amer(play.get('book_american'))} at DraftKings ({play.get('matchup')})"]
        p, dk, ev = play.get("model_prob"), play.get("dk_implied"), play.get("ev_pct")
        if play.get("tier") == 4 and isinstance(p, (int, float)) and isinstance(dk, (int, float)):
            lines.append(f"Model {p * 100:.1f}% and market {dk * 100:.1f}% agree on the favourite.")
        elif isinstance(p, (int, float)) and isinstance(dk, (int, float)):
            lines.append(f"Desk {p * 100:.1f}% vs market {dk * 100:.1f}%" + (f" · EV {ev:+.1f}%" if isinstance(ev, (int, float)) else ""))
        else:
            lines.append("")
        lines.append(_POST_TIER.get(play.get("tier"), ""))
        seen = _seen_et(play.get("odds_observed_at"))
        if seen:
            lines.append(f"Price seen {seen}.")
        optional = [2, 4]            # droppable (in this order) if the text runs long: the prob line, then the time
        kind = "play"
    else:
        no_edge = [f"{sp} ({by[sp]['games_today']} game{'' if by[sp]['games_today'] == 1 else 's'})" for sp in MAJOR_4
                   if (by.get(sp) or {}).get("verdict") == "NO EDGE" and (by.get(sp) or {}).get("games_today")]
        lines = [f"No Play of the Day · {day}"]
        if no_edge:
            lines.append(" and ".join(no_edge) + " today: our models have not beaten DraftKings' prices there this season, so no picks.")
        else:
            lines.append("Nothing on today's board cleared the bar at the DraftKings price.")
        if nxt and nxt.get("game_date"):
            lines.append(f"Next on the board: {_day_label(nxt['game_date'])}, {nxt.get('sport')}.")
        lines.append("We don't force a bet.")
        optional = [2] if len(lines) == 4 else []
        kind = "no_play"

    def build(ls):
        return chr(10).join([x for x in ls if x] + tail)

    text = build(lines)
    for i in optional:
        if len(text) <= POST_MAX:
            break
        lines[i] = ""
        text = build(lines)
    return {"kind": kind, "text": text, "chars": len(text), "max_chars": POST_MAX, "fits": len(text) <= POST_MAX,
            "note": "Draft only. Nothing posts automatically; a person copies this and presses send."}


def run(now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)
    today_et = _today_et()
    gld = _load("game_lines_desk.json")
    cands = _desk_candidates(gld, now) + _cfb_candidates(now) + _lean_candidates(gld, now)
    mlb = _mlb_pod(_load("today.json"), today_et)
    if mlb:
        cands.insert(0, mlb)

    todays = [c for c in cands if c.get("game_date") == today_et and c.get("actionable")]
    todays.sort(key=_rank_key)
    play = todays[0] if todays else None
    if play:
        play = dict(play, why=_why(play), tier_label=TIER_LABEL.get(play["tier"]), is_pick=True)

    # (2026-11-11) the best play for each major sport that plays today, any tier
    sport_plays = []
    for sp in MAJOR_4:
        own = [c for c in todays if c["sport"] == sp]
        if own:
            c = own[0]
            sport_plays.append(dict(c, why=_why(c), tier_label=TIER_LABEL.get(c["tier"]), is_pick=True,
                                    featured=bool(play and c is todays[0])))

    # the next dated play is a desk pick, never a lean (a lean is made on the day, at the day's price)
    upcoming = [c for c in cands if c.get("game_date") and c["game_date"] > today_et and c.get("tier") != 4]
    upcoming.sort(key=lambda c: (c["game_date"],) + _rank_key(c))
    nxt = upcoming[0] if upcoming else None
    if nxt:
        nxt = dict(nxt, why=_why(nxt), tier_label=TIER_LABEL.get(nxt["tier"]), is_pick=False,
                   note="not today's play: shown as the next dated desk pick")

    # per-sport status for the page: why there is (or is not) a play today
    by_sport: Dict[str, Dict[str, Any]] = {}
    for sp, d in (gld.get("sports") or {}).items():
        sport = sp.upper()
        board = d.get("board") or []
        today_rows = [r for r in board if r.get("game_date") == today_et]
        by_sport[sport] = {
            "verdict": str(d.get("verdict") or "").split(":")[0].strip().upper() or "UNKNOWN",
            "verdict_text": d.get("verdict"),
            "games_today": len(today_rows),
            "picks_today": sum(1 for r in today_rows if r.get("pick")),
            "leans_today": sum(1 for r in today_rows if r.get("lean") and not r.get("pick")),
            "lean_record": ((d.get("lean") or {}).get("backtest") or None),
            "blocked_today": [{"matchup": r.get("matchup"), "reason": r.get("pick_blocked")} for r in today_rows if r.get("pick_blocked")],
            "picks_upcoming": sum(1 for r in board if r.get("pick") and (r.get("game_date") or "") > today_et),
            "eligible": bool(d.get("proven")) or (str(d.get("verdict") or "").upper().startswith("UNPROVEN")),
        }
    cfb = _load("cfb_model.json")
    by_sport["NCAAF"] = {"verdict": "EXPERIMENTAL", "verdict_text": "the closing line is sharper than this model",
                         "games_today": sum(1 for g in (cfb.get("games") or []) if _et_date(g.get("commence_time")) == today_et),
                         "picks_today": sum(1 for e in (cfb.get("edges") or []) if e.get("game_date") == today_et),
                         "blocked_today": [], "picks_upcoming": sum(1 for e in (cfb.get("edges") or []) if (e.get("game_date") or "") > today_et),
                         "eligible": bool(cfb.get("board_fresh"))}
    t = _load("today.json")
    by_sport["MLB"] = {"verdict": "MLB", "verdict_text": "MLB game-line model", "games_today": 0 if t.get("no_games") else len(t.get("games") or []),
                       "picks_today": 1 if mlb else 0, "blocked_today": [], "picks_upcoming": 0, "eligible": not t.get("no_games")}

    reasons = []
    if not play:
        for sport in ("NFL", "NBA", "NHL", "MLB", "NCAAF"):
            s = by_sport.get(sport)
            if not s:
                continue
            if s["verdict"] == "NO EDGE":
                reasons.append(f"{sport}: desk verdict NO EDGE -- the model adds nothing to DraftKings' price, so it makes no picks by rule, "
                               f"and no game fit the lean rule with a live price ({s['games_today']} game(s) today)")
            elif sport == "MLB" and not s["eligible"]:
                reasons.append("MLB: off-season")
            elif s["games_today"] == 0:
                reasons.append(f"{sport}: no games today" + (f"; {s['picks_upcoming']} desk pick(s) on upcoming dates" if s.get("picks_upcoming") else ""))
            elif s["picks_today"] == 0 and s["blocked_today"]:
                reasons.append(f"{sport}: {s['games_today']} game(s) today, pick held -- " + "; ".join(b["reason"] for b in s["blocked_today"] if b.get("reason"))[:200])
            elif s["picks_today"] == 0:
                reasons.append(f"{sport}: {s['games_today']} game(s) today, none cleared the desk's EV bar at the DK price")
            else:
                reasons.append(f"{sport}: {s['picks_today']} pick(s) today but none with a live, pre-start DK quote")

    # (2026-11-11) the major-4 board at DraftKings today -- prices only, no pick --
    # so a no-play day still shows what is on and where the market stands.
    slate = []
    for sp in ("nfl", "nba", "nhl"):
        d = (gld.get("sports") or {}).get(sp) or {}
        for r in d.get("board") or []:
            if r.get("game_date") != today_et:
                continue
            slate.append({"sport": sp.upper(), "matchup": r.get("matchup"), "commence_time": r.get("commence"),
                          "ml_home": r.get("ml_home"), "ml_away": r.get("ml_away"), "dk_home_no_vig": r.get("p_home_dk"),
                          "held": (r.get("pick_blocked") or None), "page": SPORT_PAGE.get(sp.upper())})
    slate.sort(key=lambda x: (MAJOR_4.index(x["sport"]) if x["sport"] in MAJOR_4 else 9, str(x.get("commence_time") or "")))

    payload = {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", ""),
        "date_et": today_et,
        "rule": ("One featured play a day across every game-lines desk, best EV at the live DraftKings price, "
                 "major-4 sports (NFL/NBA/NHL/MLB) before college; the desk's verdict sets the tier and is "
                 "always shown. Each major sport that plays also gets its own play: the desk's pick, or -- when "
                 "the desk has no pick -- a labelled model lean (the favourite the model and DraftKings agree "
                 "on), which is not a proven edge and is tracked separately."),
        "play": play,
        "sport_plays": sport_plays,
        "next_play": nxt,
        "n_candidates_today": len(todays),
        "candidates_today": [{k: c.get(k) for k in ("sport", "matchup", "team", "market", "book_american", "ev_pct", "tier", "desk_verdict")} for c in todays[:10]],
        "no_play_reasons": reasons,
        "slate_today": slate,
        "odds_observed_at": (_load("espn_odds.json") or {}).get("generated_at"),
        "by_sport": by_sport,
    }
    payload["post"] = _post(payload)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    pl = p["play"]
    if pl:
        print(f"[play-of-day] {p['date_et']}: {pl['why']}")
    else:
        print(f"[play-of-day] {p['date_et']}: no play -- " + " | ".join(p["no_play_reasons"]))
    if p.get("next_play"):
        n = p["next_play"]
        print(f"  next: {n['game_date']} {n['why']}")
