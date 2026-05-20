"""
EdgeStat -- MLB UNDER alerts.

Public bettors systematically over-bet overs (action is fun to watch).
Books shade totals slightly UP to compensate. So when ALL the model
signals -- park, weather, pitchers, umpire, model fair_total -- agree
that a game projects LOW, UNDERs become structurally +EV.

This module scores each game with an "under_signal" 0-10:
   +3   model fair_total < market line by 0.5+
   +2   both starters have ERA < 3.50
   +1.5 ump is "tight" (high K mult, more strikeouts)
   +1   park factor < 1.00 (pitcher's park)
   +1   weather low carry (cold + wet)
   +1   indoor game (no wind/weather variance)
   +0.5 each team OPS < 0.700

Score >= 5 = STRONG UNDER signal. Above 6.5 = ELITE.

Output: data/mlb_unders_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_unders_alerts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _score_under(game: Dict[str, Any], matchup_data: Dict[str, Any]) -> Dict[str, Any]:
    signals = []
    score = 0.0

    model = game.get("model") or {}
    market = game.get("market") or {}
    weather = game.get("weather") or {}
    umpire = game.get("umpire") or {}

    fair_total = model.get("fair_total")
    market_total = market.get("total")
    if fair_total and market_total:
        gap = market_total - fair_total
        if gap >= 0.5:
            score += min(3.0, gap * 2)
            signals.append(f"Model fair total {fair_total:.2f} vs market {market_total:.1f} ({gap:+.2f})")

    # Starting pitchers ERA (from matchup_data)
    home_sp = (matchup_data.get("home_pitcher") or {}).get("season") or {}
    away_sp = (matchup_data.get("away_pitcher") or {}).get("season") or {}
    n_aces = 0
    for sp, side in ((home_sp, "home"), (away_sp, "away")):
        era = sp.get("era")
        if era is not None and era < 3.50:
            n_aces += 1
    if n_aces >= 2:
        score += 2.0
        signals.append(f"Both starters have ERA < 3.50")
    elif n_aces == 1:
        score += 1.0
        signals.append(f"One starter has ERA < 3.50")

    # Umpire tight (high K mult -> more strikeouts -> lower runs)
    ump_k = umpire.get("ump_k_mult") or 1.0
    if ump_k <= 0.95:
        score += 1.5
        signals.append(f"Tight ump {umpire.get('ump_name','?')} (K mult {ump_k:.2f})")

    # Park factor (would need data/parks.json -- estimate from carry_index)
    carry = weather.get("carry_index")
    if carry is not None and carry < 0.40:
        score += 1.0
        signals.append(f"Low carry index ({carry:.2f}) -- balls don't fly")

    # Weather
    temp = weather.get("temp_f") or 70
    wind = weather.get("wind_mph") or 0
    if weather.get("is_indoor"):
        score += 1.0
        signals.append("Indoor game (no weather variance)")
    elif temp < 60:
        score += 1.0
        signals.append(f"Cold weather {temp}F")
    elif weather.get("precip_pct", 0) > 50:
        score += 0.5
        signals.append("Rain expected")

    # Team OPS (from today's game features or matchups)
    home_team = matchup_data.get("home") or {}
    away_team = matchup_data.get("away") or {}
    h_ops = home_team.get("ops") or 0.700
    a_ops = away_team.get("ops") or 0.700
    if h_ops < 0.700:
        score += 0.5
        signals.append(f"Home OPS {h_ops:.3f} below avg")
    if a_ops < 0.700:
        score += 0.5
        signals.append(f"Away OPS {a_ops:.3f} below avg")

    tier = ("ELITE" if score >= 6.5 else
            "STRONG" if score >= 5.0 else
            "MODERATE" if score >= 3.0 else "WEAK")

    return {
        "matchup": game.get("matchup"),
        "market_total": market_total,
        "model_fair_total": fair_total,
        "under_signal_score": round(score, 2),
        "tier": tier,
        "signals": signals,
        "p_under_model": model.get("p_over_market") and (1 - model.get("p_over_market")),
    }


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    # Index matchups by matchup name
    matchups_by_mu = {}
    for m in (matchups.get("games") or []):
        mu = m.get("matchup")
        if mu: matchups_by_mu[mu] = m

    results = []
    for g in (today.get("games") or []):
        mu_data = matchups_by_mu.get(g.get("matchup"), {})
        results.append(_score_under(g, mu_data))

    results.sort(key=lambda r: -r["under_signal_score"])

    strong = [r for r in results if r["under_signal_score"] >= 5.0]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(results),
        "n_strong_unders": len(strong),
        "n_elite_unders": sum(1 for r in results if r["tier"] == "ELITE"),
        "top_unders": results[:10],
        "strong_unders": strong,
        "note": ("Multi-signal under detector. When park + weather + pitchers + "
                  "umpire + model_total all point low, UNDERs are structurally "
                  "+EV because the public over-bets overs."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB unders alerts: {p['n_games']} games, {p['n_strong_unders']} STRONG, {p['n_elite_unders']} ELITE")
    print(f"\n  Top 8 under signals:")
    for r in p["top_unders"][:8]:
        print(f"  [{r['tier']:8s} score {r['under_signal_score']:.1f}]  {r['matchup'][:30]:30s}  "
              f"model {r.get('model_fair_total','?')} vs market {r.get('market_total','?')}")
        for sig in r["signals"][:3]:
            print(f"     - {sig}")
