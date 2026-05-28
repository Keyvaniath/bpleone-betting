"""
EdgeStat -- MLB pitcher "sharpest plays" board.

Capstone synthesizer for the pitcher stack. Joins three model feeds into
one conviction-ranked actionable board:

  - matchup projection  (proj_k / proj_er / p_qs / start tier)
  - K distribution bands (confident_line / coin_flip_line)
  - confluence score     (composite / dom & fade signals)

conviction (0-100) = confluence composite
  + start-tier bonus (ACE_SPOT +15, STRONG +8, FADE_RISK -15)
  + K-line bonus (confident 8+ +10, 7 +6, 6 +3)
  + dom_signals*2 - fade_signals*3

Tiers: PRIME_PLAY >=75, STRONG_PLAY >=62, LEAN >=50, PASS <50.
Emits a clean primary market per play + a separate fade list.

Output: data/mlb_pitcher_sharp_plays_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_sharp_plays_board.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _idx(data, key="pitcher"):
    return {_norm(r.get(key)): r
            for r in (data.get("rows") or []) if isinstance(r, dict)}


def run() -> Dict[str, Any]:
    proj = _load(os.path.join(DATA_DIR, "mlb_pitcher_matchup_projection.json"))
    kdist = _load(os.path.join(DATA_DIR, "mlb_pitcher_k_distribution_bands.json"))
    conf = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))

    proj_idx = _idx(proj)
    kdist_idx = _idx(kdist)
    conf_idx = _idx(conf)

    names = set(proj_idx) | set(kdist_idx) | set(conf_idx)

    plays: List[Dict[str, Any]] = []
    for name in names:
        p = proj_idx.get(name, {})
        k = kdist_idx.get(name, {})
        c = conf_idx.get(name, {})

        pitcher = p.get("pitcher") or k.get("pitcher") or c.get("pitcher") or name.title()
        matchup = p.get("matchup") or k.get("matchup") or c.get("matchup") or "?"
        team = p.get("team") or k.get("team") or c.get("team")

        composite = _safe(c.get("composite_score"))
        start_tier = p.get("tier") or "NEUTRAL"
        confident_line = int(_safe(k.get("confident_line")))
        coin_flip_line = int(_safe(k.get("coin_flip_line")))
        dom = _safe(c.get("dom_signals"))
        fade = _safe(c.get("fade_signals"))
        proj_er = _safe(p.get("proj_er"))
        p_qs = _safe(p.get("p_quality_start"))

        conviction = composite
        conviction += {"ACE_SPOT": 15, "STRONG": 8, "FADE_RISK": -15}.get(start_tier, 0)
        if confident_line >= 8: conviction += 10
        elif confident_line >= 7: conviction += 6
        elif confident_line >= 6: conviction += 3
        conviction += dom * 2 - fade * 3
        conviction = round(max(0.0, min(100.0, conviction)), 1)

        is_fade = start_tier == "FADE_RISK" or fade >= 2 or proj_er >= 4.2

        if is_fade:
            tier = "FADE"
        elif conviction >= 75:
            tier = "PRIME_PLAY"
        elif conviction >= 62:
            tier = "STRONG_PLAY"
        elif conviction >= 50:
            tier = "LEAN"
        else:
            tier = "PASS"

        # Primary actionable market
        if is_fade:
            primary = f"FADE — ER OVER / opp team total (proj ER {round(proj_er,1)})"
        elif confident_line >= 6:
            primary = f"K OVER {confident_line - 0.5} (confident)"
        elif coin_flip_line >= 6:
            primary = f"K OVER {coin_flip_line - 0.5} (lean)"
        elif p_qs >= 0.5:
            primary = "quality start YES"
        elif proj_er <= 3.0:
            # No K edge, but a sharp arm projects low ER -> ratio/length play
            primary = f"ER UNDER 3.5 / Outs OVER (proj ER {round(proj_er, 1)})"
        else:
            primary = "monitor / no standout edge"

        plays.append({
            "pitcher": pitcher,
            "team": team,
            "matchup": matchup,
            "conviction": conviction,
            "tier": tier,
            "start_tier": start_tier,
            "composite_score": round(composite, 1),
            "confident_K_line": confident_line,
            "coin_flip_K_line": coin_flip_line,
            "proj_er": round(proj_er, 2),
            "p_quality_start": round(p_qs, 3),
            "dom_signals": int(dom),
            "fade_signals": int(fade),
            "primary_market": primary,
        })

    plays.sort(key=lambda r: -r["conviction"])

    board = [r for r in plays if r["tier"] in ("PRIME_PLAY", "STRONG_PLAY", "LEAN")]
    fades = [r for r in plays if r["tier"] == "FADE"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(plays),
        "n_prime": sum(1 for r in plays if r["tier"] == "PRIME_PLAY"),
        "n_strong": sum(1 for r in plays if r["tier"] == "STRONG_PLAY"),
        "n_fade": len(fades),
        "method_note": "Capstone pitcher board. conviction = confluence "
                       "composite + start-tier bonus (ACE_SPOT+15/STRONG+8/"
                       "FADE_RISK-15) + K-line bonus (8+:+10,7:+6,6:+3) + "
                       "dom*2 - fade*3. Tiers PRIME>=75, STRONG>=62, LEAN>=50. "
                       "FADE if FADE_RISK start or 2+ fade signals or projER>=4.2.",
        "best_plays": board,
        "fades": fades,
        "rows": plays,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-sharp-pitchers] {o['n_pitchers']} starters ranked "
          f"({o['n_prime']} PRIME, {o['n_strong']} STRONG, {o['n_fade']} FADE) "
          f"-> {OUT}")
