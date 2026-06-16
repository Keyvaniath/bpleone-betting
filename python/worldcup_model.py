"""
EdgeStat -- 2026 World Cup match model (the deep desk, MLB-card style).

Soccer needs a 3-WAY model: the generic engine's binary p_home_win ignores
draws, which are ~25% of group-stage matches. This module prices every
upcoming match properly:

  strength  ->  seeded elo bands (public FIFA-ranking tiers, coarse on purpose)
                blended with IN-TOURNAMENT results: seed weight fades with each
                match played (k=2), so by the knockouts the tournament's own
                evidence dominates. Honest: bands are labeled on every card.
  goals     ->  independent-Poisson scoring grid. Total goal expectation per
                match anchored to the modern WC average (~2.6), split between
                the sides by elo gap (bounded), then P(1X2) / P(over 2.5) /
                P(BTTS) come off the grid -- the same show-your-work Poisson
                math as the MLB innings models.
  context   ->  group tables computed from real finals (soccer_results.json),
                played-result strips, and per-card "why" lines (band + record).

Output: data/worldcup_cards.json
  { cards: [ {matchup, date, group_phase, p_home, p_draw, p_away, fair_*,
              exp_goals_home/away, p_over_2_5, p_btts, bands, records, why} ],
    standings: {team: {gp, w, d, l, gf, ga, pts}},
    results: [...played finals...] }
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE = os.path.join(DATA_DIR, "worldcup_state.json")
RESULTS = os.path.join(DATA_DIR, "soccer_results.json")
OUT = os.path.join(DATA_DIR, "worldcup_cards.json")

SB = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={d}"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings"
UA = {"User-Agent": "Mozilla/5.0"}

# ---------------------------------------------------------------------------
# Seed strength: coarse public-knowledge FIFA-ranking tiers, NOT precise
# ratings -- and the blend below retires them as real matches accrue.
# Teams not listed seed at MID (1500). Names must match ESPN displayName.
# ---------------------------------------------------------------------------
BAND_ELO = {"ELITE": 1760, "STRONG": 1680, "GOOD": 1590, "MID": 1500, "DEV": 1430}
SEED_BAND = {
    "Argentina": "ELITE", "France": "ELITE", "Spain": "ELITE", "England": "ELITE",
    "Brazil": "ELITE",
    "Portugal": "STRONG", "Netherlands": "STRONG", "Belgium": "STRONG",
    "Germany": "STRONG", "Croatia": "STRONG", "Uruguay": "STRONG",
    "Morocco": "STRONG", "Colombia": "STRONG", "Italy": "STRONG",
    "Japan": "GOOD", "Switzerland": "GOOD", "Mexico": "GOOD",
    "United States": "GOOD", "Senegal": "GOOD", "Iran": "GOOD",
    "South Korea": "GOOD", "Austria": "GOOD", "Australia": "GOOD",
    "Ecuador": "GOOD", "Türkiye": "GOOD", "Sweden": "GOOD", "Norway": "GOOD",
    "Egypt": "GOOD", "Algeria": "GOOD", "Ivory Coast": "GOOD",
    "Czechia": "MID", "Scotland": "MID", "Paraguay": "MID", "Canada": "MID",
    "Qatar": "MID", "Saudi Arabia": "MID", "Ghana": "MID", "Panama": "MID",
    "Uzbekistan": "MID", "Jordan": "MID", "Iraq": "MID", "South Africa": "MID",
    "Tunisia": "MID", "Bosnia-Herzegovina": "MID",
    "Haiti": "DEV", "Curaçao": "DEV", "Congo DR": "DEV",
    "Cape Verde": "DEV", "New Zealand": "DEV",
}
SEED_K = 2.0          # seed weight = K/(K + matches_played): 1.0 -> 0.5 by game 2
HFA_ELO = 20          # mostly-neutral venues; hosts get crowds, not a club edge
HALF_GOALS = 1.36     # per-team baseline goals (even match -> ~2.72 total)
GOAL_K = 0.50         # elo gap -> goal expectation (per 400 elo, exp scale)
MAX_GOALS = 8         # Poisson grid size


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12) as r:
            return json.load(r)
    except Exception:
        return None


def _load(p) -> Dict[str, Any]:
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


def _devig3(h, d, a) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    ph, pd, pa = _imp(h), _imp(d), _imp(a)
    if ph is None or pd is None or pa is None:
        return (None, None, None)
    s = ph + pd + pa
    return (ph / s, pd / s, pa / s) if s > 0 else (None, None, None)


def _book_from_comp(comp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract DraftKings 3-way moneyline + total from an ESPN competition's odds
    block (closing line). Returns None if no usable odds, so the model degrades to
    fair-value-only for that match."""
    o = (comp.get("odds") or [{}])[0]
    if not o:
        return None
    ml = o.get("moneyline") or {}
    home_ml = _amer((((ml.get("home") or {}).get("close") or {}) or {}).get("odds"))
    away_ml = _amer((((ml.get("away") or {}).get("close") or {}) or {}).get("odds"))
    draw_ml = _amer((o.get("drawOdds") or {}).get("moneyLine"))
    tot = o.get("total") or {}
    over = ((tot.get("over") or {}).get("close") or {})
    under = ((tot.get("under") or {}).get("close") or {})
    line = None
    for v in (over.get("line"), under.get("line"), o.get("overUnder")):
        try:
            line = float(str(v).lower().lstrip("ou"))
            break
        except (TypeError, ValueError):
            continue
    if home_ml is None and away_ml is None and line is None:
        return None
    return {
        "provider": (o.get("provider") or {}).get("name") or "book",
        "home_ml": home_ml, "draw_ml": draw_ml, "away_ml": away_ml,
        "total_line": line,
        "over_ml": _amer(over.get("odds")), "under_ml": _amer(under.get("odds")),
    }


def _wc_results() -> List[Dict[str, Any]]:
    return [m for m in (_load(RESULTS).get("matches") or [])
            if m.get("league") == "fifa.world"
            and m.get("home_score") is not None and m.get("away_score") is not None]


def _standings(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    st: Dict[str, Dict[str, Any]] = {}
    def row(t):
        return st.setdefault(t, {"gp": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0})
    for m in results:
        h, a = row(m["home"]), row(m["away"])
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        h["gp"] += 1; a["gp"] += 1
        h["gf"] += hs; h["ga"] += as_; a["gf"] += as_; a["ga"] += hs
        if hs > as_: h["w"] += 1; h["pts"] += 3; a["l"] += 1
        elif hs < as_: a["w"] += 1; a["pts"] += 3; h["l"] += 1
        else: h["d"] += 1; a["d"] += 1; h["pts"] += 1; a["pts"] += 1
    return st


def _groups() -> List[Dict[str, Any]]:
    """Official group tables (A-L) straight from ESPN's standings endpoint --
    authoritative W/D/L/Pts/rank with FIFA tiebreakers already applied, plus the
    `advanced` clinch flag. Empty list on any fetch failure (page falls back to
    the results-computed pooled table)."""
    data = _http(STANDINGS) or {}
    out: List[Dict[str, Any]] = []
    for ch in (data.get("children") or []):
        entries = ((ch.get("standings") or {}).get("entries")) or []
        rows = []
        for e in entries:
            s = {x.get("name"): x.get("value") for x in (e.get("stats") or [])}
            rows.append({
                "team": (e.get("team") or {}).get("displayName"),
                "gp": int(s.get("gamesPlayed") or 0), "w": int(s.get("wins") or 0),
                "d": int(s.get("ties") or 0), "l": int(s.get("losses") or 0),
                "gf": int(s.get("pointsFor") or 0), "ga": int(s.get("pointsAgainst") or 0),
                "gd": int(s.get("pointDifferential") or 0), "pts": int(s.get("points") or 0),
                "rank": int(s.get("rank") or 99), "advanced": bool(s.get("advanced")),
            })
        rows.sort(key=lambda r: r["rank"])
        if rows:
            out.append({"name": ch.get("name") or ch.get("abbreviation"), "teams": rows})
    return out


def _record_elo(team: str, st: Dict[str, Dict[str, Any]]) -> Tuple[float, int]:
    """In-tournament elo from points-per-game + goal difference. 1500-anchored."""
    r = st.get(team)
    if not r or not r["gp"]:
        return 1500.0, 0
    ppg = r["pts"] / r["gp"]                  # 0..3
    gd_pg = (r["gf"] - r["ga"]) / r["gp"]
    return 1500.0 + (ppg - 1.4) * 120 + max(-2.5, min(2.5, gd_pg)) * 40, r["gp"]


def team_elo(team: str, st: Dict[str, Dict[str, Any]]) -> Tuple[float, str, int]:
    band = SEED_BAND.get(team, "MID")
    seed = BAND_ELO[band]
    rec, gp = _record_elo(team, st)
    w = SEED_K / (SEED_K + gp)                # seed fades as the tournament speaks
    return w * seed + (1 - w) * rec, band, gp


def _pois(k: int, lam: float) -> float:
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def price_match(home: str, away: str, st) -> Dict[str, Any]:
    he, hband, hgp = team_elo(home, st)
    ae, aband, agp = team_elo(away, st)
    diff = (he + HFA_ELO) - ae
    # Each side's expected goals flexes off the elo gap around a per-team baseline
    # (exp scale). Unlike a fixed-total split, the TOTAL now rises with mismatch
    # (blowouts outscore even games) -- so over/under 2.5 is a real signal per
    # match instead of a flat ~48%% on every card. g normalized per 400 elo.
    g = diff / 400.0
    lam_h = max(0.30, min(3.4, HALF_GOALS * math.exp(GOAL_K * g)))
    lam_a = max(0.30, min(3.4, HALF_GOALS * math.exp(-GOAL_K * g)))
    ph = pd = pa = p_over = p_btts = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = _pois(i, lam_h) * _pois(j, lam_a)
            if i > j: ph += p
            elif i == j: pd += p
            else: pa += p
            if i + j >= 3: p_over += p
            if i >= 1 and j >= 1: p_btts += p
    norm = ph + pd + pa
    ph, pd, pa = ph / norm, pd / norm, pa / norm

    def amer(p):
        if p <= 0.005 or p >= 0.995: return None
        return -int(round(100 / ((1 / p) - 1))) if p >= 0.5 else int(round(((1 / p) - 1) * 100))

    return {
        "p_home": round(ph, 4), "p_draw": round(pd, 4), "p_away": round(pa, 4),
        "fair_home": amer(ph), "fair_draw": amer(pd), "fair_away": amer(pa),
        "exp_goals_home": round(lam_h, 2), "exp_goals_away": round(lam_a, 2),
        "exp_total": round(lam_h + lam_a, 2),
        "p_over_2_5": round(p_over, 4), "p_btts": round(p_btts, 4),
        "home_band": hband, "away_band": aband,
        "home_gp": hgp, "away_gp": agp,
        "why": (f"{home} seeds {hband}{' + ' + str(hgp) + 'gp evidence' if hgp else ''} vs "
                f"{away} {aband}{' + ' + str(agp) + 'gp' if agp else ''}; "
                f"elo edge {diff:+.0f} -> {lam_h:.2f}-{lam_a:.2f} expected goals"),
    }


def _recommend(c: Dict[str, Any]) -> Dict[str, Any]:
    """EdgeStat's explicit call for a card: one prediction + the best 1-2 props.
    Centralized here (not in page JS) so the recommendation is single-sourced and
    can be settled later exactly as displayed."""
    # Prediction = the 1X2 side the model favors (draw included if it's highest).
    sides = [
        ("HOME_ML", f"{c['home']} win", c["p_home"], c["fair_home"]),
        ("DRAW",    "Draw",             c["p_draw"], c["fair_draw"]),
        ("AWAY_ML", f"{c['away']} win", c["p_away"], c["fair_away"]),
    ]
    mkt, label, prob, fair = max(sides, key=lambda t: t[2])
    # Cutoffs aligned to the DISPLAYED (rounded) %, so a shown "52%" is never
    # mislabeled TOSS-UP: 0.515 is the lowest value that rounds to 52%.
    conf = "STRONG" if prob >= 0.595 else ("LEAN" if prob >= 0.515 else "TOSS-UP")
    prediction = {"market": mkt, "label": label, "prob": round(prob, 4),
                  "fair": fair, "confidence": conf}

    # Props ranked by conviction (distance from a coin); keep those past the floor.
    po, pb = c["p_over_2_5"], c["p_btts"]
    cands = [
        ("OVER_2.5", "Over 2.5 goals", po) if po >= 0.5 else ("UNDER_2.5", "Under 2.5 goals", 1 - po),
        ("BTTS_YES", "Both teams to score", pb) if pb >= 0.5 else ("BTTS_NO", "Both teams NOT to score", 1 - pb),
    ]
    props = [{"market": m, "label": l, "prob": round(p, 4)}
             for m, l, p in sorted(cands, key=lambda t: -t[2]) if p >= 0.53]
    return {"prediction": prediction, "props": props[:2]}


def run() -> Dict[str, Any]:
    results = _wc_results()
    st = _standings(results)

    # Upcoming matches: today's state + the next few scoreboard days (pre-game only)
    cards: List[Dict[str, Any]] = []
    seen = set()
    upcoming: List[Tuple[Optional[str], Optional[str], str]] = []
    book_by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # Scoreboard FIRST (its date is the slate date); the state file is the
    # fallback for anything the 5-day window misses. Dedup by PAIR -- a group
    # fixture can't repeat, and the same match must not appear under two dates.
    today = dt.date.today()
    for i in range(0, 5):
        d = today + dt.timedelta(days=i)
        sb = _http(SB.format(d=d.strftime("%Y%m%d"))) or {}
        for ev in sb.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            # Only genuinely SCHEDULED matches (state "pre"); skip live ("in") and
            # final ("post") -- a pre-game model shouldn't card a match that's
            # already kicked off with a stale pre-game prediction.
            if (comp.get("status") or {}).get("type", {}).get("state") != "pre":
                continue
            cs = comp.get("competitors") or []
            home = next(((c.get("team") or {}).get("displayName") for c in cs if c.get("homeAway") == "home"), None)
            away = next(((c.get("team") or {}).get("displayName") for c in cs if c.get("homeAway") == "away"), None)
            if home and away and "Place" not in home and "Place" not in away:
                upcoming.append((home, away, d.isoformat()))
                bk = _book_from_comp(comp)
                if bk:
                    book_by_pair[(home, away)] = bk
    # No state-file fallback: it lists live/final games with a STALE status (a
    # match shown "Scheduled" there may already be at halftime), which leaked
    # kicked-off games onto the board. The live scoreboard above is the single
    # fresh source -- 5 forward days covers the whole upcoming slate.
    #
    # Belt-and-suspenders: drop any match already PLAYED (in the results feed),
    # orientation-agnostic so a home/away flip can't slip a finished game through.
    # Group fixtures are one-and-done, so this can't drop a real rematch.
    played = {(m.get("home"), m.get("away")) for m in results}
    played |= {(m.get("away"), m.get("home")) for m in results}
    for home, away, date in upcoming:
        if not home or not away or (home, away) in seen:
            continue
        if (home, away) in played:
            continue
        seen.add((home, away))
        card = {"matchup": f"{away} @ {home}", "home": home, "away": away, "date": date}
        card.update(price_match(home, away, st))
        card["rec"] = _recommend(card)
        # Real EDGE vs the DraftKings line (de-vigged), where ESPN carries it.
        # This is what turns the desk from fair-value into edge-finding: a +edge
        # means the model gives the side a better chance than the book's price.
        bk = book_by_pair.get((home, away))
        if bk:
            bh, bd, ba = _devig3(bk.get("home_ml"), bk.get("draw_ml"), bk.get("away_ml"))
            edges: Dict[str, float] = {}
            if bh is not None:
                edges["HOME_ML"] = round((card["p_home"] - bh) * 100, 1)
            if ba is not None:
                edges["AWAY_ML"] = round((card["p_away"] - ba) * 100, 1)
            if bd is not None:
                edges["DRAW"] = round((card["p_draw"] - bd) * 100, 1)
            io, iu = _imp(bk.get("over_ml")), _imp(bk.get("under_ml"))
            if bk.get("total_line") == 2.5 and io and iu and (io + iu) > 0:
                over_devig = io / (io + iu)
                edges["OVER_2.5"] = round((card["p_over_2_5"] - over_devig) * 100, 1)
                edges["UNDER_2.5"] = round(((1 - card["p_over_2_5"]) - (1 - over_devig)) * 100, 1)
            card["book"] = {
                "provider": bk.get("provider"),
                "home_ml": bk.get("home_ml"), "draw_ml": bk.get("draw_ml"), "away_ml": bk.get("away_ml"),
                "total_line": bk.get("total_line"), "over_ml": bk.get("over_ml"), "under_ml": bk.get("under_ml"),
                "home_devig": round(bh, 4) if bh is not None else None,
                "draw_devig": round(bd, 4) if bd is not None else None,
                "away_devig": round(ba, 4) if ba is not None else None,
            }
            card["edges_vs_book"] = edges
        cards.append(card)
    cards.sort(key=lambda c: (c.get("date") or "", c["matchup"]))

    # Best Bets board: the highest-conviction plays across the whole slate, ranked.
    # One play per (match, market) so a single game can't flood the board; result
    # picks need >=55%, props >=55% (past the noise floor with margin).
    best: List[Dict[str, Any]] = []

    def _consider(c, label, market, prob, fair, kind):
        if prob < 0.55:
            return
        edge = (c.get("edges_vs_book") or {}).get(market)
        # Don't feature a play the book actively disagrees with (negative edge =
        # the book prices the side higher than the model, so it's -EV to back).
        if edge is not None and edge < 0:
            return
        best.append({"matchup": c["matchup"], "date": c["date"], "play": label,
                     "market": market, "prob": prob, "fair": fair,
                     "book_edge_pp": edge, "kind": kind})

    for c in cards:
        rec = c.get("rec") or {}
        pred = rec.get("prediction") or {}
        if pred.get("label"):
            _consider(c, pred["label"], pred["market"], pred.get("prob", 0), pred.get("fair"), "result")
        for p in (rec.get("props") or []):
            _consider(c, p["label"], p["market"], p.get("prob", 0), None, "prop")

    # Plays with a real book EDGE lead (ranked by edge); model-only plays follow by
    # conviction. A measured edge vs the line is worth more than a fair-value lean.
    best.sort(key=lambda b: (0, -b["book_edge_pp"]) if b.get("book_edge_pp") is not None
              else (1, -b["prob"]))

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_cards": len(cards),
        "n_results": len(results),
        "method_note": ("3-way Poisson match model. Strength = coarse FIFA-tier seed bands "
                        f"(labeled on every card) blended with in-tournament record elo; seed "
                        f"weight = {SEED_K:g}/({SEED_K:g}+matches played), so the tournament's own "
                        "evidence takes over by the knockouts. Goals: ~2.6/match split by elo gap, "
                        "independent Poisson grid -> 1X2 / over 2.5 / BTTS. Fair odds are 0-vig."),
        "best_bets": best,
        "cards": cards,
        "groups": _groups(),
        "standings": st,
        "results": sorted(results, key=lambda m: m.get("date") or ""),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wc-model] {o['n_cards']} cards, {o['n_results']} finals -> {OUT}")
    for c in o["cards"][:6]:
        print(f"  {c['date']} {c['matchup'][:34]:34s} 1X2 {c['p_home']:.0%}/{c['p_draw']:.0%}/{c['p_away']:.0%} "
              f"(fair {c['fair_home']}/{c['fair_draw']}/{c['fair_away']}) O2.5 {c['p_over_2_5']:.0%} BTTS {c['p_btts']:.0%}")
