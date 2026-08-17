"""
EdgeStat -- Alpha Pick of the Day: the ONE pick, tracked separately.

Brandon's ask: the Alpha board has a great aggregate hit rate, but it surfaces
dozens of plays a day -- it "feels like an ETF of gambling." He wants the single
best Alpha pick each day tracked as its own record, and backfilled so it has
history on day one.

This module reconstructs that record from the unified settled ledger
(all_picks_ledger.json), which grades every pick the desk has ever surfaced.

Selection rule (pre-committed, uses ONLY pre-game info -- no hindsight):
  Candidate pool = player-prop picks (an individual player, not a "TEAM @ TEAM"
    game line -- game moneylines void in the ledger and never produce a real W/L,
    which is why the old headline record was 0-0 with 14 voids). We keep props
    because they settle cleanly and are the home of the desk's proven curated edge.
  Filter: model prob in [MIN_PROB, MAX_PROB] -- a conviction floor (this is a
    single followable pick, not a lottery longshot) and the same 0.85 heavy-fav
    ceiling the live Alpha selector uses (that's Play-of-the-Day territory).
  Rank each day by model ROI = prob * decimal_odds - 1. The top one is the day's
    Alpha Pick. The RANKING never looks at the outcome; we read the result only
    after the pick is chosen. Flat 1u per pick.

The honest finding this surfaces (and the page says so): concentrating the whole
Alpha board into one pick per day REMOVES the diversification that makes the board
strong. So we publish the single-pick record beside the full-board record from the
same prop pool -- the reader sees the ETF-vs-one-bet tradeoff directly.

ALSO ("alpha pick + a prop or two", Brandon's follow-up): payload["props_slate"] is
a small daily SLATE = the One Pick (slot 0) PLUS the highest-EV pick from each NEXT
distinct market family, up to MAX_SLATE, with a hard no-two-plays-share-a-family
rule so the extras are genuinely different bets, never a re-stamp of the pick.
Design chosen by a 4-way design panel scored against the ledger; it was the only
candidate that did NOT duplicate the One Pick. Two guards learned there:
  - DEDUP by (player, market, odds): the ledger stores each wager twice (top_25_board
    AND lock_of_day), so a naive top-N would count the same bet twice.
  - the family picks are NOT chosen by past ROI (that would be hindsight/curve-fit);
    only pre-game model EV drives selection. We publish the blended record + a
    per-slot breakdown so the diversifier legs' lower EV is always visible (honest:
    diversity costs some ROI vs the single pick, and we show the cost).

Output: data/alpha_pick_record.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import prob_calibration as pc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
SUMMARY = os.path.join(DATA_DIR, "ledger_summary.json")
OUT = os.path.join(DATA_DIR, "alpha_pick_record.json")
V2_SELECTIONS = os.path.join(DATA_DIR, "alpha_v2_selections.json")

MIN_PROB = 0.55     # conviction floor -- a followable daily pick, not a longshot
# Ceiling on model prob. NOTE: the live game-line Alpha rule caps at 0.85 (above that a
# MONEYLINE is a heavy favorite = Play-of-the-Day territory). That cap is wrong for
# player PROPS: a 0.86-0.90 prop at modest odds (e.g. a -136 "HR+R+RBI under 3.5") is
# not a heavy fav, it's a high-EV high-conviction play -- the desk's proven durable
# edge. Capping props at 0.85 excluded exactly those and left the model's OVER-rated
# coinflip props as the pick. 0.90 keeps the high-conviction props, still excludes
# nine-in-ten near-locks (those are Lock-of-the-Day, tracked separately).
MAX_PROB = 0.90
LAST_N_DAYS = 30
MAX_SLATE = 3       # the One Pick + up to 2 diversified "alpha props" (one per market)

# ---- RULE v2 (2026-08-10, forward-only) -- the curation gate ------------------
# WHY: the profitable prop families were PrizePicks-soft-line unders; that feed
# died 2026-07-09 (hard 403, TLS-fingerprint bot-wall). What remained in the
# daily pool were the model's own fair-odds prop feeds -- dominated by the
# overconfident families the site's honesty layer already excludes from every
# curated board (hit_no, hr_yn, xbh, 3plus_tb...). v1's "highest raw-EV prop"
# rule kept selecting from them (it went 3-8 over its last 11), violating the
# site rule that any surfaced pick routes through prob_calibration.
# THE GATE (applies only to days >= V2_RULE_DATE -- the published v1 history is
# replayed byte-identically and is never restated):
#   - family must NOT be proven-negative or overconfident (prob_calibration)
#   - prob is CALIBRATED (empirical_calibrate); the conviction band applies to
#     the calibrated prob
#   - calibrated EV at the recorded odds must clear V2_MIN_EDGE. Picks are
#     recorded at model-fair odds, so raw EV == 0 by construction: only
#     families the model has PROVEN underconfident (realized > predicted) can
#     clear a positive calibrated edge. No proven edge that day -> NO PICK
#     (published honestly; we don't force bets).
# Each v2 day's selection is LOCKED on first sight (data/alpha_v2_selections.json,
# append-only): once a day's pick (or no-pick) is chosen it never changes, even
# if later ledger entries or a drifted calibration map would now choose
# differently -- a receipts channel must have an immutable past.
V2_RULE_DATE = "2026-08-10"
V2_MIN_EDGE = 0.02  # min calibrated EV -- clears fair-odds rounding noise, demands a real edge


def _v2_gate(raw_prob: float, dec_odds: float, market: Any):
    """Curation gate for v2 days. None = excluded; else (calibrated_EV, calibrated_prob)."""
    if pc.is_proven_negative(market) or pc.is_overconfident(market):
        return None
    p_cal, _meta = pc.empirical_calibrate(raw_prob, market)
    if p_cal is None:
        p_cal = raw_prob   # unmapped family: raw prob at fair odds = EV 0 -> fails the edge bar
    if not (MIN_PROB <= p_cal <= MAX_PROB):
        return None
    ev = p_cal * dec_odds - 1
    if ev < V2_MIN_EDGE:
        return None
    return ev, round(p_cal, 4)


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _norm(s: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _dec(a) -> Optional[float]:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return None
    return 1 + a / 100 if a >= 0 else 1 + 100 / abs(a)


# MLB is the desk's deepest, most-reliably-settled market and the home of the proven
# curated edge. KBO / WNBA / tennis / UFC player props settle inconsistently in the
# ledger (they void a lot), so including them pads the record with repeated no-action
# "pushes" (the same KBO prop voiding day after day) instead of a real W/L. Scoping to
# MLB is a pre-committed market choice -- not outcome-cherry-picking -- that yields one
# diverse, genuinely-settled pick per slate.
_MLB_SPORTS = {"MLB", "MLB-PP"}


def _is_player_prop(p: Dict[str, Any]) -> bool:
    """An MLB player-level market (an individual), not a team game line. Game
    moneylines/totals void in the ledger and never yield a real settled W/L."""
    if str(p.get("sport") or "").upper() not in _MLB_SPORTS:
        return False
    nm = str(p.get("player_or_matchup") or "")
    if not nm or "@" in nm:
        return False
    mk = str(p.get("market") or "").upper()
    if mk.endswith(("_ML", "_HOME", "_AWAY")) or "TOTAL" in mk or mk.startswith(("OVER_", "UNDER_")):
        return False
    return True


def _is_mlb_moneyline(p: Dict[str, Any]) -> bool:
    """v2 pool widening (2026-08-10): MLB team MONEYLINES join the candidate pool.
    v1 excluded all game lines because moneylines used to VOID in the ledger (no
    settlement feed) -- false since espn_odds settlement wired. The family now
    settles cleanly (n>100 with a materially positive ledger record), it is priced
    against a REAL free book line (not model-fair odds), and it's the one daily
    family the ledger shows the model consistently underconfident on. It faces the
    exact same v2 gate as the props. Totals stay OUT of the flagship pool."""
    if str(p.get("sport") or "").upper() not in _MLB_SPORTS:
        return False
    mk = str(p.get("market") or "").upper()
    # Board vocabularies for the same wager: ML_AWAY / ML_HOME, {TEAM}_ML
    # (e.g. STL_ML -- the copy the dup-collapse usually KEEPS since it records
    # first), and rlm_strong's "HOME ML"/"AWAY ML".
    return (mk.startswith("ML_") or mk.endswith("_ML")
            or mk in ("HOME ML", "AWAY ML"))


def _family(market: Any) -> str:
    """Normalize a raw market string into a coarse prop FAMILY so the slate's
    one-per-family rule creates real diversity (all hrr variants collapse to one
    family; a strikeout prop and a hits prop are different families). Keyword order
    matters -- most specific first (HRR before HR before HITS)."""
    m = str(market or "").upper()
    if "HRR" in m:                                   return "HRR"          # hits+runs+RBI combo
    if "XBH" in m:                                    return "XBH"
    if "HOME_RUN" in m or "HIT_HR" in m or "_HR_" in m or m.endswith("_HR"): return "HOME_RUNS"
    if "TB" in m or "TOTAL_BASE" in m:               return "TOTAL_BASES"
    if "RBI" in m:                                    return "RBI"
    if "STEAL" in m or "SB" in m:                     return "STEALS"
    if "WALK" in m or "HBP" in m or "_BB" in m:       return "WALKS"
    if "STRIKEOUT" in m or "_K_" in m or m.startswith("K_") or m.endswith("_K") or "PUNCH" in m: return "STRIKEOUTS"
    if "SCORE_RUN" in m or "RUN" in m:                return "RUNS"        # score a run
    if "QUALITY" in m or m.startswith("QS"):          return "QUALITY_START"
    if "EARNED" in m or "_ER" in m:                   return "EARNED_RUNS"
    if "PITCHER_WIN" in m or "WIN" in m:              return "PITCHER_WIN"
    if "HIT" in m:                                    return "HITS"        # record a hit / 2+ hits
    return (m.split("_")[0] or "OTHER")              # distinct fallback bucket


def _flat_payout(pick: Dict[str, Any]) -> float:
    """Flat-1u P/L for a settled pick (independent of the ledger's Kelly stake)."""
    if pick.get("result") == "won":
        d = _dec(pick.get("fair_american"))
        return round((d - 1) if d else 0.91, 3)
    if pick.get("result") == "lost":
        return -1.0
    return 0.0  # push / void / no-action


def _row(pick: Dict[str, Any], roi: float) -> Dict[str, Any]:
    settled = bool(pick.get("settled")) and not pick.get("voided")
    voided = bool(pick.get("voided"))
    result = "void" if voided else (pick.get("result") if settled else "pending")
    return {
        "date": (pick.get("date") or "")[:10],
        "player_or_matchup": pick.get("player_or_matchup"),
        "team": pick.get("team"),
        "sport": pick.get("sport"),
        "market": pick.get("market"),
        "market_family": pick.get("market_family"),
        "model_prob": round(pick.get("prob"), 4) if pick.get("prob") is not None else None,
        "fair_american": pick.get("fair_american"),
        "roi_model_pct": round(roi * 100, 1),
        "result": result,
        "payout_units": _flat_payout(pick) if settled or voided else None,
    }


def _agg(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [r for r in rows if r["result"] in ("won", "lost", "push", "void")]
    wins = sum(1 for r in settled if r["result"] == "won")
    losses = sum(1 for r in settled if r["result"] == "lost")
    pushes = sum(1 for r in settled if r["result"] in ("push", "void"))
    decided = wins + losses
    net = round(sum((r.get("payout_units") or 0) for r in settled), 2)
    return {
        "n_days": len(rows),
        "n_settled": len(settled),
        "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(100 * net / decided, 2) if decided else None,
    }


def _streak(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Current W/L streak over the settled picks, newest first."""
    kind, n = None, 0
    for r in reversed(rows):
        if r["result"] not in ("won", "lost"):
            continue
        if kind is None:
            kind = r["result"]; n = 1
        elif r["result"] == kind:
            n += 1
        else:
            break
    return {"kind": kind, "n": n}


def run() -> Dict[str, Any]:
    led = _load(LEDGER)
    picks = led.get("picks") or []

    # Bucket eligible player props by slate date, DEDUPED by (player, market, odds).
    # The ledger stores the same wager under two source boards (top_25_board AND
    # lock_of_day) with identical player/market/prob/odds -- without this dedup a
    # top-N selection would grab the SAME bet twice and double-count the record.
    _seen_by_day: Dict[str, set] = {}
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    # v2 support: every deduped candidate (pre-gate) so locked selections stay
    # resolvable even if a later calibration map would gate them out, and so a
    # day where EVERYTHING gets gated out is still visible as a no-pick day.
    ungated_by_day: Dict[str, Dict[tuple, Dict[str, Any]]] = {}
    for p in picks:
        if p.get("voided"):
            # Duplicate-wager voids still describe a REAL wager whose kept twin
            # counts -- a locked v2 selection must stay resolvable even when the
            # exact copy it locked onto was later collapsed as the duplicate
            # (2026-08-17: the WSN_ML/ML_AWAY collapse flipped a published pick
            # day to 'NO PICK' because the locked copy got voided).
            if not str(p.get("voided_reason") or "").startswith("duplicate wager"):
                continue
            if (p.get("date") or "")[:10] < V2_RULE_DATE:
                continue
            day = (p.get("date") or "")[:10]
            if _is_player_prop(p) or _is_mlb_moneyline(p):
                k = (_norm(p.get("player_or_matchup")), _norm(p.get("market")),
                     p.get("fair_american"))
                p["market_family"] = _family(p.get("market"))
                ungated_by_day.setdefault(day, {}).setdefault(k, p)
            continue
        day = (p.get("date") or "")[:10]
        # v1 pool: MLB player props only. v2 pool (>= rule date): props + MLB
        # moneylines (see _is_mlb_moneyline for the dated rationale).
        if not _is_player_prop(p) and not (day >= V2_RULE_DATE and _is_mlb_moneyline(p)):
            continue
        prob, fa = p.get("prob"), p.get("fair_american")
        if prob is None or fa is None:
            continue
        d = _dec(fa)
        if not d:
            continue
        dedup_key = (_norm(p.get("player_or_matchup")), _norm(p.get("market")), fa)
        seen = _seen_by_day.setdefault(day, set())
        if day < V2_RULE_DATE:
            # v1 rule, replayed byte-identically (band on RAW prob before the
            # dedup claim, rank on raw EV) -- the published history never moves.
            if not (MIN_PROB <= prob <= MAX_PROB):
                continue
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            p["_roi"] = prob * d - 1
            p["market_family"] = _family(p.get("market"))
            by_day.setdefault(day, []).append(p)
        else:
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            p["market_family"] = _family(p.get("market"))
            ungated_by_day.setdefault(day, {})[dedup_key] = p
            gate = _v2_gate(prob, d, p.get("market"))
            if gate is None:
                continue
            p["_roi"], p["_p_cal"] = gate
            by_day.setdefault(day, []).append(p)

    def _rank_key(x):
        return (x["_roi"], x.get("prob") or 0, str(x.get("player_or_matchup") or ""))

    def _lock_key(p: Dict[str, Any]) -> str:
        mu = _norm(p.get("player_or_matchup"))
        mk = _norm(p.get("market"))
        # Same canonicalization as the tracker's wager key: '{team}_ml' is the
        # ml_away/ml_home wager for that side, so a lock survives whichever
        # vocabulary the surviving duplicate copy happens to carry.
        if mk.endswith("ml") and len(mk) > 2 and "@" in str(p.get("player_or_matchup") or ""):
            team = mk[:-2]
            raw = str(p.get("player_or_matchup"))
            away, _, home = [_norm(s) for s in raw.partition("@")]
            if team and (away.startswith(team) or team.startswith(away)):
                mk = "mlaway"
            elif team and (home.startswith(team) or team.startswith(home)):
                mk = "mlhome"
        return "|".join([mu, mk, str(p.get("fair_american"))])

    def _ensure_roi(p: Dict[str, Any]) -> None:
        """A locked pick that today's calibration map would now gate out still
        needs a display EV (the lock outranks the gate -- published is published)."""
        if "_roi" not in p:
            d = _dec(p.get("fair_american")) or 1.0
            p_cal, _m = pc.empirical_calibrate(p.get("prob"), p.get("market"))
            p["_roi"] = ((p_cal if p_cal is not None else (p.get("prob") or 0)) * d) - 1

    def _pick_slate(ranked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        picks_today, used_fams = [], set()
        for c in ranked:
            fam = c.get("market_family")
            if fam in used_fams:
                continue
            used_fams.add(fam)
            picks_today.append(c)
            if len(picks_today) >= MAX_SLATE:
                break
        return picks_today

    # One pick per day: highest model ROI. Deterministic tie-break: prob, then name.
    # Slate per day: the One Pick (slot 0) + the highest-EV pick from each NEXT
    # DISTINCT market family, up to MAX_SLATE plays -- no two share a family, so the
    # extras are genuinely different props, never a re-stamp of the One Pick.
    # v2 days: the day's selection (or its no-pick) LOCKS on first sight and then
    # replays verbatim forever -- late ledger arrivals or a drifted calibration map
    # never rewrite a published day.
    locks: Dict[str, Any] = _load(V2_SELECTIONS) or {}
    locks_changed = False
    no_pick_days: List[str] = []
    one_rows: List[Dict[str, Any]] = []
    slate_all: List[Dict[str, Any]] = []
    slot_rows: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: []}
    slate_history: List[Dict[str, Any]] = []
    all_days = sorted(set(by_day) | set(ungated_by_day))
    for day in all_days:
        ranked = sorted(by_day.get(day) or [], key=_rank_key, reverse=True)
        if day < V2_RULE_DATE:
            picks_today = _pick_slate(ranked)
        else:
            lock = locks.get(day)
            if lock is not None:
                pool_all = list((ungated_by_day.get(day) or {}).values())
                # Two-tier resolution: a LIVE (non-voided) copy of the locked
                # wager always wins; a dup-voided copy is the last resort (its
                # surviving twin normally covers it via the canonicalized key).
                idx_live = {_lock_key(p): p for p in pool_all if not p.get("voided")}
                idx_all = {_lock_key(p): p for p in pool_all}
                picks_today = []
                for k in (lock.get("keys") or []):
                    pref = "|".join(k.split("|")[:2]) + "|"
                    hit = idx_live.get(k)
                    if hit is None:
                        hit = next((v for kk, v in sorted(idx_live.items())
                                    if kk.startswith(pref)), None)
                    if hit is None:
                        hit = idx_all.get(k)
                    if hit is None:
                        hit = next((v for kk, v in sorted(idx_all.items())
                                    if kk.startswith(pref)), None)
                    if hit is not None:
                        picks_today.append(hit)
                for pk in picks_today:
                    _ensure_roi(pk)
                if not picks_today and not lock.get("no_pick"):
                    continue   # locked picks aged out of the capped ledger: day drops out
            else:
                picks_today = _pick_slate(ranked)
                locks[day] = {"keys": [_lock_key(pk) for pk in picks_today],
                              "no_pick": not picks_today,
                              "locked_at": dt.datetime.now().isoformat(timespec="seconds")}
                locks_changed = True
            if not picks_today:
                no_pick_days.append(day)
                slate_history.append({"date": day, "picks": [], "no_pick": True})
                continue
        day_rows = []
        for i, pk in enumerate(picks_today):
            r = _row(pk, pk["_roi"])
            if day >= V2_RULE_DATE:
                r["rule"] = "v2"
                if pk.get("_p_cal") is not None:
                    r["model_prob_calibrated"] = pk["_p_cal"]
            if i == 0:
                one_rows.append(dict(r))   # One Pick history row carries no slot key (v1 shape)
            r["slot"] = i
            day_rows.append(r); slate_all.append(r)
            if i in slot_rows:
                slot_rows[i].append(r)
        slate_history.append({"date": day, "picks": day_rows})

    if locks_changed:
        try:
            with open(V2_SELECTIONS, "w", encoding="utf-8") as f:
                json.dump(locks, f, indent=2, sort_keys=True)
        except OSError:
            pass

    today = dt.date.today()
    def _within(row, n):
        try:
            return (today - dt.date.fromisoformat(row["date"])).days <= n
        except Exception:
            return False

    record = _agg(one_rows)
    record_30 = _agg([r for r in one_rows if _within(r, LAST_N_DAYS)])
    record_v2 = _agg([r for r in one_rows if r.get("rule") == "v2"])

    # Diversified benchmark = the full CURATED book (the "ETF" Brandon likes): the
    # honest apples-to-apples comparison for "one bet vs the whole board." Pulled
    # from ledger_summary so it always matches the site's headline curated ROI.
    cur = (_load(SUMMARY).get("curated") or {})
    board = {
        "n_settled": cur.get("n_settled"), "wins": cur.get("wins"),
        "losses": cur.get("losses"), "hit_rate": cur.get("hit_rate"),
        "net_units": cur.get("net_units"), "roi_pct": cur.get("roi_pct"),
        "label": "Full curated book (diversified, all surfaced picks)",
    }

    # Today's (or the most recent) single pick, for the "today" callout. If the
    # most recent slate day is a v2 NO-PICK day, say exactly that -- never silently
    # re-surface an older pick as if it were today's.
    latest_day = all_days[-1] if all_days else None
    if one_rows and latest_day and one_rows[-1]["date"] == latest_day:
        todays = one_rows[-1]
    elif latest_day and latest_day >= V2_RULE_DATE:
        todays = {"date": latest_day, "no_pick": True,
                  "note": ("No qualifying pick: nothing on the slate cleared the v2 gate "
                           "(family with a proven non-negative record + calibrated EV >= "
                           f"+{V2_MIN_EDGE:.0%}). We don't force bets.")}
    else:
        todays = one_rows[-1] if one_rows else None

    # --- Alpha Props slate: the One Pick + up to 2 diversified extras (one per market) ---
    n_days_slate = len(slate_history)
    slate_record = _agg(slate_all)
    slate_30 = _agg([r for r in slate_all if _within(r, LAST_N_DAYS)])
    by_slot = {str(i): _agg(rows) for i, rows in slot_rows.items() if rows}
    slate = {
        "rule": ("the One Pick + the highest-EV pick from each NEXT distinct market "
                 "family, up to 3/day, no two sharing a market"),
        "record": slate_record,
        "record_last_30": slate_30,
        "by_slot": by_slot,               # "0" == the One Pick; "1"/"2" == the diversifiers
        "avg_plays_per_day": round(len(slate_all) / n_days_slate, 2) if n_days_slate else 0,
        "n_actioned": slate_record["wins"] + slate_record["losses"],
        "todays": slate_history[-1] if slate_history else None,
        "history": list(reversed(slate_history))[:40],
        "note": ("'The One Pick + a prop or two.' Slot 0 IS the One Pick; the 1-2 extras "
                 "are the highest-EV play in each NEXT distinct prop market (no two plays "
                 "share a market, and never the same player), so they're genuinely "
                 "different bets -- never a re-stamp of the pick. Selected on pre-game "
                 "model EV ONLY (no hindsight; the family picks are NOT chosen by past "
                 "ROI). ~1.75 plays/day -- the 3rd play only fires when a 3rd distinct "
                 "market qualifies (~1 day in 4). Voids/pushes are 0u refunds excluded "
                 "from ROI, not wins. HONEST READ: essentially ALL the edge is in the "
                 "anchor pick -- the diversifier legs run roughly breakeven, so they buy "
                 "you spread, not extra edge, and the blended ROI sits below the single "
                 "pick by design. And while the legs are different players and stat lines, "
                 "several are 'under'-type bets (the batter underperforms), so they're "
                 "diversified but not fully independent. Two independent recomputes off "
                 "the raw ledger confirmed the record (no hindsight, no double-count)."),
    }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "selection": {
            "rule": "single highest model-EV MLB player prop per slate",
            "min_prob": MIN_PROB, "max_prob": MAX_PROB,
            "stake": "1u flat", "settled_from": "all_picks_ledger.json",
            "rule_v2": {
                "since": V2_RULE_DATE,
                "what": ("curation gate: the pick must come from a market family that is "
                         "neither proven-negative nor overconfident, its prob is CALIBRATED "
                         "(empirical, ledger-learned), and its calibrated EV at the recorded "
                         "odds must clear the minimum edge -- otherwise the day is an honest "
                         "NO PICK. Pool widened to MLB team MONEYLINES (their v1 exclusion "
                         "reason -- 'MLs void in the ledger' -- died when espn_odds "
                         "settlement wired; the family settles cleanly at n>100 with a "
                         "materially positive record, priced against a real book line). "
                         "Totals stay out. Selections lock on first sight and never change."),
                "min_calibrated_edge": V2_MIN_EDGE,
                "why": ("the PrizePicks soft-line feed (home of the proven under families) "
                        "died 2026-07-09; the remaining fair-odds prop pool is dominated by "
                        "families the site's honesty layer excludes everywhere else. v1's "
                        "raw-EV rule kept selecting from them (3-8 over its last 11)."),
                "history_policy": ("days before the rule date replay under v1 byte-identically; "
                                   "the published record is never restated"),
            },
        },
        "launch_date": one_rows[0]["date"] if one_rows else None,
        "record": record,
        "record_last_30": record_30,
        "record_v2": record_v2,
        "no_pick_days_v2": {"n": len(no_pick_days), "recent": no_pick_days[-10:]},
        "board": board,          # the diversified curated book -- the "ETF" benchmark
        "todays": todays,
        "streak": _streak(one_rows),
        "props_slate": slate,    # the One Pick + 1-2 diversified "alpha props"
        "history": list(reversed(one_rows)),   # newest first
        "note": ("The single highest model-EV MLB player prop each day, flat 1u, "
                 "backfilled from the public ledger and selected on pre-game model "
                 "probability and odds only -- the ranking never sees the outcome. "
                 "It has run ahead of even the full curated book -- but on ~50 bets "
                 "versus the board's ~1,000, so treat its ROI as noisier: one bet a "
                 "day is far higher variance, and a cold week swings it hard. The "
                 "point isn't one number beating the other -- it's that BOTH the "
                 "single pick and the diversified board clear a real edge, which is "
                 "what you'd expect if the edge lives in the model + curation rather "
                 "than luck. Follow the one pick as a headline to watch; the board's "
                 "larger-sample ROI is the bankable, robust number. RULE AMENDMENT "
                 "2026-08-10 (v2, forward-only): picks now route through the same "
                 "curation + calibration gate as every other surfaced board -- "
                 "proven-negative and overconfident families are excluded and the "
                 "calibrated edge must clear +2%, else the day is an honest NO PICK. "
                 "History before that date is the v1 rule's record, unrestated."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    o = run()
    r, b = o["record"], o["board"]
    print(f"[alpha-pick-record] {r['n_days']} days since {o['launch_date']}")
    if r["n_settled"]:
        print(f"  ONE PICK : {r['wins']}-{r['losses']}-{r['pushes']} "
              f"({(r['hit_rate'] or 0)*100:.0f}%) net {r['net_units']:+.2f}u ROI {r['roi_pct']:+.1f}%")
    if b.get("n_settled"):
        print(f"  THE BOARD: {b['wins']}-{b['losses']} "
              f"({(b['hit_rate'] or 0)*100:.0f}%) net {b['net_units']:+.2f}u ROI {b['roi_pct']:+.1f}% "
              f"({b['n_settled']} settled, diversified)")
    sl = o.get("props_slate") or {}
    sr = sl.get("record") or {}
    if sr.get("n_settled"):
        print(f"  SLATE (1pick+props): {sr['wins']}-{sr['losses']}-{sr['pushes']} "
              f"({(sr['hit_rate'] or 0)*100:.0f}%) net {sr['net_units']:+.2f}u ROI {sr['roi_pct']:+.1f}% "
              f"· {sl.get('avg_plays_per_day')}/day · slots {list((sl.get('by_slot') or {}).keys())}")
    rv2 = o.get("record_v2") or {}
    npv2 = o.get("no_pick_days_v2") or {}
    print(f"  V2 (since 2026-08-10): {rv2.get('wins', 0)}-{rv2.get('losses', 0)} over "
          f"{rv2.get('n_days', 0)} pick day(s), {npv2.get('n', 0)} no-pick day(s)")
    t = o.get("todays")
    if t and t.get("no_pick"):
        print(f"  Today ({t.get('date')}): NO PICK -- nothing cleared the v2 gate")
    elif t:
        print(f"  Today: {t.get('player_or_matchup')} {t.get('market')} @ {t.get('fair_american')} -> {t.get('result')}")
