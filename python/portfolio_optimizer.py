"""
EdgeStat -- portfolio optimizer for tonight's slate.

Picks the optimal subset of tonight's qualifying bets to play, respecting:
  - Bankroll cap (total stake <= MAX_NIGHTLY_EXPOSURE_PCT * bankroll)
  - Per-bet Kelly cap
  - Max bets per game (correlation exposure cap; default 2 -- avoids
    over-weighting one game's outcome)
  - Min quality_score gate
  - Slate-confidence-tier sensitivity: in LOW slate confidence, the
    optimizer becomes more selective (higher quality threshold, smaller
    stakes)

Output: data/portfolio.json
  {
    "generated_at": "...",
    "bankroll": 1000, "kelly_fraction": 0.25, "slate_tier": "low",
    "n_picked": 8, "total_stake": 142,
    "stake_pct_of_bankroll": 14.2,
    "expected_pl": 12.5, "expected_roi_pct": 8.8,
    "by_game_exposure": {...},
    "picks": [
      {
        "rank": 1, "label": "...", "stake": 18.0, "ev": 2.1, ...
      }
    ],
    "skipped_reasons": {...}
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BEST_BETS_PATH = os.path.join(DATA_DIR, "best_bets.json")
SLATE_CONF_PATH = os.path.join(DATA_DIR, "slate_confidence.json")
RUNTIME_PATH = os.path.join(DATA_DIR, "runtime_config.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "portfolio.json")

BANKROLL_DEFAULT = 1000.0
KELLY_FRACTION_DEFAULT = 0.25
MAX_NIGHTLY_EXPOSURE_PCT = 0.25     # never risk >25% of bankroll on one night
MAX_PER_BET_PCT = 0.05               # Kelly cap per bet
MAX_BETS_PER_GAME = 2                # cap correlation exposure

# Quality thresholds by slate confidence tier
QUALITY_GATE = {"high": 65, "medium": 72, "low": 80}


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _kelly_stake(p: float, american: int, bankroll: float, frac: float) -> float:
    if p <= 0 or p >= 1:
        return 0
    b = (american / 100.0) if american >= 0 else (100.0 / abs(american))
    q = 1 - p
    f = max(0, (b * p - q) / b) * frac
    f = min(f, MAX_PER_BET_PCT)
    return round(bankroll * f, 2)


def _matchup_for_player(pid, matchups):
    if pid is None: return None
    for g in matchups.get("games") or []:
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                if b.get("id") == pid:
                    return g.get("matchup")
        for s in ("home_pitcher", "away_pitcher"):
            if (g.get(s) or {}).get("id") == pid:
                return g.get("matchup")
    return None


def run() -> Dict[str, Any]:
    bb = _load(BEST_BETS_PATH).get("bets") or []
    slate = _load(SLATE_CONF_PATH)
    rt = _load(RUNTIME_PATH)
    matchups = _load(MATCHUPS_PATH)

    bankroll = float(rt.get("bankroll.starting_units", BANKROLL_DEFAULT))
    kelly_frac = float(rt.get("plays.kelly_fraction", KELLY_FRACTION_DEFAULT))
    slate_tier = slate.get("tier") or "medium"
    quality_gate = QUALITY_GATE.get(slate_tier, 72)

    # Score-rank by quality (already done by best_bets) but apply gate
    # Allow DK / PP / NRFI flat plays. SGPs sized separately on /parlays.
    candidates = [b for b in bb if (b.get("quality_score") or 0) >= quality_gate
                                   and b.get("source") in ("DK", "PP", "NRFI")
                                   and b.get("model_prob") is not None]
    candidates.sort(key=lambda b: -b["quality_score"])

    picks: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {"low_quality": 0, "exposure_cap": 0, "game_cap": 0, "wrong_source": 0}
    skipped["low_quality"] = len(bb) - len(candidates)
    skipped["wrong_source"] = sum(1 for b in bb if b.get("source") not in ("DK", "PP", "NRFI"))

    game_exposure: Dict[str, int] = {}
    total_stake = 0.0
    max_total = bankroll * MAX_NIGHTLY_EXPOSURE_PCT
    for b in candidates:
        p = b["model_prob"]
        if p < 0.50 or p > 0.95:
            continue
        # Use book price -110 as conservative default for DK props.
        american = -110
        stake = _kelly_stake(p, american, bankroll, kelly_frac)
        if stake <= 0:
            continue
        # Game-exposure cap (correlation)
        matchup = _matchup_for_player(b.get("player_id"), matchups) or b.get("matchup") or "??"
        if game_exposure.get(matchup, 0) >= MAX_BETS_PER_GAME:
            skipped["game_cap"] += 1
            continue
        # Nightly exposure cap
        if total_stake + stake > max_total:
            skipped["exposure_cap"] += 1
            continue
        b_profit = stake * ((american / 100.0) if american >= 0 else (100.0 / abs(american)))
        ev = p * b_profit + (1 - p) * (-stake)
        picks.append({
            "rank": b.get("rank"),
            "label": b.get("label"),
            "player_id": b.get("player_id"),
            "player": b.get("player"),
            "market": b.get("market"),
            "line": b.get("line"),
            "play": b.get("play"),
            "source": b.get("source"),
            "model_prob": round(p, 4),
            "quality_score": b.get("quality_score"),
            "stake": stake,
            "max_profit": round(b_profit, 2),
            "ev": round(ev, 2),
            "matchup": matchup,
            "stars": b.get("stars"),
        })
        total_stake += stake
        game_exposure[matchup] = game_exposure.get(matchup, 0) + 1

    total_ev = sum(p["ev"] for p in picks)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "bankroll": bankroll,
        "kelly_fraction": kelly_frac,
        "slate_tier": slate_tier,
        "slate_score": slate.get("score"),
        "quality_gate": quality_gate,
        "n_candidates": len(bb),
        "n_picked": len(picks),
        "total_stake": round(total_stake, 2),
        "stake_pct_of_bankroll": round(total_stake / bankroll * 100, 2) if bankroll else 0,
        "max_nightly_exposure_pct": MAX_NIGHTLY_EXPOSURE_PCT * 100,
        "expected_pl": round(total_ev, 2),
        "expected_roi_pct": round(total_ev / total_stake * 100, 2) if total_stake else 0,
        "by_game_exposure": game_exposure,
        "picks": picks,
        "skipped_reasons": skipped,
        "rationale": (f"Slate tier {slate_tier} (score {slate.get('score')}/100) "
                       f"-> quality gate {quality_gate}. Capped per-game exposure at "
                       f"{MAX_BETS_PER_GAME}; total nightly stake capped at "
                       f"{int(MAX_NIGHTLY_EXPOSURE_PCT*100)}% of bankroll."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Slate: {p['slate_tier']} ({p['slate_score']}/100), quality gate {p['quality_gate']}")
    print(f"  Picks: {p['n_picked']} of {p['n_candidates']} candidates")
    print(f"  Stake: ${p['total_stake']} ({p['stake_pct_of_bankroll']}% of ${p['bankroll']})")
    print(f"  Expected: P&L ${p['expected_pl']}, ROI {p['expected_roi_pct']}%")
    print(f"  Skipped: {p['skipped_reasons']}")
