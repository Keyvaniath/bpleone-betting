"""
EdgeStat -- golf region/nationality matchup props.

For each region group, projects:
  - Top finisher in group (highest p_top5 / p_top10 weighted sum)
  - Top USA / Top European / Top Asian / Top SA / Top Other markets
  - Head-to-head pair within region

Uses golf_props.json (p_win + p_top5 + p_top10 + p_top20 per player + country).

Output: data/golf_region_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_region_props.json")

# Country → region mapping
REGION_OF = {
    "USA": "USA",
    "Canada": "Americas (non-USA)",
    "Mexico": "Americas (non-USA)",
    "Argentina": "Americas (non-USA)",
    "Colombia": "Americas (non-USA)",
    "Venezuela": "Americas (non-USA)",
    "Chile": "Americas (non-USA)",

    "England": "Europe", "Scotland": "Europe", "Northern Ireland": "Europe",
    "Ireland": "Europe", "Wales": "Europe", "France": "Europe",
    "Germany": "Europe", "Italy": "Europe", "Spain": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe",
    "Finland": "Europe", "Poland": "Europe", "Austria": "Europe",
    "Netherlands": "Europe", "Belgium": "Europe", "Switzerland": "Europe",
    "Portugal": "Europe",

    "Japan": "Asia", "South Korea": "Asia", "China": "Asia",
    "Thailand": "Asia", "India": "Asia", "Taiwan": "Asia",
    "Malaysia": "Asia", "Philippines": "Asia", "Indonesia": "Asia",

    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",

    "South Africa": "Africa", "Zimbabwe": "Africa", "Kenya": "Africa",
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _top_player_prob(players_in_group: List[Dict[str, Any]],
                     prob_key: str) -> List[Dict[str, Any]]:
    """For each player in the group, return their probability of being the
    top finisher in the group. Approximation: each player's marginal p_top5
    contributes proportionally."""
    total = sum((p.get(prob_key) or 0) for p in players_in_group)
    if total <= 0: return []
    out = []
    for p in players_in_group:
        marginal = p.get(prob_key) or 0
        p_top_in_group = marginal / total
        out.append({
            "name": p.get("name"),
            "country": p.get("country"),
            "p_top_in_region": round(p_top_in_group, 4),
            "marginal_p_top": marginal,
            "fair_american": _american(p_top_in_group),
        })
    out.sort(key=lambda x: -x["p_top_in_region"])
    return out


def run() -> Dict[str, Any]:
    g = _load(os.path.join(DATA_DIR, "golf_props.json"))
    players = g.get("players") or []
    if not players:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "n_players": 0, "note": "no golf field data"}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Bucket players by region
    by_region: Dict[str, List[Dict[str, Any]]] = {}
    for p in players:
        if p.get("is_cut") or p.get("is_withdrawn"): continue
        region = REGION_OF.get(p.get("country") or "", "Other")
        by_region.setdefault(region, []).append(p)

    # For each region, compute top finisher probabilities
    regions: List[Dict[str, Any]] = []
    for region, ps in by_region.items():
        if len(ps) < 2: continue   # need at least 2 players for a meaningful market
        top5_dist = _top_player_prob(ps, "p_top5")
        top10_dist = _top_player_prob(ps, "p_top10")
        regions.append({
            "region": region,
            "n_players": len(ps),
            "top_top5": top5_dist[:8],
            "top_top10": top10_dist[:8],
            "favorite_top5": top5_dist[0] if top5_dist else None,
            "favorite_top10": top10_dist[0] if top10_dist else None,
        })
    regions.sort(key=lambda r: -r["n_players"])

    # Cross-region matchup pairs: top USA vs top non-USA
    usa_top = next((r for r in regions if r["region"] == "USA"), None)
    intl_top = []
    for r in regions:
        if r["region"] != "USA" and r["favorite_top10"]:
            intl_top.append(r["favorite_top10"])
    intl_top.sort(key=lambda x: -x["p_top_in_region"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "tournament": (g.get("tournament") if isinstance(g.get("tournament"), str)
                        else (g.get("tournament") or {}).get("name") if isinstance(g.get("tournament"), dict)
                        else None),
        "n_active_players": sum(r["n_players"] for r in regions),
        "n_regions": len(regions),
        "regions": regions,
        "top_usa_vs_top_intl": {
            "usa_favorite": usa_top["favorite_top10"] if usa_top else None,
            "intl_favorite": intl_top[0] if intl_top else None,
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Golf region props: {p['n_active_players']} active players across {p['n_regions']} regions")
    for r in p.get("regions", []):
        fav5 = r.get("favorite_top5") or {}
        fav10 = r.get("favorite_top10") or {}
        print(f"  [{r['region']:25s}] n={r['n_players']:3} "
              f"top5_fav: {fav5.get('name','?'):20s} ({fav5.get('p_top_in_region',0)*100:.0f}%, fair {fav5.get('fair_american','?')}) "
              f"top10_fav: {fav10.get('name','?'):20s} ({fav10.get('p_top_in_region',0)*100:.0f}%)")
    cross = p.get("top_usa_vs_top_intl") or {}
    usa = cross.get("usa_favorite") or {}
    intl = cross.get("intl_favorite") or {}
    print(f"\nTop USA vs Top International (top10 markets):")
    print(f"  USA:  {usa.get('name','?')} ({usa.get('country','?')}) {usa.get('p_top_in_region',0)*100:.0f}% fair {usa.get('fair_american','?')}")
    print(f"  INTL: {intl.get('name','?')} ({intl.get('country','?')}) {intl.get('p_top_in_region',0)*100:.0f}% fair {intl.get('fair_american','?')}")
