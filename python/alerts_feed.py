"""
EdgeStat -- "The Tape": one unified, value-ranked feed of the desk's strongest
ACTIVE signals, aggregated from the modules that already run every cycle.

The site has plenty of signal surfaces (line movement, RLM, top plays, the WC
desk, basketball book edges) -- but no single stream that answers "what's worth
my attention right now?" This builds that: a typed, strength-scored, deduped
feed the product layer points returning users at (and the homepage teases).

It INVENTS no new signals -- it's a reader/ranker over existing artifacts, so it
can never disagree with the page each item links to. Sources, each best-effort:
  * line_movement.json   movers[steam]      -> STEAM   (sharp money moving a line)
  * reverse_line_movement strong_only       -> SHARP   (line moved against the public)
  * todays_top_plays      top plays (Kelly)  -> EDGE    (fresh curated model edge)
  * worldcup_cards        best_bets          -> WC      (tournament conviction play)
  * nba_book_edges        games[lean]        -> HOOPS   (model vs the book)

Output: data/alerts_feed.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "alerts_feed.json")

# per-type caps so one chatty source can't flood the tape; total cap after merge
CAP = {"STEAM": 12, "SHARP": 8, "EDGE": 12, "WC": 6, "HOOPS": 6, "GOLF": 3}
TOTAL_CAP = 40


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _clamp(x: float) -> int:
    return int(max(0, min(100, round(x))))


# Upstream feeds occasionally carry a template/placeholder row (e.g. an un-filled
# "AWA @ HOM"); a product feed shouldn't surface it. Real matchups are "XXX @ YYY"
# with distinct, non-placeholder team codes.
_PLACEHOLDER = {"AWA", "HOM", "AWAY", "HOME", "TBD", "", "@"}


def _valid_matchup(mu: Optional[str]) -> bool:
    if not mu or "@" not in mu:
        return False
    a, _, b = mu.partition("@")
    a, b = a.strip().upper(), b.strip().upper()
    if a in _PLACEHOLDER or b in _PLACEHOLDER or a == b:
        return False
    return True


def _steam(items: List[Dict[str, Any]], ts: str) -> List[Dict[str, Any]]:
    out = []
    for m in items:
        if not m.get("steam") or not _valid_matchup(m.get("matchup")):
            continue
        mv = abs(m.get("ml_move_pp") or 0)
        tot = abs(m.get("total_move") or 0)
        toward = m.get("ml_money_toward") or m.get("total_money_toward") or ""
        kinds = "+".join(m.get("steam_kind") or []) or "line"
        out.append({
            "type": "STEAM", "icon": "📈", "sport": m.get("sport") or "",
            "title": f"Steam: {m.get('matchup','')}",
            "detail": (f"Sharp money toward {toward} — {kinds} moved "
                       f"{mv:.1f}pp{(' / total ' + format(tot, '.1f')) if tot else ''} "
                       f"over {m.get('snapshots','?')} snapshots"),
            "score": _clamp(mv * 4 + tot * 12), "ts": ts, "link": "line-movement.html",
        })
    return out


def _sharp(items: List[Dict[str, Any]], ts: str) -> List[Dict[str, Any]]:
    out = []
    for r in items:
        if not _valid_matchup(r.get("matchup")):
            continue
        delta = abs(r.get("line_delta_pp") or 0)
        out.append({
            "type": "SHARP", "icon": "🧠", "sport": r.get("sport") or "MLB",
            "title": f"Reverse line move: {r.get('matchup','')} · {r.get('pick','')}",
            "detail": r.get("interpretation") or
                      f"{r.get('public_pct','?')}% of public on the other side; line moved {delta:.1f}pp",
            "score": _clamp(delta * 3.5), "ts": ts, "link": "anomalies.html",
        })
    return out


def _edge(items: List[Dict[str, Any]], ts: str) -> List[Dict[str, Any]]:
    out = []
    for p in items:
        prob = p.get("prob") or 0
        edge = p.get("edge_pct") or 0
        kelly = p.get("kelly_fraction") or 0
        name = p.get("player_or_matchup") or p.get("market") or "play"
        mkt = (p.get("market") or "").replace("PP_", "").replace("_", " ")
        out.append({
            "type": "EDGE", "icon": "🎯", "sport": p.get("sport") or "",
            "title": f"Model edge: {name}",
            "detail": (f"{mkt} — {prob:.0%} model{(' (' + str(p.get('fair_american')) + ')') if p.get('fair_american') else ''}, "
                       f"{edge:.0f}% edge, {p.get('unit_size_quarter_kelly', kelly):.2f}u ¼-Kelly"),
            "score": _clamp(30 + kelly * 200 + edge * 0.3), "ts": ts, "link": "todays-top-plays.html",
        })
    return out


def _wc(items: List[Dict[str, Any]], ts: str) -> List[Dict[str, Any]]:
    out = []
    for b in items:
        prob = b.get("prob") or 0
        edge = b.get("book_edge_pp")
        out.append({
            "type": "WC", "icon": "🏆", "sport": "WORLDCUP",
            "title": f"World Cup: {b.get('play','')}",
            "detail": (f"{b.get('matchup','')} · {b.get('date','')} — {prob:.0%}"
                       f"{(' · +' + str(edge) + 'pp vs book') if (edge is not None and edge > 0) else ''}"),
            "score": _clamp(prob * 70 + (edge or 0) * 3), "ts": ts, "link": "worldcup.html",
        })
    return out


def _hoops(items: List[Dict[str, Any]], ts: str) -> List[Dict[str, Any]]:
    out = []
    for g in items:
        ep = g.get("lean_edge_pp") or 0
        out.append({
            "type": "HOOPS", "icon": "🏀", "sport": g.get("sport") or "WNBA",
            "title": f"Book edge: {g.get('matchup','')} · {g.get('lean','')}",
            "detail": (f"model {(g.get('model_p_home') or 0):.0%} vs book {(g.get('book_p_home') or 0):.0%} "
                       f"— +{ep}pp"
                       f"{(' · CLV ' + ('+' if (g.get('clv_pp') or 0) >= 0 else '') + str(g.get('clv_pp')) + 'pp') if g.get('clv_pp') is not None else ''}"),
            "score": _clamp(35 + ep * 9), "ts": ts, "link": "book-edges.html",
        })
    return out


def _golf(state: Dict[str, Any], tracker: Dict[str, Any], bestbet: Dict[str, Any],
          preview: Dict[str, Any], ts: str) -> List[Dict[str, Any]]:
    """Golf on the tape. When a tournament is genuinely LIVE we surface the desk's
    actionable best-bet; otherwise a pre-tournament heads-up for the upcoming major
    (model field-favorites). We do NOT surface the position-based best-bet unless
    is_live -- it goes stale between events (reads a transition leaderboard)."""
    out: List[Dict[str, Any]] = []
    is_live = bool((tracker or {}).get("is_live"))
    at = (state or {}).get("active_tournament") or {}
    tname = at.get("name") or (bestbet or {}).get("tournament") or "PGA event"

    tb = (bestbet or {}).get("top_bet") or {}
    if is_live and tb.get("player") and (tb.get("confidence") in ("HIGH", "STRONG")):
        p = tb.get("model_prob") or 0
        out.append({
            "type": "GOLF", "icon": "⛳", "sport": "GOLF",
            "title": f"Golf: {tb.get('bet_label') or (str(tb.get('player')) + ' ' + str(tb.get('type') or ''))}",
            "detail": (f"{p:.0%} model · {tb.get('fair_american')}"
                       + (f" · {tb.get('reasoning')}" if tb.get("reasoning") else "")),
            "score": _clamp(45 + p * 100), "ts": ts, "link": "golf-live.html",
        })
        return out

    # Pre-tournament heads-up (only for a real upcoming/scheduled event with a field).
    prev = ((preview or {}).get("previews") or [{}])[0]
    contenders = [c.get("player") for c in (prev.get("top_5_contenders") or [])[:3] if c.get("player")]
    status = str(at.get("status") or "").lower()
    if at.get("name") and contenders and (status in ("scheduled", "pre", "") and not is_live):
        out.append({
            "type": "GOLF", "icon": "⛳", "sport": "GOLF",
            "title": f"{tname}: model's field favorites",
            "detail": ("Top by model — " + ", ".join(contenders)
                       + (f" · {prev.get('n_players_total')}-player field" if prev.get("n_players_total") else "")
                       + " · live best-bets once it tees off"),
            "score": 38, "ts": ts, "link": "golf.html",
        })
    return out


def run() -> Dict[str, Any]:
    lm = _load("line_movement.json")
    rlm = _load("reverse_line_movement.json")
    ttp = _load("todays_top_plays.json")
    wc = _load("worldcup_cards.json")
    bb = _load("nba_book_edges.json")
    g_state = _load("golf_state.json")
    g_track = _load("golf_live_tracker.json")
    g_best = _load("golf_bestbet.json")
    g_prev = _load("golf_tournament_preview.json")

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "STEAM": _steam(lm.get("movers") or [], lm.get("generated_at") or ""),
        "SHARP": _sharp(rlm.get("strong_only") or rlm.get("rlm_picks") or [], rlm.get("generated_at") or ""),
        "EDGE": _edge((ttp.get("top_5_by_kelly") or []) + (ttp.get("top_25") or []), ttp.get("generated_at") or ""),
        "WC": _wc((wc.get("best_bets") or [])[:8], wc.get("generated_at") or ""),
        "HOOPS": _hoops([g for g in (bb.get("games") or []) if (g.get("lean_edge_pp") or 0) >= 1.0],
                        bb.get("generated_at") or ""),
        "GOLF": _golf(g_state, g_track, g_best, g_prev,
                      g_track.get("generated_at") or g_state.get("generated_at") or ""),
    }

    items: List[Dict[str, Any]] = []
    seen = set()
    for typ, lst in buckets.items():
        lst.sort(key=lambda x: -x["score"])
        kept = 0
        for it in lst:
            key = (it["type"], it["title"])
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
            kept += 1
            if kept >= CAP.get(typ, 10):
                break

    # final order: strongest first across all types (the tape is value-ranked,
    # not strictly chronological -- the source feeds share a per-run timestamp).
    items.sort(key=lambda x: -x["score"])
    items = items[:TOTAL_CAP]

    counts = {t: sum(1 for it in items if it["type"] == t) for t in CAP}
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n": len(items),
        "counts": counts,
        "note": ("One value-ranked stream of the desk's strongest ACTIVE signals, aggregated "
                 "from the modules that run every cycle (steam, reverse line moves, fresh "
                 "curated model edges, World Cup conviction plays, basketball book edges). It "
                 "surfaces existing signals — every item links to the page that owns it. "
                 "Refreshes with the pipeline (~2h)."),
        "items": items,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[alerts-feed] {o['n']} signals on the tape: " +
          ", ".join(f"{k} {v}" for k, v in o["counts"].items()) + f" -> {OUT}")
    for it in o["items"][:10]:
        print(f"  [{it['score']:3d}] {it['type']:5s} {it['title'][:54]}")
