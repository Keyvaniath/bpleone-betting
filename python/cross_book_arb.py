"""
EdgeStat -- cross-book arbitrage / shading detector.

Joins DK props (props.json) with PrizePicks props (pickem.json) on
(player_id, market) and flags every prop where:
  - PP line is softer than DK line on OUR favored side, AND
  - Combined implied probabilities sum to < 1 (true arb), OR
  - PP line offers a cents-better implied price

True arb in MLB props is rare (PP isn't really 2-sided), but the
shading mismatch lets the operator route bets to the cheaper book.

Output: data/cross_book_arb.json
  {
    "generated_at": "...",
    "n_arb": 2,            # true arbs (combined implied < 1)
    "n_shaded": 24,        # cases where PP softer than DK
    "alerts": [
      { player, market, dk_line, pp_line, dk_play, pp_play,
        better_book, juice_delta_cents, ... }
    ]
  }
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
OUT_PATH = os.path.join(DATA_DIR, "cross_book_arb.json")

PP_AMERICAN = -119   # PP standard price is ~ -119 (1.91 decimal flex pay)


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _implied(a):
    if a is None: return None
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def run() -> Dict[str, Any]:
    dk_by_pid_mkt: Dict[str, Dict[str, Any]] = {}
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        if not p.get("player_id") or not p.get("market"):
            continue
        dk_by_pid_mkt[f"{p['player_id']}|{p['market']}"] = p

    alerts: List[Dict[str, Any]] = []
    n_true_arb = 0
    for p in (_load(PICKEM_PATH).get("props") or []):
        pid, market = p.get("player_id"), p.get("market")
        if not pid or not market:
            continue
        dk = dk_by_pid_mkt.get(f"{pid}|{market}")
        if not dk:
            continue
        dk_line = dk.get("line")
        pp_line = p.get("pp_line")
        if dk_line is None or pp_line is None:
            continue
        # Model says which side is the play
        play = "OVER" if (p.get("model_prob_over") or 0) >= (p.get("model_prob_under") or 0) else "UNDER"
        line_diff = pp_line - dk_line
        # PP softer = PP line is lower for OVER (easier to clear), higher for UNDER
        pp_softer = (line_diff < 0 and play == "OVER") or (line_diff > 0 and play == "UNDER")
        # Juice diff (cents)
        dk_p = dk.get("dk_over") if play == "OVER" else dk.get("dk_under")
        dk_implied = _implied(dk_p)
        pp_implied = _implied(PP_AMERICAN)
        true_arb = (dk_implied is not None and pp_implied is not None
                     and (1 - dk_implied) + (1 - pp_implied) > 1)
        # ^ rough: if we could bet the OPPOSITE side at each book and combined < 1, arb
        if not pp_softer and not true_arb:
            continue
        if true_arb:
            n_true_arb += 1
        alerts.append({
            "player": p.get("player"),
            "player_id": pid,
            "market": market,
            "dk_line": dk_line,
            "pp_line": pp_line,
            "line_delta": round(pp_line - dk_line, 1),
            "play": play,
            "dk_price": dk_p,
            "pp_price_assumed": PP_AMERICAN,
            "dk_implied": round(dk_implied, 4) if dk_implied is not None else None,
            "pp_implied": round(pp_implied, 4) if pp_implied is not None else None,
            "better_book": "PrizePicks" if pp_softer else "DraftKings",
            "true_arb": true_arb,
            "model_prob": p.get("model_prob_over") if play == "OVER" else p.get("model_prob_under"),
        })
    alerts.sort(key=lambda a: (0 if a["true_arb"] else 1, -abs(a["line_delta"])))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_dk_props": len(dk_by_pid_mkt),
        "n_alerts": len(alerts),
        "n_true_arb": n_true_arb,
        "n_shaded": len(alerts) - n_true_arb,
        "alerts": alerts[:50],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Alerts: {p['n_alerts']}  ({p['n_true_arb']} true arbs, {p['n_shaded']} shaded)")
    for a in p["alerts"][:5]:
        print(f"    {a['player']:25} {a['market']:25} DK {a['dk_line']:>5}  PP {a['pp_line']:>5}  -> bet {a['better_book']}")
