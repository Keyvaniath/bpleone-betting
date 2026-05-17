"""
EdgeStat -- composite Best Bets digest.

Single ranked list across every market we score (DK props, PrizePicks
softer lines, game lines, NRFI, top SGPs). For each candidate, computes
a composite "bet quality" score that incorporates:

  - Raw edge_pct
  - Model probability
  - Per-player trust tier (from player_breakdowns)
  - Lineup confirmation status
  - Weather lean alignment (game's HR mult vs prop direction)
  - Pitcher fatigue alignment (for K props vs SP fatigue grade)

Output: data/best_bets.json
  {
    "generated_at": "...",
    "n_bets": 25,
    "bets": [
      {
        "rank": 1,
        "label": "...",                # plain-English description
        "player": "...", "player_id": ..., "team": "...",
        "market": "...", "line": ..., "play": "OVER" | "UNDER",
        "source": "DK" | "PP" | "game" | "NRFI" | "SGP",
        "model_prob": 0.62, "edge_pct": 5.4,
        "quality_score": 87,            # 0-100 composite
        "stars": 4,
        "factors": [...],              # contributing factor notes
        "risks": [...],                # caveats
        "url_anchor": "player.html?id=..." | "nrfi.html" | "parlays.html"
      }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
NRFI_PATH = os.path.join(DATA_DIR, "nrfi.json")
SGP_PATH = os.path.join(DATA_DIR, "sgps.json")
BREAKDOWNS_PATH = os.path.join(DATA_DIR, "player_breakdowns.json")
WX_PATH = os.path.join(DATA_DIR, "weather_conditional.json")
FATIGUE_PATH = os.path.join(DATA_DIR, "pitcher_fatigue.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "best_bets.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _bd_index() -> Dict[str, Any]:
    return (_load(BREAKDOWNS_PATH).get("by_id") or {})


def _fatigue_for_pitcher(name: Optional[str], fatigue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    for r in fatigue.get("by_pitcher") or []:
        if r.get("name") == name:
            return r
    return None


def _weather_for_matchup(matchup: Optional[str], wx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not matchup:
        return None
    for g in wx.get("by_game") or []:
        if g.get("matchup") == matchup:
            return g
    return None


def _player_team_to_matchup(pid: int, matchups: Dict[str, Any]) -> Optional[str]:
    for g in matchups.get("games") or []:
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                if b.get("id") == pid:
                    return g.get("matchup")
        for s in ("home_pitcher", "away_pitcher"):
            if (g.get(s) or {}).get("id") == pid:
                return g.get("matchup")
    return None


def score_prop(p: Dict[str, Any], bd: Dict[str, Any], wx: Dict[str, Any],
                fatigue: Dict[str, Any], matchups: Dict[str, Any]) -> Dict[str, Any]:
    """Return a {quality_score, factors[], risks[]} for one prop."""
    factors: List[str] = []
    risks: List[str] = []
    score = 50  # baseline

    edge = p.get("best_edge_pct") or p.get("edge_pct") or 0
    prob = p.get("model_prob_over") or 0
    play = (p.get("play") or "").upper()

    # Edge: cap pre-cal noise (>15%)
    if edge and edge > 15:
        score -= 10
        risks.append(f"Pre-cal edge {edge:.1f}% (>15% is noisy)")
    elif edge >= 5:
        score += int(min(edge - 5, 8))   # +8 max for edge 13%
        factors.append(f"Strong edge +{edge:.1f}%")
    elif edge >= 3:
        score += 4
        factors.append(f"Edge +{edge:.1f}%")
    elif edge < 1.5:
        score -= 6
        risks.append(f"Thin edge {edge:.1f}%")

    # Model confidence
    if play == "OVER":
        pp = prob
    elif play == "UNDER":
        pp = 1 - prob if prob else 0
    else:
        pp = 0
    if pp >= 0.70:
        score += 8
        factors.append(f"High model confidence ({pp*100:.0f}%)")
    elif pp >= 0.60:
        score += 4
    elif pp < 0.55:
        score -= 4

    # Player trust tier
    pid = p.get("player_id")
    bdp = bd.get(str(pid)) or {}
    acc = bdp.get("model_accuracy") or {}
    tier = acc.get("trust_tier")
    if tier == "trusted" and acc.get("n_props", 0) >= 20:
        score += 6
        factors.append(f"Player trust: TRUSTED ({int((acc.get('hit_rate') or 0)*100)}% on {acc.get('n_props')} props)")
    elif tier == "untrusted":
        score -= 10
        risks.append(f"Player trust: UNTRUSTED — model has been wrong on this player")

    # Lineup status
    ls = p.get("lineup_status")
    if ls == "confirmed":
        score += 4
        factors.append("Lineup CONFIRMED")
    elif ls == "scratched":
        score -= 50
        risks.append("PLAYER SCRATCHED — skip")
    elif ls == "pending":
        risks.append("Lineup pending — ~10% scratch risk")

    # Hot/cold trend
    hc = ((bdp.get("form") or {}).get("hot_cold") or "")
    if "heating up" in hc:
        score += 3
        factors.append("Heating up (recent OPS above season)")
    elif "cooling" in hc:
        score -= 3
        risks.append("Cooling off (recent OPS below season)")

    # Weather alignment for HR / TB
    market = p.get("market") or ""
    matchup = _player_team_to_matchup(pid, matchups)
    wg = _weather_for_matchup(matchup, wx)
    if wg and market in ("batter_home_runs", "batter_total_bases", "batter_hits"):
        mult = wg.get("hr_mult_delta_pct", 0)
        lean = wg.get("lean")
        if mult >= 6 and play == "OVER":
            score += 4
            factors.append(f"Weather: {wg.get('reason')} aligns with OVER")
        elif mult <= -6 and play == "UNDER":
            score += 4
            factors.append(f"Weather: {wg.get('reason')} aligns with UNDER")
        elif (mult >= 6 and play == "UNDER") or (mult <= -6 and play == "OVER"):
            score -= 4
            risks.append(f"Weather: {wg.get('reason')} pushes against play")

    # Pitcher fatigue for K props
    if market == "pitcher_strikeouts":
        f = _fatigue_for_pitcher(p.get("player"), fatigue)
        if f:
            risk = f.get("early_hook_risk")
            if risk == "high" and play == "OVER":
                score -= 8
                risks.append(f"SP fatigue HIGH ({f.get('fatigue_note')}) -- against OVER K")
            elif risk == "low" and play == "OVER":
                score += 3
                factors.append(f"SP fatigue grade {f.get('fatigue_grade')} -- fresh")

    score = max(0, min(100, score))
    stars = 5 if score >= 88 else 4 if score >= 76 else 3 if score >= 62 else 2 if score >= 48 else 1
    return {"quality_score": score, "stars": stars, "factors": factors, "risks": risks}


def run() -> Dict[str, Any]:
    bd = _bd_index()
    wx = _load(WX_PATH)
    fatigue = _load(FATIGUE_PATH)
    matchups = _load(MATCHUPS_PATH)

    candidates: List[Dict[str, Any]] = []

    # DK props
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        if not p.get("play") or p.get("play") == "SKIP":
            continue
        sc = score_prop(p, bd, wx, fatigue, matchups)
        candidates.append({
            "source": "DK",
            "label": f"{p.get('player')} {p.get('play')} {p.get('line')} {(p.get('market') or '').replace('_',' ')}",
            "player": p.get("player"), "player_id": p.get("player_id"),
            "team": p.get("team"),
            "market": p.get("market"), "line": p.get("line"),
            "play": p.get("play"),
            "model_prob": p.get("model_prob_over"),
            "edge_pct": p.get("best_edge_pct") or p.get("edge_pct"),
            "url_anchor": f"player.html?id={p.get('player_id')}",
            **sc,
        })

    # PrizePicks softer lines
    for p in (_load(PICKEM_PATH).get("props") or []):
        if not p.get("pp_advantage"):
            continue
        prob = max(p.get("model_prob_over", 0) or 0, p.get("model_prob_under", 0) or 0)
        play = "OVER" if (p.get("model_prob_over") or 0) >= (p.get("model_prob_under") or 0) else "UNDER"
        if prob < 0.55:
            continue
        pp_shim = {**p, "line": p.get("pp_line"), "play": play, "best_edge_pct": p.get("edge_pct")}
        sc = score_prop(pp_shim, bd, wx, fatigue, matchups)
        # PP gets a small bonus for being softer than DK
        sc["quality_score"] = min(100, sc["quality_score"] + 3)
        sc["factors"].append("PP line softer than DK")
        candidates.append({
            "source": "PP",
            "label": f"{p.get('player')} {play} {p.get('pp_line')} {(p.get('market') or '').replace('_',' ')} (PP softer)",
            "player": p.get("player"), "player_id": p.get("player_id"),
            "team": p.get("team"),
            "market": p.get("market"), "line": p.get("pp_line"),
            "play": play,
            "model_prob": prob,
            "edge_pct": p.get("edge_pct"),
            "url_anchor": f"player.html?id={p.get('player_id')}",
            **sc,
        })

    # NRFI/YRFI leans
    nrfi = _load(NRFI_PATH)
    baseline = nrfi.get("league_nrfi_baseline") or 0.58
    for g in nrfi.get("games") or []:
        edge_nrfi = (g.get("p_nrfi") or 0) - baseline
        edge_yrfi = (g.get("p_yrfi") or 0) - (1 - baseline)
        if edge_yrfi > 0.06:
            candidates.append({
                "source": "NRFI",
                "label": f"{g.get('matchup')} YRFI (1st-inning OVER 0.5)",
                "team": None, "player": None, "player_id": None,
                "market": "first_inning", "line": 0.5, "play": "OVER",
                "model_prob": g.get("p_yrfi"),
                "edge_pct": round(edge_yrfi * 100, 2),
                "url_anchor": "nrfi.html",
                "quality_score": 60 + min(20, int(edge_yrfi * 100)),
                "stars": 3 if edge_yrfi < 0.10 else 4,
                "factors": [f"P(YRFI) {(g.get('p_yrfi') or 0)*100:.1f}% vs baseline {(1-baseline)*100:.1f}%"],
                "risks": ["NRFI market is tight, sharp"],
            })
        elif edge_nrfi > 0.06:
            candidates.append({
                "source": "NRFI",
                "label": f"{g.get('matchup')} NRFI (no run 1st inning)",
                "team": None, "player": None, "player_id": None,
                "market": "first_inning", "line": 0.5, "play": "UNDER",
                "model_prob": g.get("p_nrfi"),
                "edge_pct": round(edge_nrfi * 100, 2),
                "url_anchor": "nrfi.html",
                "quality_score": 60 + min(20, int(edge_nrfi * 100)),
                "stars": 3 if edge_nrfi < 0.10 else 4,
                "factors": [f"P(NRFI) {(g.get('p_nrfi') or 0)*100:.1f}% vs baseline {baseline*100:.1f}%"],
                "risks": ["NRFI market is tight, sharp"],
            })

    # Top SGP per game
    sgps = _load(SGP_PATH).get("by_game") or []
    for sg in sgps[:6]:
        top = (sg.get("suggestions") or [None])[0]
        if not top:
            continue
        candidates.append({
            "source": "SGP",
            "label": f"{sg.get('matchup')} {top.get('n_legs')}-leg SGP @ {top.get('fair_american'):+d}",
            "team": None, "player": None, "player_id": None,
            "market": "sgp", "line": top.get("fair_decimal"),
            "play": f"{top.get('n_legs')}-leg",
            "model_prob": top.get("joint_prob"),
            "edge_pct": top.get("ev_pct"),
            "url_anchor": "parlays.html",
            "quality_score": min(100, 55 + int(top.get("ev_pct", 0) * 0.4)),
            "stars": 5 if top.get("ev_pct", 0) >= 40 else 4 if top.get("ev_pct", 0) >= 20 else 3,
            "factors": [f"Joint prob {top.get('joint_prob'):.3f} (correlation boost {top.get('correlation_boost'):+.3f})"] +
                        [f"Leg: {l.get('label')}" for l in (top.get("legs") or [])[:4]],
            "risks": ["SGPs are correlated -- one bad leg sinks the parlay"],
        })

    # Golf Play of the Tournament + runners-up (cross-sport injection)
    gb = _load(os.path.join(DATA_DIR, "golf_bestbet.json"))
    state = _load(os.path.join(DATA_DIR, "golf_state.json"))
    t = state.get("active_tournament") or {}
    if gb.get("top_bet") and not t.get("is_complete"):
        golf_cands = [gb["top_bet"]] + (gb.get("runners_up") or [])[:3]
        for gc in golf_cands:
            conf = gc.get("confidence", "MED")
            q = 78 if conf == "HIGH" else 68 if conf == "MED" else 58
            stars = 5 if conf == "HIGH" else 4 if conf == "MED" else 3
            candidates.append({
                "source": "GOLF",
                "label": f"⛳ {gc.get('player')}{' vs ' + gc.get('opponent') if gc.get('opponent') else ''} {gc.get('type')} @ {gc.get('fair_american','?')} ({t.get('name','PGA')})",
                "team": None, "player": gc.get("player"), "player_id": None,
                "market": f"golf_{(gc.get('type') or '').lower()}", "line": gc.get("fair_american"),
                "play": gc.get("type"),
                "model_prob": gc.get("model_prob"),
                "edge_pct": None,
                "url_anchor": "golf.html",
                "quality_score": q,
                "stars": stars,
                "factors": [gc.get("reasoning", "")],
                "risks": ["Golf outright variance is high; smaller stake recommended"],
            })

    # Sort and rank
    candidates.sort(key=lambda c: -c.get("quality_score", 0))
    for i, c in enumerate(candidates[:50]):
        c["rank"] = i + 1
    top = candidates[:50]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_bets": len(top),
        "total_candidates": len(candidates),
        "by_source": {s: sum(1 for c in top if c.get("source") == s)
                       for s in ("DK", "PP", "NRFI", "SGP", "GOLF")},
        "bets": top,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: top {p['n_bets']} of {p['total_candidates']} candidates")
    print(f"  by source: {p['by_source']}")
    print(f"  top 5:")
    for b in p["bets"][:5]:
        print(f"    [{b['rank']}] ({b['quality_score']}/100, {b['stars']} stars) {b['label']}")
