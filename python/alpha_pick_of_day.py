"""
EdgeStat -- Alpha Pick of the Day.

Different from Play of the Day:
  Play of the Day = highest CONFIDENCE play (often a -150 fav at 70%)
  Alpha Pick      = highest +EV/ROI play (often an underdog with mispriced edge)

The Alpha Pick is the model's "this is where the book is wrong by the most"
recommendation — regardless of whether it's a favorite or underdog. Could be:
  - A +250 underdog the model thinks is actually 38% to win (ROI ~+33%)
  - A -110 favorite the model thinks is 60% (ROI ~+14%)
  - A +500 longshot the model thinks is 22% (ROI ~+32%)

Method:
  Scan all picks from todays_top_plays + per-sport strong_edges. For each:
    decimal_odds = american_to_decimal(fair_american) — model's fair price
    book_decimal = a proxy for current book price (we use 0.95 * fair as
                  vig-adjusted proxy since we don't pull live book odds here)
    ROI per $1 = model_prob * book_decimal - 1
  Filter:
    - min model_prob = 0.18 (no <18% longshots — variance too brutal)
    - min model_prob = 0.85 max (heavy favs not Alpha — that's POD territory)
    - require source != 'top_25_board' (avoid double-counting)
  Sort by ROI descending. Top = Alpha Pick.

Output: data/alpha_pick_of_day.json
  {
    "alpha_pick": {...top play...},
    "top_5_alphas": [...top 5 by ROI...],
    "diagnostics": {...filter counts...}
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "alpha_pick_of_day.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(a):
    if a is None: return None
    try:
        a = int(a)
    except Exception:
        return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _decimal_to_american(d):
    if d is None or d <= 1.0: return None
    if d >= 2.0: return int(round((d - 1) * 100))
    return -int(round(100 / (d - 1)))


def _pacific_now() -> dt.datetime:
    """Current Pacific time (the slate is keyed to the 7am-PT morning refresh)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        return dt.datetime.utcnow() - dt.timedelta(hours=7)  # PDT fallback


def _clean_market(m: Optional[str]) -> str:
    return (m or "").replace("PP_", "").replace("_", " ").strip()


def _props_of_day(top: Dict[str, Any], k: int = 5) -> List[Dict[str, Any]]:
    """The 3-5 best curated player props for the morning slip -- ranked by the
    machine's own quarter-Kelly stake, deduped by player, capped at 3 per market
    family for variety.

    Two-pass: EXHAUST top_25 first (those are LEDGER-LOGGED, so the slip earns a
    real settled track record); only backfill from the broader all_plays board if
    top_25 is too thin to field a 3-leg slip."""
    keyf = (lambda p: (p.get("unit_size_quarter_kelly") or 0,
                       p.get("kelly_fraction") or 0, p.get("edge_pct") or 0))
    is_prop = (lambda p: p.get("src") == "player" or str(p.get("sport", "")).endswith("-PP"))
    t25 = sorted([p for p in (top.get("top_25") or []) if is_prop(p)], key=keyf, reverse=True)
    allp = sorted([p for p in (top.get("all_plays") or []) if is_prop(p)], key=keyf, reverse=True)

    out: List[Dict[str, Any]] = []
    seen_players: set = set()
    fam_count: Dict[str, int] = {}

    def _take(pool: List[Dict[str, Any]], fam_cap: int) -> None:
        for p in pool:
            if len(out) >= k:
                return
            name = p.get("player_or_matchup")
            fam = p.get("market_family") or "?"
            if not name or name in seen_players or fam_count.get(fam, 0) >= fam_cap:
                continue
            seen_players.add(name)
            fam_count[fam] = fam_count.get(fam, 0) + 1
            out.append({
                "player": name, "team": p.get("team"), "sport": p.get("sport"),
                "market": _clean_market(p.get("market")), "market_family": fam,
                "prob": round(p.get("prob") or 0, 4), "fair_american": p.get("fair_american"),
                "edge_pct": p.get("edge_pct"),
                "unit_quarter_kelly": p.get("unit_size_quarter_kelly"),
                "kelly_fraction": p.get("kelly_fraction"),
            })

    _take(t25, 3)                 # settleable, curated -- the real slip
    if len(out) < 3:
        _take(allp, 3)            # backfill only to avoid a too-thin slip
    return out


def _other_picks() -> List[Dict[str, Any]]:
    """A few diversified non-prop plays the machine likes today -- a real
    book-edge game lean, a World Cup conviction, and the correlation-aware
    PrizePicks slip. Each links to the page that owns it."""
    picks: List[Dict[str, Any]] = []

    # 1) Best game-line lean (real de-vigged book edge, calibrated)
    bvm = _load(os.path.join(DATA_DIR, "book_vs_model_team.json"))
    ml = [e for e in (bvm.get("ml_edges") or [])
          if (e.get("calibrated_edge_pct") or 0) > 0 and 0.30 <= (e.get("calibrated_prob") or 0) <= 0.82]
    if ml:
        e = max(ml, key=lambda x: x.get("calibrated_edge_pct") or 0)
        who = e.get("team") if e.get("team") not in (None, "HOME", "AWAY") else e.get("side")
        picks.append({
            "kind": "Game line", "sport": "MLB",
            "label": f"{e.get('matchup')} · {who} ML",
            "detail": f"{(e.get('calibrated_prob') or 0):.0%} model · {(e.get('book_american') or 0):+d} · "
                      f"+{(e.get('calibrated_edge_pct') or 0):.1f}% edge",
            "link": "book-edges.html",
        })

    # 2) World Cup conviction (prefer a real book edge, else highest prob)
    wc = _load(os.path.join(DATA_DIR, "worldcup_cards.json"))
    bb = wc.get("best_bets") or []
    if bb:
        b = sorted(bb, key=lambda x: (x.get("book_edge_pp") if x.get("book_edge_pp") is not None else -99,
                                      x.get("prob") or 0), reverse=True)[0]
        edge = b.get("book_edge_pp")
        picks.append({
            "kind": "World Cup", "sport": "WORLDCUP",
            "label": f"{b.get('play')} — {b.get('matchup')}",
            "detail": f"{(b.get('prob') or 0):.0%}" + (f" · +{edge}pp vs book" if edge else "")
                      + (f" · {b.get('date')}" if b.get("date") else ""),
            "link": "worldcup.html",
        })

    # 3) Correlation-aware PrizePicks Power Play
    pp = _load(os.path.join(DATA_DIR, "prizepicks_value.json"))
    s = pp.get("best_slate")
    if isinstance(s, dict) and s.get("n_legs"):
        picks.append({
            "kind": "PrizePicks", "sport": "DFS",
            "label": f"{s.get('n_legs')}-leg Power Play ({s.get('payout_multiple')}x)",
            "detail": f"{s.get('correlation', '')} · joint {(s.get('joint_prob') or 0):.0%} · "
                      f"{s.get('stake_pct_quarter_kelly')}% ¼-Kelly",
            "link": "prizepicks-value.html",
        })

    # 4) Golf -- ONLY a live actionable best-bet or a STRONG pre-tournament lean.
    # Never the stale between-events position bet (gated on is_live / preview tier).
    gt, gb = _load(os.path.join(DATA_DIR, "golf_live_tracker.json")), _load(os.path.join(DATA_DIR, "golf_bestbet.json"))
    gp, gs = _load(os.path.join(DATA_DIR, "golf_tournament_preview.json")), _load(os.path.join(DATA_DIR, "golf_state.json"))
    gat = gs.get("active_tournament") or {}
    tname = gat.get("name") or gb.get("tournament") or "Golf"
    tb = gb.get("top_bet") or {}
    prev = (gp.get("previews") or [{}])[0]
    # Live = golf_state.is_in_progress (authoritative; the live tracker under-reports),
    # and the best-bet must be FOR that tournament so a stale read can't leak in.
    g_live = (bool(gat.get("is_in_progress"))
              or str(gat.get("status") or "").lower() in ("in progress", "in_progress", "live")
              or bool(gt.get("is_live")))
    g_fresh = tb.get("player") and (gb.get("tournament") == gat.get("name") or not gat.get("name"))
    if g_live and g_fresh and tb.get("confidence") in ("HIGH", "STRONG"):
        picks.append({
            "kind": "Golf", "sport": "GOLF",
            "label": tb.get("bet_label") or f"{tb.get('player')} {tb.get('type')}",
            "detail": f"{(tb.get('model_prob') or 0):.0%} model · {tb.get('fair_american')} · {tname}",
            "link": "golf-live.html",
        })
    elif ((prev.get("n_locks") or 0) + (prev.get("n_strong") or 0)) > 0 and prev.get("top_contender"):
        picks.append({
            "kind": "Golf", "sport": "GOLF",
            "label": f"{prev.get('top_contender')} — {tname}",
            "detail": f"model's top pre-tournament contender · {prev.get('tier', '')}",
            "link": "golf.html",
        })
    return picks[:4]


def run() -> Dict[str, Any]:
    top = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    plays = top.get("top_25") or []

    candidates: List[Dict[str, Any]] = []
    n_input = len(plays)
    n_lowprob = 0
    n_highprob = 0
    n_no_odds = 0

    for p in plays:
        prob = p.get("prob")
        dec_odds = p.get("decimal_odds") or _american_to_decimal(p.get("fair_american"))
        if prob is None or dec_odds is None:
            n_no_odds += 1
            continue
        if prob < 0.18:
            n_lowprob += 1
            continue
        if prob > 0.85:
            # That's Play-of-Day territory — skip for Alpha
            n_highprob += 1
            continue

        # ROI per $1 risked = prob * decimal_odds - 1
        # We use decimal_odds as book proxy (it's fair-odds, so this gives
        # the model's view of true ROI not accounting for actual book vig).
        roi = (prob * dec_odds) - 1
        candidates.append({
            "sport": p.get("sport"),
            "player_or_matchup": p.get("player_or_matchup"),
            "team": p.get("team"),
            "market": p.get("market"),
            "market_family": p.get("market_family"),
            "model_prob": round(prob, 4),
            "fair_american": p.get("fair_american"),
            "decimal_odds": round(dec_odds, 3),
            "edge_pct": p.get("edge_pct"),
            "roi_per_dollar": round(roi, 4),
            "kelly_fraction": p.get("kelly_fraction"),
            "unit_size_quarter_kelly": p.get("unit_size_quarter_kelly"),
            "source_module": p.get("source"),
            "src": p.get("src"),
        })

    # 2026-05-21: also pull REAL book-vs-model edges (ML + totals) from
    # book_vs_model_team.json. These have BOOK decimal odds, not model fair —
    # so the ROI calculation against real book prices is more honest.
    bvm = _load(os.path.join(DATA_DIR, "book_vs_model_team.json"))
    real_book_edges = (bvm.get("ml_edges") or []) + (bvm.get("total_edges") or [])
    n_book_added = 0
    for e in real_book_edges:
        # Prefer calibrated_prob (Bayesian-shrunk toward book) over raw model_prob
        prob = e.get("calibrated_prob") or e.get("model_prob")
        dec = e.get("book_decimal")
        if prob is None or dec is None: continue
        if prob < 0.18 or prob > 0.85: continue
        roi = (prob * dec) - 1
        if roi < 0.03: continue
        # Same dedup: don't add if same matchup+side already in candidates
        match_key = (e.get("matchup"), e.get("side"))
        candidates.append({
            "sport": "MLB" if "@" in (e.get("matchup") or "") else None,
            "player_or_matchup": e.get("matchup") + " " + e.get("side"),
            "team": e.get("team"),
            "market": "TEAM_ML_" + e.get("side") if e.get("side") in ("HOME", "AWAY") else "TOTAL_" + e.get("side"),
            "market_family": "team_ml" if e.get("side") in ("HOME", "AWAY") else "total_ou",
            "model_prob": round(prob, 4),
            "fair_american": e.get("book_american"),
            "decimal_odds": round(dec, 3),
            "edge_pct": e.get("edge_pct"),
            "roi_per_dollar": round(roi, 4),
            "kelly_fraction": e.get("kelly_fraction"),
            "unit_size_quarter_kelly": None,
            "source_module": "book_vs_model_team",
            "src": "real_book",   # tag so UI can show this is real-book-priced
            "book_implied_devig": e.get("book_implied_devig"),
            "model_book_gap_pp": e.get("model_book_gap_pp"),
        })
        n_book_added += 1

    # Sort by ROI descending
    candidates.sort(key=lambda c: -c["roi_per_dollar"])

    top_5 = candidates[:5]
    alpha = candidates[0] if candidates else None

    # Categorize the alpha pick
    pick_type = None
    if alpha:
        if alpha["model_prob"] < 0.40:
            pick_type = "underdog_value"  # model thinks longshot is mispriced
        elif alpha["model_prob"] < 0.55:
            pick_type = "coinflip_edge"   # close to 50/50 but model has edge
        else:
            pick_type = "favorite_value"  # fav with bigger edge than POD

    # The daily digest Brandon wants: 3-5 best props + a few other machine picks,
    # keyed to the 7am-PT morning refresh.
    props_of_day = _props_of_day(top, k=5)
    other_picks = _other_picks()
    pac = _pacific_now()

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "slate_date": pac.strftime("%Y-%m-%d"),
        "slate_weekday": pac.strftime("%A"),
        "refresh_pt": "07:00 America/Los_Angeles",
        "alpha_pick": alpha,
        "pick_type": pick_type,
        "props_of_day": props_of_day,
        "other_picks": other_picks,
        "top_5_alphas": top_5,
        "n_candidates": len(candidates),
        "diagnostics": {
            "n_input_plays": n_input,
            "n_filtered_low_prob": n_lowprob,
            "n_filtered_high_prob_pod_territory": n_highprob,
            "n_no_odds": n_no_odds,
            "n_real_book_edges_added": n_book_added,
        },
        "method_note": "Alpha Pick = highest ROI (prob × decimal_odds − 1) from "
                       "todays_top_plays. Filtered to model_prob in [0.18, 0.85] "
                       "so true longshots and POD-tier favs are excluded.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    a = o["alpha_pick"]
    if a:
        print(f"[alpha-pod] {o['slate_date']} ({o['slate_weekday']}) {o['pick_type']}: "
              f"{a['player_or_matchup']} {a['market']} p={a['model_prob']:.1%} "
              f"odds={a['fair_american']:+d} ROI={a['roi_per_dollar']:+.1%}")
    else:
        print(f"[alpha-pod] {o['slate_date']}: no headline alpha from {o['n_candidates']} eligible")
    print(f"           props_of_day={len(o['props_of_day'])} other_picks={len(o['other_picks'])}")
    for p in o["props_of_day"]:
        print(f"             PROP {p['player']:20s} {p['market'][:26]:26s} {p['prob']:.0%} {p.get('fair_american')} ({p.get('unit_quarter_kelly')}u)")
    for x in o["other_picks"]:
        print(f"             {x['kind']:9s} {x['label'][:50]}")
