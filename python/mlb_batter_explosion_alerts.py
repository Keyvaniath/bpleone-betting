"""
EdgeStat -- MLB batter explosion alerts.

Per-batter multi-prop OVER alignment. Counterpart to nba_player_ceiling_stack
but for MLB hitters. Surfaces batters with 3+ aligned positive signals:
  - HR_YES (p_hr >= 18%)
  - 2PLUS_HITS (p_2plus >= 40%)
  - 1PLUS_RBI (p_rbi >= 50%)
  - 1PLUS_HIT (p_hit >= 75%)
  - 3PLUS_TB (p_tb3 >= 22%)
  - TB_OVER (total bases OVER lean)
  - DOUBLE_LEAN (XBH OVER)
  - WALK_LEAN (1+ walk YES >= 45%)

CEILING_ELITE = 5+ signals; STRONG = 3-4. DFS / parlay anchor candidate.

Output: data/mlb_batter_explosion_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_explosion_alerts.json")


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


def _is_over(ec: str) -> bool:
    return "OVER" in (ec or "").upper()


def run() -> Dict[str, Any]:
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    hits_2 = _load(os.path.join(DATA_DIR, "mlb_batter_2plus_hits_props.json"))
    rbi = _load(os.path.join(DATA_DIR, "mlb_batter_rbi_props.json"))
    hit_yn = _load(os.path.join(DATA_DIR, "mlb_to_record_hit_yn.json"))
    tb_3 = _load(os.path.join(DATA_DIR, "mlb_batter_3plus_tb_props.json"))
    tb = _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json"))
    doubles = _load(os.path.join(DATA_DIR, "mlb_doubles_props.json"))
    walks = _load(os.path.join(DATA_DIR, "mlb_batter_walks_props.json"))

    batters: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return batters.setdefault(key, {
            "batter": name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "signals": {},
            "scores": {},
        })

    def _ingest_threshold(src: Dict[str, Any], signal_key: str,
                          p_field: str, threshold: float,
                          name_field: str = "batter") -> None:
        seen: set = set()
        for k in ("rows", "strong_edges", "top_25_by_p_2plus",
                  "top_25_by_p_rbi", "top_25_by_p_hr", "top_25_by_p_hit",
                  "top_25_by_p_tb3"):
            for r in (src.get(k) or []):
                if not isinstance(r, dict): continue
                name = r.get(name_field) or r.get("batter") or r.get("player") or ""
                key = _norm(name)
                if key in seen: continue
                seen.add(key)
                entry = _entry(name, r)
                if not entry: continue
                p_val = _safe(r.get(p_field) or r.get("p"))
                entry["signals"][signal_key] = 1 if p_val >= threshold else 0
                entry["scores"][signal_key] = round(p_val, 3)

    def _ingest_over(src: Dict[str, Any], signal_key: str,
                     name_field: str = "batter") -> None:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            name = r.get(name_field) or r.get("batter") or r.get("player") or ""
            entry = _entry(name, r)
            if not entry: continue
            entry["signals"][signal_key] = 1 if _is_over(r.get("edge_class") or "") else 0

    _ingest_threshold(hr, "HR_YES", "p_hr", 0.18)
    _ingest_threshold(hits_2, "2PLUS_HITS", "p_2plus", 0.40)
    _ingest_threshold(rbi, "1PLUS_RBI", "p_rbi", 0.50)
    _ingest_threshold(hit_yn, "1PLUS_HIT", "p_hit", 0.75)
    _ingest_threshold(tb_3, "3PLUS_TB", "p_tb3", 0.22)
    _ingest_over(tb, "TB_OVER")
    _ingest_over(doubles, "DOUBLE_LEAN")
    _ingest_threshold(walks, "WALK_LEAN", "p_1plus_walk", 0.45)

    alerts: List[Dict[str, Any]] = []
    for key, entry in batters.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        if n >= 5:
            tier = "CEILING_ELITE"
        elif n >= 4:
            tier = "CEILING_STRONG"
        else:
            tier = "CEILING_LEAN"
        alerts.append({
            "batter": entry["batter"],
            "team": entry["team"],
            "matchup": entry["matchup"],
            "n_aligned_overs": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_aligned_overs"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "CEILING_ELITE"),
        "n_strong": sum(1 for a in alerts if a["tier"] == "CEILING_STRONG"),
        "method_note": "MLB batter explosion alerts. Counterpart to NBA/NHL "
                       "ceiling stacks but for MLB hitters. 3+ aligned signals "
                       "across HR_YES, 2PLUS_HITS, 1PLUS_RBI, 1PLUS_HIT, "
                       "3PLUS_TB, TB_OVER, DOUBLE_LEAN, WALK_LEAN. "
                       "CEILING_ELITE = 5+; STRONG = 4; LEAN = 3.",
        "alerts": alerts,
        "elite_ceilings": [a for a in alerts if a["tier"] == "CEILING_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-batter-explosion] {o['n_alerts']} alerts ({o['n_elite']} ELITE, "
          f"{o['n_strong']} STRONG) -> {OUT}")
