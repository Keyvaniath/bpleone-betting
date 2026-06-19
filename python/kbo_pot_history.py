"""
EdgeStat -- KBO Play of the Day rolling history + settlement.

The KBO desk prices each game (kbo_model -> kbo_props -> kbo_bestbet) but nothing
ever settled, so it never tracked a record -- the 82 ledger picks all voided
"no outcome feed". There IS a free feed: Daum Sports' hermes API carries final
scores + winner (homeWlt/awayWlt) for completed games. This snapshots the daily
POD (moneyline OR total OVER/UNDER) and settles it from that SAME feed, re-queried
by the pick's game date -- so a finished game settles even though kbo_state only
ever holds the upcoming slate (same robustness trick as cws_pot_history's settle
-by-id). Flat 1u per pick.

Output: data/kbo_pot_history.json  (sport_coverage reads this -> KBO shows a real
settled record instead of "no outcome feed yet").
"""
from __future__ import annotations
import os, sys, json, datetime as dt
from typing import Any, Dict, List, Optional

# Reuse the pipeline's exact Daum parser so pricing and settlement read the feed
# identically. Make the import work regardless of the cwd the cron uses.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from kbo_pipeline import _pull_daum_schedule
except Exception:
    _pull_daum_schedule = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BESTBET_PATH = os.path.join(DATA_DIR, "kbo_bestbet.json")
HIST_PATH = os.path.join(DATA_DIR, "kbo_pot_history.json")
TOTAL_LINE = 8.5
MAX_HISTORY = 400
VOID_DAYS = 7      # a pending pick older than this can't be settled -> void it


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _payout_units(american) -> float:
    """Profit on a 1u win at fair odds; default to -110-ish if unknown."""
    try:
        american = int(american)
    except (TypeError, ValueError):
        return 0.91
    return american / 100 if american >= 0 else 100 / abs(american)


_FINALS_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _games_on(date_str: str) -> List[Dict[str, Any]]:
    """All Daum games for a KST date (cached per run). Empty if parser absent."""
    if date_str in _FINALS_CACHE:
        return _FINALS_CACHE[date_str]
    games: List[Dict[str, Any]] = []
    if _pull_daum_schedule:
        try:
            games = _pull_daum_schedule(dt.date.fromisoformat(date_str))
        except Exception:
            games = []
    _FINALS_CACHE[date_str] = games
    return games


def _find_final(entry) -> Optional[Dict[str, Any]]:
    """The entry's COMPLETED game on Daum. Prefer the stable gameId; fall back to
    the home/away team set. Search the pick date +/- 1 to absorb KST/UTC slop."""
    base = entry.get("game_date") or entry.get("date")
    if not base:
        return None
    try:
        bd = dt.date.fromisoformat(str(base)[:10])
    except Exception:
        return None
    gid = str(entry.get("game_id") or "")
    # Orientation: explicit home/away, else parse the "home|away" match_id.
    home, away = entry.get("home_team"), entry.get("away_team")
    if (not home or not away) and entry.get("match_id"):
        parts = str(entry["match_id"]).split("|")
        if len(parts) == 2:
            home, away = parts[0], parts[1]
    teams = {home, away} if home and away else set()
    for off in (0, 1, -1):
        for g in _games_on((bd + dt.timedelta(days=off)).isoformat()):
            if g.get("state") != "post":
                continue
            if gid and g.get("game_id") == gid:
                return g
            if teams and {g.get("home_team"), g.get("away_team")} == teams:
                return g
    return None


def _settle(entry):
    if entry.get("settled"):
        return entry
    g = _find_final(entry)
    if not g:
        return entry
    hs, as_ = g.get("home_score"), g.get("away_score")
    if hs is None or as_ is None:
        return entry
    kind = entry.get("kind")
    payout = _payout_units(entry.get("fair_american"))
    outcome: Optional[str] = None
    pl = 0.0
    if kind == "ML":
        winner = g.get("winner")
        if winner == "tie":                       # KBO allows draws -> ML pushes
            outcome, pl = "PUSH", 0.0
        else:
            won = winner == entry.get("team")
            outcome, pl = ("WIN", payout) if won else ("LOSS", -1.0)
    elif kind in ("OVER", "UNDER"):
        total = hs + as_
        line = entry.get("total_line") or TOTAL_LINE
        if total == line:
            outcome, pl = "PUSH", 0.0
        else:
            over = total > line
            won = (kind == "OVER") == over
            outcome, pl = ("WIN", payout) if won else ("LOSS", -1.0)
    else:
        return entry
    entry.update({
        "settled": True,
        "outcome": outcome,
        "pl_units": round(pl, 3),
        "actual_score": f"{as_}-{hs}",
        "actual_winner": g.get("winner"),
        "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
    })
    return entry


def run():
    bestbet = _load(BESTBET_PATH)
    hist: List[Dict[str, Any]] = _load(HIST_PATH).get("history") or []
    today = dt.date.today().isoformat()

    # Snapshot the current POD once per (date, matchup, kind).
    pot = bestbet.get("top_bet")
    if pot and pot.get("kind") in ("ML", "OVER", "UNDER"):
        key = (today, pot.get("team"), pot.get("opponent"), pot.get("kind"))
        if not any((h.get("date"), h.get("team"), h.get("opponent"), h.get("kind")) == key
                   for h in hist):
            hist.append({
                "date": today,
                "game_date": pot.get("game_date") or today,
                "game_id": pot.get("game_id"),
                "match_id": pot.get("match_id"),
                "kind": pot.get("kind"),
                "team": pot.get("team"),
                "opponent": pot.get("opponent"),
                "home_team": pot.get("home_team"),
                "away_team": pot.get("away_team"),
                "total_line": TOTAL_LINE if pot.get("kind") in ("OVER", "UNDER") else None,
                "prob": pot.get("prob"),
                "fair_american": pot.get("fair_american"),
                "confidence": pot.get("confidence"),
                "label": pot.get("label"),
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    n_before = sum(1 for h in hist if h.get("settled"))
    for i, e in enumerate(hist):
        if not e.get("settled"):
            hist[i] = _settle(e)
    hist = hist[-MAX_HISTORY:]

    # Void picks too old to ever settle -- pre-rewrite orphans (no game ref) or a
    # postponed game that never produced a final -- so they don't linger as "pending".
    today_d = dt.date.today()
    for e in hist:
        if e.get("settled") or e.get("voided"):
            continue
        try:
            ed = dt.date.fromisoformat(str(e.get("date"))[:10])
        except Exception:
            ed = None
        if ed is not None and (today_d - ed).days > VOID_DAYS:
            e.update(voided=True, outcome="VOID",
                     void_reason=f"no final matched within {VOID_DAYS} days")

    settled = [h for h in hist if h.get("settled")]
    pending = [h for h in hist if not h.get("settled") and not h.get("voided")]
    voided = [h for h in hist if h.get("voided")]
    wins = sum(1 for h in settled if h.get("outcome") == "WIN")
    losses = sum(1 for h in settled if h.get("outcome") == "LOSS")
    pushes = sum(1 for h in settled if h.get("outcome") == "PUSH")
    net = round(sum(h.get("pl_units", 0) for h in settled), 2)
    decided = wins + losses
    record = None
    if decided or pushes:
        record = f"{wins}-{losses}" + (f"-{pushes}" if pushes else "")

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": "KBO",
        "total_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_voided": len(voided),
        "n_settled_this_run": len(settled) - n_before,
        "wins": wins, "losses": losses, "pushes": pushes,
        "record": record,
        "hit_rate": round(wins / decided, 4) if decided else None,
        "net_units": net,
        "roi_pct": round(100 * net / decided, 2) if decided else None,
        "stake_assumption": "1u flat per POD (ML or total 8.5), settled off Daum Sports finals by game date",
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[kbo-history] {p['total_pots']} picks, {p['n_settled']} settled, {p['n_pending']} pending "
          f"(+{p['n_settled_this_run']} this run)")
    if p["record"]:
        roi = p["roi_pct"] if p["roi_pct"] is not None else 0.0
        print(f"  Record {p['record']} net {p['net_units']:+.2f}u ROI {roi:+.1f}%")
    for h in p["history"][:6]:
        print(f"    {h['date']} {str(h.get('label',''))[:38]:38s} -> {h['outcome']}")
