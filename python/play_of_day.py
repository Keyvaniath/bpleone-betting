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
              3: "experimental (college model; the close is sharper)"}


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
    return (c["tier"], major, -(c.get("ev_pct") or 0))


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
    if isinstance(p, (int, float)) and isinstance(dk, (int, float)):
        bits.append(f"desk {p * 100:.1f}% vs DraftKings' no-vig {dk * 100:.1f}% at {px}")
    elif isinstance(p, (int, float)):
        bits.append(f"model {p * 100:.1f}% at {px}")
    if isinstance(ev, (int, float)):
        bits.append(f"EV {ev:+.1f}% at the DK price")
    bits.append(TIER_LABEL.get(c.get("tier"), ""))
    return " · ".join(b for b in bits if b)


def run(now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)
    today_et = _today_et()
    gld = _load("game_lines_desk.json")
    cands = _desk_candidates(gld, now) + _cfb_candidates(now)
    mlb = _mlb_pod(_load("today.json"), today_et)
    if mlb:
        cands.insert(0, mlb)

    todays = [c for c in cands if c.get("game_date") == today_et and c.get("actionable")]
    todays.sort(key=_rank_key)
    play = todays[0] if todays else None
    if play:
        play = dict(play, why=_why(play), tier_label=TIER_LABEL.get(play["tier"]), is_pick=True)

    upcoming = [c for c in cands if c.get("game_date") and c["game_date"] > today_et]
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
                reasons.append(f"{sport}: desk verdict NO EDGE -- the model adds nothing to DraftKings' price, so it makes no picks by rule ({s['games_today']} game(s) today)")
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
        "rule": ("One play a day across every game-lines desk, best EV at the live DraftKings price, "
                 "major-4 sports (NFL/NBA/NHL/MLB) before college; the desk's verdict sets the tier and is "
                 "always shown. A NO EDGE desk makes no picks, so it cannot produce a play."),
        "play": play,
        "next_play": nxt,
        "n_candidates_today": len(todays),
        "candidates_today": [{k: c.get(k) for k in ("sport", "matchup", "team", "market", "book_american", "ev_pct", "tier", "desk_verdict")} for c in todays[:10]],
        "no_play_reasons": reasons,
        "slate_today": slate,
        "odds_observed_at": (_load("espn_odds.json") or {}).get("generated_at"),
        "by_sport": by_sport,
    }
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
