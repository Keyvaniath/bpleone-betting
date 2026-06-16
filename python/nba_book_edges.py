"""
EdgeStat -- NBA / WNBA model-vs-book edge board (free ESPN odds).

The MLB desk already edges off the free ESPN/DraftKings moneyline (book_vs_model);
this brings the same to the two in-season basketball leagues. For every upcoming
game it joins the model's win probability ({sport}_state.json p_home_win) with the
de-vigged DraftKings moneyline from ESPN's scoreboard and reports the edge per side.

Honest framing: NBA/WNBA closing moneylines are fairly sharp, so most edges are
small -- the value is the transparency (and spotting the rare game where the model
genuinely diverges from the market). NBA is empty in the off-season; WNBA is live.

Output: data/nba_book_edges.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_book_edges.json")
HIST = os.path.join(DATA_DIR, "nba_odds_history.json")
SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/{lg}/scoreboard?dates={d}"
UA = {"User-Agent": "Mozilla/5.0"}
LEAGUES = ("nba", "wnba")
MIN_EDGE_PP = 1.0    # surface a side as a lean when the model beats the de-vig book by >=1pp
MOVE_EPS = 0.004     # only snapshot history when the de-vig home line moves >=0.4pp
MAX_SNAPS = 60       # cap snapshots per game
KEEP_DAYS = 6        # prune history older than this


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12) as r:
            return json.load(r)
    except Exception:
        return None


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _amer(s) -> Optional[int]:
    try:
        return int(str(s).replace("+", "").strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _imp(am: Optional[int]) -> Optional[float]:
    if am is None:
        return None
    return 100.0 / (am + 100.0) if am >= 0 else abs(am) / (abs(am) + 100.0)


def _model_index(sport: str) -> Dict[str, float]:
    """home-team (lowercased) -> model p_home_win for today's upcoming games."""
    idx: Dict[str, float] = {}
    for g in (_load(f"{sport}_state.json").get("games") or []):
        ph = g.get("p_home_win")
        mu = g.get("matchup") or ""
        if ph is None or "@" not in mu:
            continue
        home = mu.split("@", 1)[1].strip().lower()
        try:
            idx[home] = float(ph)
        except (TypeError, ValueError):
            continue
    return idx


def _book_2way(comp: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    o = (comp.get("odds") or [{}])[0]
    ml = o.get("moneyline") or {}
    home_ml = _amer((((ml.get("home") or {}).get("close") or {}) or {}).get("odds"))
    away_ml = _amer((((ml.get("away") or {}).get("close") or {}) or {}).get("odds"))
    return home_ml, away_ml


def _update_history(edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Append a timestamped book-line snapshot per game (only on a real move) so we
    can measure CLV open->close. Capped + pruned. This is the sharp's metric: did
    the market move TOWARD the side the model leaned, by the time it closed."""
    try:
        with open(HIST, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = {}
    snaps = hist.get("snaps") or {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for e in edges:
        k = e["_key"]
        seq = snaps.setdefault(k, [])
        bp = e["book_p_home"]
        if not seq or abs(seq[-1].get("bp", -9) - bp) >= MOVE_EPS:
            seq.append({"ts": now, "bp": bp, "mp": e["model_p_home"], "side": e["lean_side"]})
            snaps[k] = seq[-MAX_SNAPS:]
    # prune old game-days
    cutoff = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    snaps = {k: v for k, v in snaps.items() if (k.split("|")[-1] >= cutoff)}
    out = {"updated_at": now, "snaps": snaps}
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


def _clv(snaps: Dict[str, Any]) -> Dict[str, Any]:
    """CLV per game from the snapshot trail: how far the de-vig line moved toward
    the model's lean, open->latest. Positive = the model beat the (current) close."""
    rows = []
    for k, seq in snaps.items():
        if len(seq) < 2:
            continue
        o, c = seq[0], seq[-1]
        side = c.get("side") or o.get("side")
        # move of the LEANED side's implied prob, open -> latest
        delta_home = (c["bp"] - o["bp"])
        clv = delta_home if side == "HOME" else -delta_home
        sp, mu, dt_ = k.split("|")
        rows.append({"sport": sp, "matchup": mu, "date": dt_,
                     "open_book_p_home": round(o["bp"], 4), "now_book_p_home": round(c["bp"], 4),
                     "lean_side": side, "clv_pp": round(clv * 100, 1),
                     "beat_close": clv > 0, "snapshots": len(seq)})
    rows.sort(key=lambda r: -r["clv_pp"])
    tracked = [r for r in rows if r["snapshots"] >= 2]
    n_beat = sum(1 for r in tracked if r["beat_close"])
    return {
        "n_tracked": len(tracked),
        "n_beat_close": n_beat,
        "beat_close_rate": round(n_beat / len(tracked), 3) if tracked else None,
        "avg_clv_pp": round(sum(r["clv_pp"] for r in tracked) / len(tracked), 2) if tracked else None,
        "rows": rows,
    }


def run() -> Dict[str, Any]:
    today = dt.date.today()
    edges: List[Dict[str, Any]] = []
    n_games = 0
    for sport in LEAGUES:
        model = _model_index(sport)
        if not model:
            continue
        seen = set()
        for i in range(0, 3):
            d = today + dt.timedelta(days=i)
            sb = _http(SB.format(lg=sport, d=d.strftime("%Y%m%d"))) or {}
            for ev in (sb.get("events") or []):
                comp = (ev.get("competitions") or [{}])[0]
                if (comp.get("status") or {}).get("type", {}).get("state") != "pre":
                    continue
                cs = comp.get("competitors") or []
                home = next(((c.get("team") or {}).get("displayName") for c in cs if c.get("homeAway") == "home"), None)
                away = next(((c.get("team") or {}).get("displayName") for c in cs if c.get("homeAway") == "away"), None)
                if not home or not away or (sport, home) in seen:
                    continue
                p_home = model.get(home.lower())
                if p_home is None:
                    continue
                home_ml, away_ml = _book_2way(comp)
                ih, ia = _imp(home_ml), _imp(away_ml)
                if not ih or not ia or (ih + ia) <= 0:
                    continue
                seen.add((sport, home))
                n_games += 1
                book_home = ih / (ih + ia)
                e_home = round((p_home - book_home) * 100, 1)
                # the recommended side is whichever the model likes MORE than the book
                side = "HOME" if e_home >= 0 else "AWAY"
                edge_pp = abs(e_home)
                edges.append({
                    "sport": sport.upper(), "date": d.isoformat(),
                    "matchup": f"{away} @ {home}", "home": home, "away": away,
                    "model_p_home": round(p_home, 4), "book_p_home": round(book_home, 4),
                    "home_ml": home_ml, "away_ml": away_ml,
                    "edge_home_pp": e_home,
                    "lean": (f"{home if side == 'HOME' else away} ML"),
                    "lean_side": side,
                    "lean_edge_pp": round(edge_pp, 1),
                    "_key": f"{sport.upper()}|{away} @ {home}|{d.isoformat()}",
                })

    edges.sort(key=lambda x: -x["lean_edge_pp"])
    leans = [e for e in edges if e["lean_edge_pp"] >= MIN_EDGE_PP]

    # CLV: snapshot the lines now, then measure open->latest movement on our leans.
    hist = _update_history(edges)
    clv = _clv(hist.get("snaps") or {})
    clv_by_key = {f"{r['sport']}|{r['matchup']}|{r['date']}": r for r in clv["rows"]}
    for e in edges:
        c = clv_by_key.get(e.pop("_key", None))
        if c:
            e["clv_pp"] = c["clv_pp"]
            e["beat_close"] = c["beat_close"]

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "ESPN / DraftKings free moneyline (no key)",
        "n_games": n_games,
        "n_leans": len(leans),
        "min_edge_pp": MIN_EDGE_PP,
        "clv": {k: v for k, v in clv.items() if k != "rows"},
        "note": ("Model win prob ({sport}_state) vs the de-vigged DraftKings moneyline. "
                 "Basketball closing lines are sharp, so edges are usually small -- this is "
                 "transparency + spotting genuine divergence, not a promise of value. CLV = how "
                 "far the line moved TOWARD our lean (open->latest); beating the close is proof "
                 "of edge independent of any single result. NBA is empty out of season."),
        "games": edges,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    cv = o.get("clv") or {}
    print(f"[nba-book-edges] {o['n_games']} games priced, {o['n_leans']} leans >= {o['min_edge_pp']}pp | "
          f"CLV tracked {cv.get('n_tracked', 0)} beat-close {cv.get('beat_close_rate')} avg {cv.get('avg_clv_pp')}pp -> {OUT}")
    for e in o["games"][:8]:
        print(f"    {e['sport']:4s} {e['matchup']:34s} model {e['model_p_home']:.0%} vs book {e['book_p_home']:.0%} "
              f"-> {e['lean']} +{e['lean_edge_pp']}pp")
