"""
EdgeStat -- Cross-signal convergence detector.

Looks at every game on tonight's slate and stacks the signals that hit it:
  - pre-game alert (form-aligned)
  - heat/cold alert (team trending)
  - anomaly alert (residual/streak mismatch)
  - pitcher matchup edge (K or ER play)
  - ATS signal (model underrates/overrates a team in the game)

Games where 3+ signals stack are the highest-conviction plays of the day:
"everything aligned" picks.

Output: data/convergence_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "convergence_alerts.json")


def _load(p):
    fp = os.path.join(DATA_DIR, p)
    if not os.path.exists(fp): return {}
    try:
        with open(fp) as f: return json.load(f)
    except Exception: return {}


def _flatten(v):
    """Coerce dict-or-str team field to lowercased str."""
    if isinstance(v, str): return v.lower()
    if isinstance(v, dict):
        for k in ("name", "abbr", "team", "team_name", "displayName"):
            if v.get(k): return str(v[k]).lower()
    return None


def _team_keys(g):
    """Build keys this game would match against (case-insensitive)."""
    keys = set()
    for fld in ("home_team", "away_team", "home", "away"):
        s = _flatten(g.get(fld))
        if s: keys.add(s)
    return keys


def _alert_targets_team(alert, all_team_keys):
    """Does this alert mention any team in this game?"""
    blob = json.dumps(alert).lower()
    return any(k in blob for k in all_team_keys)


def run() -> Dict[str, Any]:
    today = _load("today.json")
    matchups = _load("matchups.json")
    pregame = _load("pregame_alerts.json")
    heat_cold = _load("heat_cold_alerts.json")
    anomalies = _load("anomaly_alerts.json")
    pitcher_matchup = _load("mlb_pitcher_matchup.json")

    # ATS signals as flat name list
    ats_signals: Dict[str, List[Dict[str, Any]]] = {}
    for sport in ("nba", "nhl", "wnba", "mls", "epl", "mlb", "cws"):
        ats = _load(f"ats_tracker_{sport}.json")
        for tid, t in (ats.get("teams") or {}).items():
            name = (t.get("name") or "").lower()
            if not name: continue
            sig = t.get("signal") or "ALIGNED"
            if sig in ("MODEL_UNDERRATES", "MODEL_OVERRATES"):
                ats_signals.setdefault(name, []).append({
                    "sport": sport, "team": t.get("name"),
                    "signal": sig, "cover_pct": t.get("cover_pct"),
                })

    games: List[Dict[str, Any]] = []
    games.extend(matchups.get("games") or [])
    games.extend(today.get("games") or [])
    # Add other-sport scoreboards (each emits state -> games)
    for sport_state in ("nba_state.json", "nhl_state.json", "wnba_state.json",
                          "mls_state.json", "epl_state.json"):
        s = _load(sport_state)
        for g in (s.get("games") or []):
            # Normalize keys
            g.setdefault("home_team", g.get("home"))
            g.setdefault("away_team", g.get("away"))
            games.append(g)

    pre_alerts = pregame.get("alerts") or []
    hc_alerts = heat_cold.get("alerts") or []
    anom_alerts = anomalies.get("alerts") or []
    pitcher_games = {(m.get("matchup") or "").lower(): m for m in (pitcher_matchup.get("matchups") or [])}

    convergence: List[Dict[str, Any]] = []
    seen = set()
    for g in games:
        keys = _team_keys(g)
        if not keys: continue
        # Dedupe by sorted team-pair
        signature = tuple(sorted(keys))
        if signature in seen: continue
        seen.add(signature)

        signals: List[Dict[str, Any]] = []
        # Pre-game alerts (schema: confidence, side, team, p_pick_side, fair_american, form_aligned)
        for a in pre_alerts:
            if _alert_targets_team(a, keys):
                detail_parts = []
                if a.get("side") and a.get("team"):
                    detail_parts.append(f"{a['side']} {a['team']}")
                if a.get("p_pick_side"):
                    detail_parts.append(f"p={a['p_pick_side']*100:.0f}%")
                if a.get("fair_american") is not None:
                    detail_parts.append(f"fair {a['fair_american']:+d}")
                if a.get("form_aligned"): detail_parts.append("form-aligned")
                signals.append({"type": "PREGAME",
                                 "level": a.get("confidence", "MED"),
                                 "detail": " | ".join(detail_parts) or a.get("team", "?")})
        # Heat/cold (schema: type, sport, team, detail)
        for a in hc_alerts:
            if _alert_targets_team(a, keys):
                signals.append({"type": "HEAT_COLD", "level": "MED",
                                 "detail": f"{a.get('type','?')}: {a.get('team','?')} -- {a.get('detail','?')}"})
        # Anomalies (schema: type, sport, team, matchup, avg_residual, detail)
        for a in anom_alerts:
            if _alert_targets_team(a, keys):
                sev = "HIGH" if abs(a.get("avg_residual", 0) or 0) >= 10 else "MED"
                signals.append({"type": "ANOMALY", "level": sev,
                                 "detail": f"{a.get('type','?')}: {a.get('team','?')} residual={a.get('avg_residual','?')}"})
        # ATS
        for k in keys:
            for sig in ats_signals.get(k, []):
                signals.append({"type": "ATS", "level": "MED",
                                "detail": f"{sig['team']} {sig['signal']} ({sig.get('cover_pct',0)*100:.0f}% cover)"})
        # Pitcher matchup
        for mkey, m in pitcher_games.items():
            if any(k in mkey for k in keys):
                best = m.get("best_k_play")
                if best and best.get("p_over", 0) >= 0.60:
                    signals.append({"type": "PITCHER_K", "level": "HIGH",
                                    "detail": f"{best['pitcher']} OVER {best['line']} K ({best['p_over']*100:.0f}%) fair {best.get('fair_over','?')}"})
                for e in (m.get("er_under_2_5_candidates") or [])[:1]:
                    signals.append({"type": "PITCHER_ER", "level": "HIGH",
                                    "detail": f"{e['pitcher']} UNDER 2.5 ER ({e['p_under_2_5_er']*100:.0f}%) fair {e.get('fair_under','?')}"})

        if len(signals) >= 2:  # 2+ signals = worth surfacing, 3+ = high conviction
            tier = "ELITE" if len(signals) >= 4 else "HIGH" if len(signals) >= 3 else "MED"
            home_str = _flatten(g.get("home_team")) or _flatten(g.get("home")) or "?"
            away_str = _flatten(g.get("away_team")) or _flatten(g.get("away")) or "?"
            mu = g.get("matchup")
            if not mu or not isinstance(mu, str):
                mu = f"{away_str} @ {home_str}".upper()
            convergence.append({
                "matchup": mu,
                "home_team": home_str,
                "away_team": away_str,
                "sport": (g.get("sport") or "MLB").upper() if isinstance(g.get("sport"), str) else "MLB",
                "n_signals": len(signals),
                "tier": tier,
                "signals": signals,
            })

    convergence.sort(key=lambda c: -c["n_signals"])
    by_tier = {}
    for c in convergence:
        by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games_with_2plus_signals": len(convergence),
        "n_elite": by_tier.get("ELITE", 0),
        "n_high": by_tier.get("HIGH", 0),
        "n_med": by_tier.get("MED", 0),
        "convergence": convergence,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Convergence: {p['n_games_with_2plus_signals']} games with 2+ signals "
          f"(ELITE {p['n_elite']} / HIGH {p['n_high']} / MED {p['n_med']})")
    for c in p["convergence"][:5]:
        print(f"  [{c['tier']}] {c['matchup']:35} | {c['n_signals']} signals")
        for s in c["signals"][:3]:
            print(f"    {s['type']:12} {s['level']:5} {s['detail'][:80]}")
