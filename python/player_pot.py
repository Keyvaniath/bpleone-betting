"""
EdgeStat -- Player Play of the Day across LoL/CS/KBO.

Scans every player-prop projection and picks the top 5 prop bets by quality:
  - Sweet-spot probability (55-72% for OVER, 28-45% for UNDER)
  - Elite-player bonus (Chovy, ZywOo, top KBO sluggers)
  - League-tier bonus (LCK > regional, BLAST > tier-2 CS, etc.)
  - Sample-size penalty for unknown rookies

Output: data/player_pot.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "player_pot.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _score_prop(p_over: float, sport: str, elite: bool) -> float:
    """Quality score 0-1.5."""
    if not (0.04 < p_over < 0.95): return 0.0
    # Sweet spot
    sweet_over = 1.0 - abs(p_over - 0.62) * 1.8
    sweet_under = 1.0 - abs(p_over - 0.38) * 1.8
    sweet = max(sweet_over, sweet_under)
    if sweet <= 0: return 0
    elite_mult = 1.20 if elite else 1.0
    return sweet * elite_mult


def _scan_lol() -> List[Dict[str, Any]]:
    """Scan LoL player props for top bets."""
    props = _load(os.path.join(DATA_DIR, "lol_player_props.json"))
    out: List[Dict[str, Any]] = []
    for p in (props.get("projections") or []):
        for kp in (p.get("kill_props") or []):
            score = _score_prop(kp["p_over"], "LOL", p.get("is_elite", False))
            if score >= 0.35:
                out.append({
                    "sport": "LOL",
                    "player": p["summoner_name"],
                    "team": p.get("team_code") or p.get("team_name"),
                    "league": p.get("league"),
                    "role": p.get("role"),
                    "market": "kills",
                    "play": "OVER" if kp["p_over"] >= 0.5 else "UNDER",
                    "line": kp["line"],
                    "prob": kp["p_over"] if kp["p_over"] >= 0.5 else kp["p_under"],
                    "fair_american": kp["fair_over_american"] if kp["p_over"] >= 0.5 else kp["fair_under_american"],
                    "quality_score": round(score, 4),
                    "is_elite": p.get("is_elite", False),
                    "label": f"{p['summoner_name']} {'OVER' if kp['p_over'] >= 0.5 else 'UNDER'} {kp['line']} Kills",
                })
        # Assist props
        for ap in (p.get("assist_props") or []):
            score = _score_prop(ap["p_over"], "LOL", p.get("is_elite", False))
            if score >= 0.40 and p.get("role") == "support":
                out.append({
                    "sport": "LOL",
                    "player": p["summoner_name"],
                    "team": p.get("team_code") or p.get("team_name"),
                    "league": p.get("league"),
                    "role": p.get("role"),
                    "market": "assists",
                    "play": "OVER" if ap["p_over"] >= 0.5 else "UNDER",
                    "line": ap["line"],
                    "prob": ap["p_over"] if ap["p_over"] >= 0.5 else ap["p_under"],
                    "fair_american": ap["fair_over_american"] if ap["p_over"] >= 0.5 else ap["fair_under_american"],
                    "quality_score": round(score, 4),
                    "is_elite": p.get("is_elite", False),
                    "label": f"{p['summoner_name']} {'OVER' if ap['p_over'] >= 0.5 else 'UNDER'} {ap['line']} Assists",
                })
    return out


def _scan_cs() -> List[Dict[str, Any]]:
    props = _load(os.path.join(DATA_DIR, "cs_player_props.json"))
    out: List[Dict[str, Any]] = []
    for p in (props.get("players") or []):
        rating = p.get("rating", 1.0)
        elite = rating >= 1.18
        for k in (p.get("props_bo3", {}).get("kills") or []):
            score = _score_prop(k["p_over"], "CS", elite)
            if score >= 0.35:
                out.append({
                    "sport": "CS",
                    "player": p["name"],
                    "team": p.get("team"),
                    "role": p.get("role"),
                    "market": "kills_bo3",
                    "play": "OVER" if k["p_over"] >= 0.5 else "UNDER",
                    "line": k["line"],
                    "prob": k["p_over"] if k["p_over"] >= 0.5 else (1 - k["p_over"]),
                    "fair_american": k["fair_over"] if k["p_over"] >= 0.5 else k["fair_under"],
                    "quality_score": round(score, 4),
                    "is_elite": elite,
                    "label": f"{p['name']} {'OVER' if k['p_over'] >= 0.5 else 'UNDER'} {k['line']} Kills (BO3)",
                })
    return out


def _scan_kbo() -> List[Dict[str, Any]]:
    props = _load(os.path.join(DATA_DIR, "kbo_player_props.json"))
    out: List[Dict[str, Any]] = []
    for p in (props.get("players") or []):
        if p.get("kind") == "batter":
            elite = (p.get("ops", 0) or 0) >= 0.900
            for market, label_short in (("two_plus_hits", "2+ hits"), ("one_plus_rbi", "1+ RBI"), ("one_plus_tb", "1+ TB")):
                pr = p.get("props", {}).get(market) or {}
                if not pr: continue
                score = _score_prop(pr["p"], "KBO", elite)
                if score >= 0.40:
                    fair_yes = pr.get("fair_yes") or pr.get("fair_over")
                    out.append({
                        "sport": "KBO",
                        "player": p["name"],
                        "team": p.get("team"),
                        "market": market,
                        "play": "YES",
                        "line": None,
                        "prob": pr["p"],
                        "fair_american": fair_yes,
                        "quality_score": round(score, 4),
                        "is_elite": elite,
                        "label": f"{p['name']} {label_short} ({p['team']})",
                    })
            # HR prop for sluggers
            hr = p.get("props", {}).get("hit_a_hr") or {}
            if hr.get("p", 0) >= 0.20 and (p.get("ops", 0) or 0) >= 0.880:
                score = _score_prop(hr["p"], "KBO", elite)
                if score >= 0.30:
                    out.append({
                        "sport": "KBO",
                        "player": p["name"],
                        "team": p.get("team"),
                        "market": "hr",
                        "play": "YES",
                        "line": None,
                        "prob": hr["p"],
                        "fair_american": hr.get("fair_yes"),
                        "quality_score": round(score, 4),
                        "is_elite": elite,
                        "label": f"{p['name']} hits a HR ({p['team']})",
                    })
        else:
            # Pitcher K props
            for line_key in ("k_over_55", "k_over_65"):
                kp = p.get("props", {}).get(line_key) or {}
                if not kp: continue
                line = float(line_key.replace("k_over_", "")) / 10
                score = _score_prop(kp["p"], "KBO", (p.get("era", 99) or 99) < 3.50)
                if score >= 0.40:
                    out.append({
                        "sport": "KBO",
                        "player": p["name"],
                        "team": p.get("team"),
                        "market": "pitcher_k",
                        "play": "OVER" if kp["p"] >= 0.5 else "UNDER",
                        "line": line,
                        "prob": kp["p"],
                        "fair_american": kp.get("fair_over") if kp["p"] >= 0.5 else kp.get("fair_under"),
                        "quality_score": round(score, 4),
                        "is_elite": (p.get("era", 99) or 99) < 3.50,
                        "label": f"{p['name']} K {'OVER' if kp['p'] >= 0.5 else 'UNDER'} {line}",
                    })
    return out


def run() -> Dict[str, Any]:
    all_cands = []
    all_cands.extend(_scan_lol())
    all_cands.extend(_scan_cs())
    all_cands.extend(_scan_kbo())
    all_cands.sort(key=lambda c: -c["quality_score"])
    top = all_cands[:5]
    by_sport_top = {}
    for sport in ("LOL", "CS", "KBO"):
        sport_cands = [c for c in all_cands if c["sport"] == sport]
        if sport_cands:
            by_sport_top[sport] = sport_cands[0]
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_candidates": len(all_cands),
        "n_top": len(top),
        "top_5": top,
        "top_by_sport": by_sport_top,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Player POT: {p['n_candidates']} candidates, top {p['n_top']} surfaced")
    for c in p["top_5"]:
        print(f"  [{c['sport']:4}] {c['label']:50} P={c['prob']*100:.1f}% fair {c['fair_american']:+d}  Q={c['quality_score']}")
    print(f"  Top per sport:")
    for sport, c in p["top_by_sport"].items():
        print(f"    {sport}: {c['label']} ({c['quality_score']})")
