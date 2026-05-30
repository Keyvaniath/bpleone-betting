"""
EdgeStat -- TODAY'S TOP PLAYS unified board.

Brandon's curated list of ONLY the picks worth betting today:
  - Probability >= 70% (no coin-flip noise)
  - Across all sports / sources
  - Ranked by edge_pct (Kelly EV at fair market price)
  - DEDUPED so you never see 14 "92% UNDER X.5" picks for the same family
  - DIVERSIFIED so top 25 mixes sports/markets/players (max 6 per sport)

Pulls from slate_player_pot.json + slate_team_pot.json.

Per-source fair pricing (critical -- not all sources are -110):
  PrizePicks 2-pick:  pays 3x -> each leg fair odds = sqrt(3) decimal = -136 American
  PrizePicks 3-pick:  pays 5x -> each leg fair odds = 5^(1/3) decimal = -141 American
  Standard market:    -110 (decimal 1.909)

  We use -136 for any PP leg without an explicit fair_american. This drops
  the inflated +75% edge on PP picks down to realistic +25-40% territory.

Output: data/todays_top_plays.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "todays_top_plays.json")

MIN_PROB = 0.55              # was 0.70 -- but apply AFTER shrinkage now
MIN_EDGE_PCT = 1.0           # must be >= 1% edge to make the board
MAX_PICKS_PER_SPORT = 6      # diversity cap in top 25
MAX_PICKS_PER_PLAYER = 2     # don't load up on same player's market variants

# Calibration shrinkage: raw model probs are usually overconfident
# (small-sample sample means without uncertainty). Shrink toward a slightly-
# above-coinflip baseline. This compresses 92% picks down to ~73-76% and
# 70% picks to ~64% -- still useful ranking, more believable edges.
SHRINKAGE_BASELINE_PROB = 0.55
# Per-source shrinkage weight (higher = trust the model more, less shrink).
# Game-line model (today.json) has years of MLB data behind it: less shrink.
# PrizePicks raw probs are based on PP's projection model which we don't
# fully trust: more shrink.
DEFAULT_SHRINKAGE_W = 0.55     # default mix toward baseline
SOURCE_SHRINKAGE_W = {
    "today": 0.80,                       # MLB game model -- well-calibrated
    "today_reco": 0.80,
    "mlb_ext_batter": 0.60,
    "mlb_ext_pitcher": 0.65,
    "mlb_batter_logs": 0.55,             # raw last-14 rate -- needs shrink
    "pitcher_matchup": 0.65,
    "pitcher_form_regression": 0.65,
    "mlb_batter_sp_edges": 0.60,
    "mlb_batter_situational": 0.55,
    "mlb_batter_lvr": 0.60,              # MLB Stats API real splits -- decent trust
    "pp_over": 0.45,                     # PP projections -- aggressive shrink
    "pp_under": 0.45,
    "nba_ext": 0.55,
    "wnba_ext": 0.55,
    "nhl_ext": 0.55,
    "nhl_goalie": 0.65,
    "mlb_team_total": 0.60,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _kelly_fraction(p, decimal_odds):
    """Standard Kelly: f = (b*p - q) / b where b = decimal_odds - 1"""
    if not decimal_odds or decimal_odds <= 1: return 0
    b = decimal_odds - 1
    q = 1 - p
    f = (b * p - q) / b
    return max(0, min(0.25, f))    # cap at 25% (fractional Kelly)


def _edge_pct(p, decimal_odds):
    """Edge = (p * decimal_odds) - 1 (Kelly EV at $1 bet)."""
    if not decimal_odds or decimal_odds <= 1: return 0
    return p * decimal_odds - 1


def _fair_odds_for_source(source, src_type):
    """Return default fair_american for picks that don't supply one."""
    if not source: return -110
    s = str(source).lower()
    if "pp" in s or "pickem" in s or "prizepicks" in s:
        return -136    # PP 2-pick break-even per leg
    return -110


def _market_family(market):
    """Strip line value so 'HRR_under_3.5' and 'HRR_under_4.5' collapse."""
    if not market: return ""
    m = str(market)
    # drop trailing _<number> and trailing _.5
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", m)
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m.lower()


def _market_implied_prob(american):
    """American odds -> implied probability (no vig adjustment)."""
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def _load_learned_weights():
    """Self-learning feedback: read learned per-source weights if available.
    Prefers w_final (includes user overrides from /model-control) over w_learned."""
    p = os.path.join(DATA_DIR, "learned_weights.json")
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: d = json.load(f)
        out = {}
        for src, w in (d.get("weights") or {}).items():
            # w_final includes user overrides; use it whenever set, otherwise w_learned (with data)
            wf = w.get("w_final")
            wl = w.get("w_learned")
            if wf is not None and w.get("user_override") is not None:
                out[src] = wf  # user override -> always apply
            elif wl is not None and w.get("n_settled", 0) > 0:
                out[src] = wl  # learned with data
        return out
    except Exception:
        return {}


_LEARNED_W_CACHE = None
_FAMILY_W_CACHE = None


def _load_family_weights():
    """Per-market-family learned weights — the bridge to this board, whose
    candidates are tagged by MARKET, not by the ledger source name (so the
    per-source weights above never match a displayed candidate). Market family
    is the shared vocabulary."""
    p = os.path.join(DATA_DIR, "learned_weights.json")
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: d = json.load(f)
        out = {}
        for fam, w in (d.get("weights_by_family") or {}).items():
            wl = w.get("w_learned")
            if wl is not None and w.get("n_settled", 0) > 0:
                out[fam] = wl
        return out
    except Exception:
        return {}


def _market_family(market):
    """Mirror of all_picks_tracker._market_family so families match the ledger."""
    if not market: return "unknown"
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", str(market))
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m.lower() or "unknown"


_PROVEN_NEG_CACHE = None
CURATE_MIN_N = 25          # need a real sample before calling a family a loser
CURATE_MAX_NET = -5.0      # lost > 5u over that sample => proven -EV, do not publish


def _load_proven_negative_families():
    """Market families PROVEN to lose money over a real sample (from the settled
    ledger's by_market_family). The featured board hard-excludes these. A
    professional desk does not publish -EV markets no matter how high the raw
    hit rate -- e.g. k_1plus hits 61% but is priced so short it bleeds -84u."""
    p = os.path.join(DATA_DIR, "all_picks_ledger.json")
    if not os.path.exists(p): return set()
    try:
        with open(p) as f: d = json.load(f)
        out = set()
        for fam, v in (d.get("by_market_family") or {}).items():
            n = (v.get("wins") or 0) + (v.get("losses") or 0)
            net = v.get("net_units")
            if n >= CURATE_MIN_N and net is not None and net <= CURATE_MAX_NET:
                out.add(fam)
        return out
    except Exception:
        return set()


def _shrink_prob(raw_prob, source, fair_american=None, market=None):
    """Two-stage calibration:

       1. If a market line is available (fair_american), shrink the raw
          model prob TOWARD the market-implied probability. The market is
          usually closer to truth than the model -- a 25-pp divergence
          almost always means the model is wrong.

       2. Otherwise (or as a final step), shrink toward a flat baseline.

       calibrated = w * raw + (1 - w) * anchor

    where anchor = market_implied (if available) else SHRINKAGE_BASELINE_PROB.
    """
    if raw_prob is None: return None
    # Self-learning weight overrides if data accumulated
    global _LEARNED_W_CACHE, _FAMILY_W_CACHE
    if _LEARNED_W_CACHE is None:
        _LEARNED_W_CACHE = _load_learned_weights()
    if _FAMILY_W_CACHE is None:
        _FAMILY_W_CACHE = _load_family_weights()
    # Prefer the per-source learned weight; if the source has no learned data
    # (true for every displayed candidate, which is tagged by market not by
    # ledger source), fall back to the per-market-family learned weight; only
    # then to the hardcoded prior. This is what lets the brain's settled-outcome
    # learning actually reach the displayed board.
    w_learned = _LEARNED_W_CACHE.get(source or "")
    if w_learned is None and market:
        w_learned = _FAMILY_W_CACHE.get(_market_family(market))
    w = w_learned if w_learned is not None else SOURCE_SHRINKAGE_W.get(source or "", DEFAULT_SHRINKAGE_W)
    market_p = _market_implied_prob(fair_american)
    if market_p is not None:
        # Market anchor available -- use it as the shrinkage target
        anchor = market_p
        # If model and market agree closely, keep more of model. If they
        # disagree wildly, lean more on market.
        gap = abs(raw_prob - market_p)
        if gap > 0.25:
            # Big disagreement -- model is probably wrong, lean to market
            w = w * 0.5
        elif gap > 0.15:
            w = w * 0.75
    else:
        anchor = SHRINKAGE_BASELINE_PROB
    return w * raw_prob + (1 - w) * anchor


def run() -> Dict[str, Any]:
    player_pot = _load(os.path.join(DATA_DIR, "slate_player_pot.json"))
    team_pot = _load(os.path.join(DATA_DIR, "slate_team_pot.json"))

    global _PROVEN_NEG_CACHE
    if _PROVEN_NEG_CACHE is None:
        _PROVEN_NEG_CACHE = _load_proven_negative_families()
    n_curated_out = 0

    candidates: List[Dict[str, Any]] = []
    for src, doc in (("player", player_pot), ("team", team_pot)):
        items = doc.get("all_picks") or doc.get("top_50") or doc.get("top_30") or []
        for x in items:
            raw_prob = x.get("prob")
            if not raw_prob: continue
            source = x.get("source")
            # CURATION: never publish a market family proven to lose money over a
            # real sample (e.g. to_hit_hr -92u, k_1plus -84u). ROI, not hit rate.
            if _market_family(x.get("market")) in _PROVEN_NEG_CACHE:
                n_curated_out += 1
                continue
            # Get explicit fair_american FIRST so shrinkage can anchor to market
            fair = x.get("fair_american")
            calibrated_prob = _shrink_prob(raw_prob, source, fair if isinstance(fair, (int, float)) else None, market=x.get("market"))
            if calibrated_prob is None or calibrated_prob < MIN_PROB: continue
            # Fall back to source-default fair odds if none provided
            if not isinstance(fair, (int, float)):
                fair = _fair_odds_for_source(source, src)
            dec_odds = _american_to_decimal(fair) or 1.91
            edge = _edge_pct(calibrated_prob, dec_odds)
            kelly = _kelly_fraction(calibrated_prob, dec_odds)
            if edge * 100 < MIN_EDGE_PCT: continue   # require material edge
            candidates.append({
                "src": src,
                "sport": x.get("sport"),
                "player_or_matchup": x.get("player") or x.get("matchup"),
                "team": x.get("team"),
                "market": x.get("market"),
                "market_family": _market_family(x.get("market")),
                "prob": round(calibrated_prob, 4),
                "raw_prob": round(raw_prob, 4),
                "shrinkage_w": round(SOURCE_SHRINKAGE_W.get(source or "", DEFAULT_SHRINKAGE_W), 2),
                "fair_american": fair,
                "decimal_odds": round(dec_odds, 3),
                "edge_pct": round(edge * 100, 1),
                "kelly_fraction": round(kelly, 4),
                "unit_size_quarter_kelly": round(kelly * 0.25, 3),
                "source": source,
            })

    # Rank by edge_pct desc (so highest-EV picks float to top)
    candidates.sort(key=lambda c: -c["edge_pct"])

    # ---- DEDUPE: collapse (player, market_family) so only top-edge variant
    #      of each (player, market_family) survives. Same player can still
    #      appear for DIFFERENT market families (HRR vs TB vs RBI).
    seen_key = set()
    deduped: List[Dict[str, Any]] = []
    for c in candidates:
        key = (c.get("sport"), c.get("player_or_matchup"), c.get("market_family"))
        if key in seen_key: continue
        seen_key.add(key)
        deduped.append(c)

    # ---- DIVERSITY FILTER for top_25:
    #      - max MAX_PICKS_PER_SPORT per sport
    #      - max MAX_PICKS_PER_PLAYER per (sport, player_or_matchup)
    sport_count: Dict[str, int] = {}
    player_count: Dict[Tuple[str, str], int] = {}
    top_25: List[Dict[str, Any]] = []
    for c in deduped:
        if len(top_25) >= 25: break
        sp = c.get("sport") or "?"
        pl = (sp, c.get("player_or_matchup") or "?")
        if sport_count.get(sp, 0) >= MAX_PICKS_PER_SPORT: continue
        if player_count.get(pl, 0) >= MAX_PICKS_PER_PLAYER: continue
        sport_count[sp] = sport_count.get(sp, 0) + 1
        player_count[pl] = player_count.get(pl, 0) + 1
        top_25.append(c)

    by_sport: Dict[str, int] = {}
    for c in deduped:
        by_sport[c["sport"]] = by_sport.get(c["sport"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_prob": MIN_PROB,
        "min_edge_pct": MIN_EDGE_PCT,
        "max_picks_per_sport": MAX_PICKS_PER_SPORT,
        "max_picks_per_player": MAX_PICKS_PER_PLAYER,
        "calibration": {
            "shrinkage_baseline_prob": SHRINKAGE_BASELINE_PROB,
            "default_shrinkage_w": DEFAULT_SHRINKAGE_W,
            "per_source_w": SOURCE_SHRINKAGE_W,
            "note": ("All displayed probabilities are post-shrinkage. Raw model "
                      "outputs are mixed with a 0.55 baseline weighted by source "
                      "reliability -- shrinkage_w in each pick = weight on raw."),
        },
        "n_total_plays": len(deduped),
        "n_raw_candidates": len(candidates),
        "n_curated_out_proven_neg": n_curated_out,
        "curated_excluded_families": sorted(_PROVEN_NEG_CACHE),
        "curation_note": ("Featured board excludes market families proven to lose "
                          "money over a real settled sample (ROI, not hit rate). "
                          f"{n_curated_out} candidate(s) filtered this run."),
        "by_sport": by_sport,
        "top_25": top_25,
        "top_5_by_kelly": sorted(deduped, key=lambda c: -c["kelly_fraction"])[:5],
        "top_5_by_prob": sorted(deduped, key=lambda c: -c["prob"])[:5],
        "all_plays": deduped[:200],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Today's top plays: {p['n_total_plays']} +EV picks deduped (from {p['n_raw_candidates']} raw) at >={p['min_prob']:.0%} prob")
    print(f"  By sport: {p['by_sport']}")
    print(f"\nTop 25 by edge_pct (diversity-capped):")
    for c in p["top_25"]:
        print(f"  [{c['sport']:7s}] {(c['player_or_matchup'] or '?')[:30]:30s} "
              f"{(c['market'] or '?')[:30]:30s} p={c['prob']*100:.0f}% edge={c['edge_pct']:+.1f}% "
              f"kelly={c['kelly_fraction']*100:.1f}% qK_unit={c['unit_size_quarter_kelly']:.2f}u")
    print(f"\nTop 5 by Kelly fraction (size up):")
    for c in p["top_5_by_kelly"]:
        print(f"  {(c['player_or_matchup'] or '?'):30s} {(c['market'] or '?'):30s} "
              f"kelly={c['kelly_fraction']*100:.1f}%  qK_unit={c['unit_size_quarter_kelly']:.2f}u")
