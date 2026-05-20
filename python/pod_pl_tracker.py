"""
EdgeStat -- Play-of-the-Day P&L tracker (PRIMARY accuracy metric).

This is Brandon's accuracy benchmark: ONE pick per day, the highest-edge
ML / total play from today.json, recorded with a permanent ID. Settled
the next day from historical_games.json. All-time + last-30-day W-L,
net units (assumes flat 1u stake), ROI%.

What makes this DIFFERENT from locks_of_day:
   exactly 1 pick per day (not 5)
   GAME-level only (no PrizePicks) -- the settlement is reliable
   flat 1u stake (no Kelly inflation)
   no calibration shrinkage on probability (we're tracking what was
     ACTUALLY called, not what the model "should have called")

Output: data/pod_pl.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "pod_pl.json")
MAX_HISTORY = 365   # ~1 year of daily PODs


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _today_date_str() -> str:
    return dt.date.today().isoformat()


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _pick_today_pod() -> Optional[Dict[str, Any]]:
    """Pick the day's POD = highest-edge ML or game total from today.json.

    Brandon wants ONLY game-level picks (no player props) for P&L
    accuracy -- player props need per-player gamelogs to settle, and
    he wants the single best ML/TOTAL of the day as the benchmark.

    GUARD: if today.json is stale (generated_at older than 6 hours OR
    not from today's date), we refuse to lock in a POD -- better to
    have no POD recorded than to lock in a stale one.
    """
    today = _load(os.path.join(DATA_DIR, "today.json"))
    if not today: return None

    # Staleness check: today.json's generated_at must be from today
    today_str = dt.date.today().isoformat()
    gen_at = (today.get("generated_at") or "")[:10]
    if gen_at and gen_at != today_str:
        # today.json is from a different date -- don't record stale POD
        return None
    # Also check age in hours
    try:
        gen_dt = dt.datetime.fromisoformat(today.get("generated_at"))
        age_hours = (dt.datetime.now() - gen_dt).total_seconds() / 3600
        if age_hours > 6: return None    # too stale
    except Exception:
        pass

    best = None
    for g in (today.get("games") or []):
        recos = g.get("recommendations") or []
        for r in recos:
            label = (r.get("label") or "").upper()
            # Only ML or OVER/UNDER markets
            if not ("_ML" in label or "OVER_" in label or "UNDER_" in label):
                continue
            edge = r.get("edge_pct") or 0
            if best is None or edge > (best.get("edge_pct") or 0):
                best = {
                    "matchup": g.get("matchup"),
                    "label": label,
                    "model_prob": r.get("model_prob"),
                    "market_price": r.get("market_price"),
                    "edge_pct": edge,
                    "confidence": r.get("confidence"),
                    "first_pitch_str": g.get("time"),   # e.g. "8:40p ET"
                    "gamePk": g.get("gamePk"),          # MLB game ID for exact matching
                }
    return best


def _settle_pod(pod: Dict[str, Any]) -> Optional[str]:
    """Cross-reference historical_mlb.json (MLB-only POD) for the outcome.

    CRITICAL: only settle if at least 12 hours have passed since the POD
    was recorded. Otherwise we risk matching against last night's
    already-completed game with the same matchup string (UTC date in
    historical_mlb often spans the calendar boundary -- a game played
    Mon evening ET is dated Tue in UTC).
    """
    if pod.get("settled"):
        return None
    # 12-hour cool-off guard
    try:
        recorded_at = dt.datetime.fromisoformat(pod.get("recorded_at") or "")
        if (dt.datetime.now() - recorded_at).total_seconds() < 12 * 3600:
            return None
    except Exception:
        return None

    hist = _load(os.path.join(DATA_DIR, "historical_mlb.json"))
    games = hist.get("games") or []
    matchup = (pod.get("matchup") or "").lower()
    label = (pod.get("label") or "").upper()
    date_s = pod.get("date")
    pod_game_pk = pod.get("gamePk")
    for g in games:
        # PREFER exact gamePk match (avoids UTC-date-confusion of same matchup
        # played on consecutive days)
        is_pk_match = (pod_game_pk and g.get("id") and
                        str(pod_game_pk) == str(g.get("id")))
        if not is_pk_match:
            g_date = (g.get("date") or "")[:10]
            if g_date != date_s: continue
            # Build matchup string from abbrevs ("LAD @ SD")
            g_mu = (g.get("matchup") or "").lower()
            if not g_mu and g.get("away_abbrev") and g.get("home_abbrev"):
                g_mu = f"{g['away_abbrev']} @ {g['home_abbrev']}".lower()
            if not g_mu: continue
            if matchup not in g_mu and g_mu not in matchup: continue
        if g.get("home_score") is None: continue
        home_score = g.get("home_score") or 0
        away_score = g.get("away_score") or 0
        total = home_score + away_score
        # ML_HOME = home team wins
        if label.endswith("_ML") and label != "OVER_ML" and label != "UNDER_ML":
            # e.g. NYY_ML -- team name is in the prefix
            # For ML_HOME / ML_AWAY explicit
            if label == "ML_HOME" or "HOME" in label:
                return "won" if home_score > away_score else "lost"
            if label == "ML_AWAY" or "AWAY" in label:
                return "won" if away_score > home_score else "lost"
            # Team abbreviation prefix -- match against matchup
            team_abbr = label.replace("_ML", "")
            home_abbr = g_mu.split("@")[-1].strip().split()[0] if "@" in g_mu else ""
            if team_abbr.lower() in home_abbr or home_abbr.lower() in team_abbr.lower():
                return "won" if home_score > away_score else "lost"
            return "won" if away_score > home_score else "lost"
        if label.startswith("OVER_") or label.startswith("UNDER_"):
            try:
                line = float(label.split("_")[-1])
            except Exception:
                continue
            if "OVER_" in label:
                if total > line: return "won"
                if total == line: return "push"
                return "lost"
            else:
                if total < line: return "won"
                if total == line: return "push"
                return "lost"
    return None


def run() -> Dict[str, Any]:
    state = _load(OUT)
    history = state.get("history") or []
    existing_by_date = {p.get("date"): p for p in history}
    today_str = _today_date_str()

    # Record today's POD if not already done
    n_added = 0
    if today_str not in existing_by_date:
        pod = _pick_today_pod()
        if pod and pod.get("matchup") and pod.get("label"):
            decimal_odds = _american_to_decimal(pod.get("market_price")) or 1.91
            entry = {
                "date": today_str,
                "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
                "matchup": pod.get("matchup"),
                "label": pod.get("label"),
                "model_prob": pod.get("model_prob"),
                "market_price": pod.get("market_price"),
                "decimal_odds": round(decimal_odds, 3),
                "raw_edge_pct": pod.get("edge_pct"),   # tracking what was called, not "true" edge
                "settled": False,
                "result": "pending",
                "payout_units": None,
                "settled_at": None,
            }
            history.append(entry)
            n_added = 1

    # Settle any pending entries
    n_newly_settled = 0
    for pod in history:
        if pod.get("settled"): continue
        result = _settle_pod(pod)
        if result:
            pod["settled"] = True
            pod["result"] = result
            pod["settled_at"] = dt.datetime.now().isoformat(timespec="seconds")
            decimal_odds = pod.get("decimal_odds") or 1.91
            # Flat 1u stake
            if result == "won":
                pod["payout_units"] = round(decimal_odds - 1, 3)
            elif result == "lost":
                pod["payout_units"] = -1.0
            else:   # push
                pod["payout_units"] = 0.0
            n_newly_settled += 1

    # Cap
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # Aggregate
    settled = [p for p in history if p.get("settled")]
    pending = [p for p in history if not p.get("settled")]
    wins = sum(1 for p in settled if p["result"] == "won")
    losses = sum(1 for p in settled if p["result"] == "lost")
    pushes = sum(1 for p in settled if p["result"] == "push")
    n_decided = wins + losses
    hit_rate = round(wins / n_decided, 4) if n_decided > 0 else None
    net_units = round(sum((p.get("payout_units") or 0) for p in settled), 3)
    n_risked = sum(1 for p in settled if p["result"] != "push")   # 1u per pick
    roi_pct = round(net_units / n_risked * 100, 2) if n_risked > 0 else None

    # Last 30 days
    today = dt.date.today()
    last_30 = []
    for p in settled:
        try:
            d = dt.date.fromisoformat(p.get("date") or "")
            if (today - d).days <= 30:
                last_30.append(p)
        except Exception:
            continue
    l30_wins = sum(1 for p in last_30 if p["result"] == "won")
    l30_losses = sum(1 for p in last_30 if p["result"] == "lost")
    l30_net = round(sum((p.get("payout_units") or 0) for p in last_30), 3)
    l30_decided = l30_wins + l30_losses

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "stake_assumption": "1u flat per pick",
        "total_pods": len(history),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "net_units": net_units,
        "roi_pct": roi_pct,
        "last_30_days": {
            "wins": l30_wins,
            "losses": l30_losses,
            "net_units": l30_net,
            "hit_rate": round(l30_wins / l30_decided, 4) if l30_decided > 0 else None,
        },
        "n_added_this_run": n_added,
        "n_newly_settled_this_run": n_newly_settled,
        "todays_pod": next((p for p in history if p["date"] == today_str), None),
        "history": history,
        "note": ("Play of the Day P&L: ONE pick per day, ML or game-total "
                  "only. Flat 1u stake. The single accuracy benchmark -- "
                  "no Kelly inflation, no PrizePicks, no aggregated 5-locks. "
                  "Brandon's primary track record."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"POD P&L: {p['total_pods']} total PODs ({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  This run: +{p['n_added_this_run']} new, +{p['n_newly_settled_this_run']} newly settled")
    if p["hit_rate"] is not None:
        print(f"  All-time: {p['wins']}-{p['losses']}-{p['pushes']} ({p['hit_rate']*100:.1f}%) | net {p['net_units']:+.2f}u | ROI {p['roi_pct']:+.1f}%")
    else:
        print(f"  All-time: 0-0 (no settled outcomes yet)")
    l30 = p["last_30_days"]
    if l30["hit_rate"] is not None:
        print(f"  Last 30d: {l30['wins']}-{l30['losses']} ({l30['hit_rate']*100:.1f}%) | net {l30['net_units']:+.2f}u")
    if p["todays_pod"]:
        t = p["todays_pod"]
        print(f"\n  Today's POD: {t['matchup']} {t['label']} @ {t['market_price']} (model {t.get('model_prob',0)*100:.0f}%) -- {t['result'].upper()}")
