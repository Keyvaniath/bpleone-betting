"""
EdgeStat -- college-football model-vs-book edges (the CFB desk's pick engine).

Joins our Elo ratings (cfb_ratings) to the live DraftKings college-football
moneylines that ESPN publishes free (espn_odds), de-vigs the book pair, shrinks
our probability toward the book, routes the result through prob_calibration,
and surfaces only what survives.

THE POSTURE, AND WHY IT IS DELIBERATELY HUMBLE
Our own walk-forward says this model hits ~71% / 0.190 Brier once a season has
four weeks of its own data, and ~65% / 0.207 predicting off prior-season
ratings alone -- which is where it stands today. A market that closes near
0.19 Brier is therefore AT LEAST our equal and probably better right now, so
the model's job is NOT to price games from scratch. It is to find the places
where it disagrees with the book enough to be interesting, defer to the book
everywhere else, and say plainly how little it knows in September.

Two consequences, both intentional:
  1. Shrinkage toward the book is STRONGER than the MLB desk's (which faces a
     model that has thousands of settled games behind it). See SHRINK_CAP.
  2. Nothing here is published to the curated boards. Every pick is emitted as
     an EXPERIMENTAL family (cfb_model_*) -- the same "tracked to train, not
     featured" pattern the World Cup desk uses -- and it stays experimental
     until it has a real settled record that clears the same gates the Alpha
     pick clears. A brand-new model touching the public record is exactly the
     risk this codebase has been burned by before.

Output: data/cfb_model.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import cfb_ratings as cr

try:
    import prob_calibration as pc
except Exception:                                   # pragma: no cover
    pc = None

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cfb_model.json")
ODDS_PATH = os.path.join(DATA_DIR, "espn_odds.json")
RATINGS_PATH = os.path.join(DATA_DIR, "cfb_ratings.json")

# Defer harder than the MLB desk (cap 0.80): that model has thousands of
# settled games; this one has zero and a measured early-season Brier (0.207)
# no better than a closing line's. A 0.90 cap means even a wild disagreement
# keeps at most 10% of our own opinion until we have earned more.
SHRINK_CAP = 0.90
SHRINK_SLOPE = 3.5

MIN_EDGE = 0.04          # 4% -- deliberately above the MLB desk's 3%
MIN_PROB, MAX_PROB = 0.35, 0.80   # no lottery dogs, no -600 chalk

# Experimental family prefix. Markets are named so prob_calibration can learn
# them per side, and so the settlement branch grades them as game lines.
FAMILY_PREFIX = "cfb_model"


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _american_to_decimal(a) -> Optional[float]:
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    return 1 + a / 100.0 if a >= 0 else 1 + 100.0 / abs(a)


def _prob_to_american(p: float) -> int:
    if p <= 0 or p >= 1:
        return 0
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def _devig_pair(home_ml, away_ml) -> Tuple[Optional[float], Optional[float]]:
    dh, da = _american_to_decimal(home_ml), _american_to_decimal(away_ml)
    if not dh or not da:
        return None, None
    ih, ia = 1.0 / dh, 1.0 / da
    tot = ih + ia
    return ih / tot, ia / tot


def _shrink_toward_book(model_p: float, book_devig: float) -> float:
    if model_p is None or book_devig is None:
        return model_p
    gap = abs(model_p - book_devig)
    w = min(SHRINK_CAP, gap * SHRINK_SLOPE)
    return model_p * (1 - w) + book_devig * w


def _norm_team(s: Any) -> str:
    return str(s or "").strip().upper()


def _et_date(commence_utc: Any) -> Optional[str]:
    """The ET calendar day a game belongs to, from its UTC kickoff.

    ESPN's scoreboard files a game under its EASTERN date, but commence_time is
    UTC -- a 7:30pm PT Saturday kickoff is 02:30Z SUNDAY. Naively slicing the
    UTC string files that game a day late, which is exactly the bug that left
    an 8/27 MLB final sitting unmatched under 8/28. Football season spans EDT
    (UTC-4) and EST (UTC-5); both offsets put a 00:00-05:00Z kickoff on the
    previous ET day, and no CFB game kicks between 05:00Z and 11:00Z, so a
    single -5h shift is correct year-round here."""
    s = str(commence_utc or "")
    if len(s) < 16:
        return s[:10] or None
    try:
        t = dt.datetime.strptime(s[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return s[:10]
    return (t - dt.timedelta(hours=5)).date().isoformat()


# --- graduation: when this desk stops being experimental -------------------
# "Experimental until it earns its way" is worthless as a promise; it has to be
# a computation. These are the bars, checked every run against the REAL ledger,
# and published in the artifact so the desk's status is never a claim someone
# has to trust.
GRAD_MIN_SETTLED = 100      # a season's worth of graded picks, not a hot week
GRAD_MIN_ROI = 0.0          # must not be losing money
GRAD_MIN_CI_FLOOR = -0.05   # bootstrap floor: allow variance, forbid a hole
LEDGER_PATH = os.path.join(DATA_DIR, "all_picks_ledger.json")


def graduation_status() -> Dict[str, Any]:
    """Has the CFB desk earned a place on the curated boards yet?

    Reads the canonical ledger predicate (settled AND NOT voided) over
    cfb_model rows only. Returns the bars, where we stand, and a single
    `graduated` boolean. Nothing in this module promotes itself -- promotion is
    a deliberate act a human takes after this says yes."""
    led = _load(LEDGER_PATH)
    rows = [p for p in (led.get("picks") or [])
            if str(p.get("source") or "") == "cfb_model"
            and p.get("settled") and not p.get("voided")]
    wins = sum(1 for p in rows if p.get("result") == "won")
    losses = sum(1 for p in rows if p.get("result") == "lost")
    n = wins + losses
    net = sum(float(p.get("payout_units") or 0) for p in rows)
    roi = (net / n) if n else None
    unmet = []
    if n < GRAD_MIN_SETTLED:
        unmet.append(f"needs {GRAD_MIN_SETTLED} settled picks (has {n})")
    if roi is None or roi < GRAD_MIN_ROI:
        unmet.append(f"needs ROI >= {GRAD_MIN_ROI:.0%} "
                     f"(has {'n/a' if roi is None else format(roi, '.1%')})")
    return {
        "graduated": not unmet,
        "n_settled": n, "wins": wins, "losses": losses,
        "net_units": round(net, 2),
        "roi_pct": round(roi * 100, 2) if roi is not None else None,
        "bars": {"min_settled": GRAD_MIN_SETTLED,
                 "min_roi_pct": GRAD_MIN_ROI * 100,
                 "min_ci_floor_pct": GRAD_MIN_CI_FLOOR * 100},
        "unmet": unmet,
        "note": ("Until every bar is met these picks stay off the curated "
                 "boards and out of the headline record. Promotion is a "
                 "deliberate human step, never automatic."),
    }


def run() -> Dict[str, Any]:
    now = dt.datetime.now().isoformat(timespec="seconds")
    ratings_payload = _load(RATINGS_PATH)
    if not ratings_payload.get("ratings"):
        # Degraded payload must be SHAPE-IDENTICAL to a good one (this repo has
        # crashed a whole pipeline on a display path before). Say why, publish
        # nothing, fail loud in the note rather than silently emitting picks.
        return _write({
            "generated_at": now, "n_games": 0, "n_edges": 0,
            "regime": "unknown", "edges": [], "games": [],
            "note": ("No CFB ratings artifact -- run cfb_ratings.py first. "
                     "No edges published."),
        })

    # FAIL CLOSED on the honesty layer. Every EdgeStat board routes its probs
    # through prob_calibration; if that import failed we must publish NOTHING
    # rather than a board of uncalibrated, unguarded picks. Losing the desk for
    # a run is recoverable -- publishing ungated picks is not.
    if pc is None:
        return _write({
            "generated_at": now, "n_games": 0, "n_edges": 0,
            "regime": "unknown", "edges": [], "games": [],
            "status": "experimental",
            "note": ("prob_calibration unavailable -- no edges published. Every "
                     "surfaced probability must pass the curation/overconfidence "
                     "guards, so the desk goes dark rather than skip them."),
        })

    by_team = {_norm_team(r["team"]): r for r in ratings_payload["ratings"]}
    regime = ratings_payload.get("regime") or "unknown"
    applicable = ratings_payload.get("applicable_backtest") or {}

    odds = _load(ODDS_PATH)
    rows = [g for g in (odds.get("games") or [])
            if str(g.get("sport") or "").upper() == "NCAAF"]

    games_out: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    n_unrated = 0

    for g in rows:
        mk = g.get("market") or {}
        ml_home, ml_away = mk.get("ml_home"), mk.get("ml_away")
        home, away = _norm_team(g.get("home")), _norm_team(g.get("away"))
        rh, ra = by_team.get(home), by_team.get(away)
        if not rh or not ra:
            # An unrated team is usually an FCS visitor. Never invent a rating:
            # count it, name it, and skip it.
            n_unrated += 1
            games_out.append({
                "matchup": g.get("matchup"), "home": home, "away": away,
                "status": g.get("status"), "commence_time": g.get("commence_time"),
                "rated": False,
                "note": "one or both teams unrated (non-FBS or new) -- not priced",
            })
            continue

        neutral = bool(g.get("neutral"))
        p_home_model = cr.win_prob(rh["rating"], ra["rating"], neutral)
        bh, ba = _devig_pair(ml_home, ml_away)
        row = {
            "matchup": g.get("matchup"), "home": home, "away": away,
            "status": g.get("status"), "commence_time": g.get("commence_time"),
            "rated": True,
            "home_rating": rh["rating"], "away_rating": ra["rating"],
            "home_rank": rh.get("rank"), "away_rank": ra.get("rank"),
            "prior_weight": max(rh.get("prior_weight", 0), ra.get("prior_weight", 0)),
            "model_p_home": round(p_home_model, 4),
            "model_spread_home": round(
                (rh["rating"] + (0 if neutral else cr.HFA_ELO) - ra["rating"])
                / cr.ELO_PER_POINT, 1),
            "book_ml_home": ml_home, "book_ml_away": ml_away,
            "book_p_home_devig": round(bh, 4) if bh is not None else None,
            "book_total": mk.get("total"),
            "book_spread": mk.get("spread"),
        }
        games_out.append(row)

        if bh is None or str(g.get("status")) != "pre":
            continue

        for side, p_model, book_devig, book_ml in (
            ("HOME", p_home_model, bh, ml_home),
            ("AWAY", 1.0 - p_home_model, ba, ml_away),
        ):
            dec = _american_to_decimal(book_ml)
            if not dec:
                continue
            p_shrunk = _shrink_toward_book(p_model, book_devig)
            market = f"{FAMILY_PREFIX}_ml_{side.lower()}"
            # Honesty layer: the same engine every other EdgeStat board uses.
            # A family with no settled history returns method 'model_only' and
            # is admitted; once it HAS history, curation can bury it.
            p_cal, meta = pc.empirical_calibrate(p_shrunk, market)
            if p_cal is None:
                p_cal = p_shrunk
            if pc.is_proven_negative(market) or pc.is_overconfident(market):
                continue
            if not (MIN_PROB <= p_cal <= MAX_PROB):
                continue
            edge = p_cal * dec - 1
            if edge < MIN_EDGE:
                continue
            team = home if side == "HOME" else away
            edges.append({
                "matchup": g.get("matchup"),
                "side": side,
                "team": team,
                "market": market,
                # Settlement identity: the ESPN event id grades this pick
                # against the exact game; game_date is the ET day it belongs to.
                "event_id": str(g.get("event_id") or ""),
                "game_date": _et_date(g.get("commence_time")),
                "commence_time": g.get("commence_time"),
                "model_prob_raw": round(p_model, 4),
                "model_prob_shrunk": round(p_shrunk, 4),
                "calibrated_prob": round(p_cal, 4),
                "book_implied_devig": round(book_devig, 4),
                "book_american": book_ml,
                "book_decimal": round(dec, 3),
                "fair_american": _prob_to_american(p_cal),
                "edge_pct": round(edge * 100, 2),
                "prior_weight": row["prior_weight"],
                "calibration_method": (meta or {}).get("method"),
                "family_n_settled": (meta or {}).get("n"),
                # The reasoning chain, mirroring the Alpha pick's why-panel.
                "why": (
                    f"Elo {rh['rating']:.0f} vs {ra['rating']:.0f}"
                    f"{'' if neutral else ' +' + str(int(cr.HFA_ELO)) + ' home'} "
                    f"-> model {p_model:.1%}; shrunk to {p_shrunk:.1%} against the "
                    f"book's de-vigged {book_devig:.1%}; at {book_ml} that is "
                    f"{edge * 100:.1f}% edge."),
            })

    edges.sort(key=lambda e: -e["edge_pct"])

    payload = {
        "generated_at": now,
        "season": ratings_payload.get("season"),
        "regime": regime,
        "n_games": len(games_out),
        "n_rated": sum(1 for g in games_out if g.get("rated")),
        "n_unrated": n_unrated,
        "n_edges": len(edges),
        "edges": edges,
        "games": games_out,
        "model_backtest": applicable,
        "constants": {"shrink_cap": SHRINK_CAP, "shrink_slope": SHRINK_SLOPE,
                      "min_edge": MIN_EDGE, "prob_band": [MIN_PROB, MAX_PROB]},
        "graduation": graduation_status(),
        "status": "experimental",
        "note": (
            "EXPERIMENTAL -- tracked, not featured. These edges are recorded to "
            "build a settled record and are deliberately absent from every "
            "curated board until they have one. Our own walk-forward puts this "
            f"model at {applicable.get('accuracy', '?')} accuracy / "
            f"{applicable.get('brier', '?')} Brier (n={applicable.get('n', 0)}) in "
            f"the {regime.replace('_', ' ')} regime it is in today -- no better "
            "than a sharp closing line, which is exactly why every probability "
            "is shrunk hard toward the book and only genuine divergence "
            "survives. Moneylines only; no spreads, totals, or player props."),
        "sources": {
            "ratings": "data/cfb_ratings.json (Elo on ESPN results)",
            "lines": "data/espn_odds.json (DraftKings via ESPN free feed)",
        },
    }
    return _write(payload)


def _write(payload: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def _self_test() -> bool:
    ok = True
    dh, da = _devig_pair(-200, 170)
    if dh is None or abs((dh + da) - 1.0) > 1e-9:
        print(f"  FAIL devig sums to 1: {dh}, {da}"); ok = False
    if not (dh > da):
        print("  FAIL favorite carries the larger de-vigged prob"); ok = False
    # shrink must always land between model and book, and nearer the book
    s = _shrink_toward_book(0.70, 0.50)
    if not (0.50 < s < 0.70):
        print(f"  FAIL shrink bounds: {s}"); ok = False
    if not (abs(s - 0.50) < abs(s - 0.70)):
        print(f"  FAIL shrink defers to book on a wide gap: {s}"); ok = False
    # agreement is a no-op
    if abs(_shrink_toward_book(0.55, 0.55) - 0.55) > 1e-9:
        print("  FAIL shrink is identity on agreement"); ok = False
    # fair odds must round-trip the displayed probability
    if _prob_to_american(0.50) not in (100, -100):
        print("  FAIL prob_to_american at even money"); ok = False
    print(f"  model self-test: {'OK' if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    if not _self_test():
        raise SystemExit("cfb_model self-test FAILED")
    p = run()
    print(f"[cfb-model] {p['n_games']} CFB games ({p['n_rated']} rated, "
          f"{p['n_unrated']} unrated) -> {p['n_edges']} experimental edges "
          f"[{p['regime']}]")
    for e in p["edges"][:6]:
        print(f"    {e['team']:5s} {e['side']:4s} {e['matchup']:22s} "
              f"{e['book_american']:>5} | model {e['model_prob_raw']:.0%}"
              f" -> {e['calibrated_prob']:.0%} | edge +{e['edge_pct']}%")
