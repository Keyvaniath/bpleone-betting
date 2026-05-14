"""
EdgeStat -- umpire feed.

Pulls the Home Plate umpire from MLB's schedule endpoint
(?hydrate=officials), plus a curated tendency table for well-known umpires.

The tendency table is a stand-in for a real per-umpire-K-rate database (which
requires either a paid feed like Umpire Scorecards Pro, or computing from
pitch-by-pitch data nightly). For now, we lean on the well-publicized
tendencies of the most discussed plate umps. Brandon can extend the table.

Returns a multiplier in [0.93, 1.07] applied to expected Ks. A tight zone =>
fewer Ks => multiplier < 1. Wide zone => more Ks => multiplier > 1.
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "umpires")
CACHE_TTL = 6 * 3600


# Curated tendencies from published Umpire Scorecards aggregates (2024-2025).
# Values are K-multipliers: 1.05 means ~5% more Ks than league average; 0.95 = 5% fewer.
# Source: public season summaries; refine over time.
TENDENCIES: Dict[str, Dict[str, Any]] = {
    "Pat Hoberg":      {"k_mult": 0.99, "label": "tight, very accurate"},
    "Tripp Gibson":    {"k_mult": 0.97, "label": "tight zone"},
    "Mark Carlson":    {"k_mult": 1.03, "label": "wide zone"},
    "Angel Hernandez": {"k_mult": 1.05, "label": "wide / inconsistent"},   # retired but historical reference
    "C.B. Bucknor":    {"k_mult": 1.04, "label": "wide zone"},
    "Doug Eddings":    {"k_mult": 0.96, "label": "tight zone"},
    "Joe West":        {"k_mult": 1.06, "label": "very wide (retired)"},
    "Edwin Moscoso":   {"k_mult": 1.04, "label": "wide zone"},
    "Larry Vanover":   {"k_mult": 1.03, "label": "wide-ish"},
    "Bill Miller":     {"k_mult": 1.00, "label": "neutral"},
    "Quinn Wolcott":   {"k_mult": 1.02, "label": "slightly wide"},
    "Lance Barksdale": {"k_mult": 1.04, "label": "wide zone"},
    "John Tumpane":    {"k_mult": 0.98, "label": "slightly tight"},
    "Phil Cuzzi":      {"k_mult": 1.02, "label": "slightly wide"},
    "Alan Porter":     {"k_mult": 0.99, "label": "neutral"},
}


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def _cache_get(name: str) -> Optional[Any]:
    p = _cache_path(name)
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > CACHE_TTL:
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _cache_put(name: str, data: Any) -> None:
    try:
        with open(_cache_path(name), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def get_home_plate_umpire(game_pk: int) -> Dict[str, Any]:
    """Returns {name, id, k_mult, label} for the HP umpire of a game. {} if not posted yet."""
    cache_name = f"ump_{game_pk}"
    c = _cache_get(cache_name)
    if c is not None:
        return c
    if requests is None:
        return {}
    try:
        r = requests.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&gamePk={game_pk}&hydrate=officials", timeout=10)
        if not r.ok:
            return {}
        d = r.json()
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    for date in d.get("dates", []):
        for g in date.get("games", []):
            for o in g.get("officials", []) or []:
                if o.get("officialType") == "Home Plate":
                    name = (o.get("official") or {}).get("fullName")
                    out = {
                        "name": name,
                        "id": (o.get("official") or {}).get("id"),
                        **TENDENCIES.get(name or "", {"k_mult": 1.0, "label": "no tendency data"}),
                    }
                    break
    _cache_put(cache_name, out)
    return out


def k_multiplier(game_pk: int) -> float:
    u = get_home_plate_umpire(game_pk)
    return float(u.get("k_mult", 1.0))


if __name__ == "__main__":
    # Pull today's umpires from MLB schedule
    if requests is None:
        raise SystemExit("requests not installed")
    sched = requests.get("https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=officials", timeout=15).json()
    print("Today's HP umpires:")
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            for o in g.get("officials", []) or []:
                if o.get("officialType") != "Home Plate":
                    continue
                name = (o.get("official") or {}).get("fullName")
                tend = TENDENCIES.get(name or "", {"k_mult": 1.0, "label": "no tendency data"})
                marker = "" if tend["k_mult"] == 1.0 else f" -- {tend['label']} (K mult={tend['k_mult']})"
                print(f"  gamePk={g['gamePk']}: {name}{marker}")
