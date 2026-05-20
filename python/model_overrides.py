"""
EdgeStat -- Model overrides loader.

Reads data/model_overrides.json (user-editable via /model-control.html) and
provides accessor functions:
  - source_weight(source) -> overridden weight or None
  - sport_prior(sport) -> { k_per_9_prior, era_prior, hit_rate_floor, ... }
  - constraint(name) -> { min_ev_pct, max_picks_per_game, exclude_park, ... }
  - is_module_enabled(module_name) -> bool

The overrides file is OPTIONAL. If absent, everything falls back to the
hand-tuned PRIOR_WEIGHTS in self_learn_weights.py.

Used by:
  - todays_top_plays.py  -- applies source weight overrides
  - self_learn_weights.py -- merges learned + override
  - locks_of_day.py       -- applies edge floors
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OVERRIDES_FILE = os.path.join(DATA_DIR, "model_overrides.json")

_CACHE = None


def _load() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not os.path.exists(OVERRIDES_FILE):
        _CACHE = {"version": 0, "sources": {}, "sports": {}, "constraints": {},
                  "modules": {}, "global": {}}
        return _CACHE
    try:
        with open(OVERRIDES_FILE) as f:
            _CACHE = json.load(f) or {}
    except Exception:
        _CACHE = {}
    # Backfill missing keys
    for k in ("sources", "sports", "constraints", "modules", "global"):
        _CACHE.setdefault(k, {})
    return _CACHE


def reload() -> Dict[str, Any]:
    """Force re-read from disk."""
    global _CACHE
    _CACHE = None
    return _load()


def source_weight(source: str) -> Optional[float]:
    o = _load().get("sources", {}).get(source)
    if isinstance(o, dict):
        return o.get("weight")
    if isinstance(o, (int, float)):
        return float(o)
    return None


def sport_prior(sport: str) -> Dict[str, Any]:
    return _load().get("sports", {}).get(sport, {}) or {}


def constraint(name: str, default=None) -> Any:
    return _load().get("constraints", {}).get(name, default)


def is_module_enabled(module: str) -> bool:
    m = _load().get("modules", {}).get(module)
    if m is None: return True
    if isinstance(m, dict):
        return bool(m.get("enabled", True))
    return bool(m)


def global_param(name: str, default=None) -> Any:
    return _load().get("global", {}).get(name, default)


def all_overrides() -> Dict[str, Any]:
    """Get the full override config (for the dashboard)."""
    return _load()


def write_overrides(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Write a new overrides payload (used by the worker save endpoint)."""
    global _CACHE
    os.makedirs(os.path.dirname(OVERRIDES_FILE), exist_ok=True)
    with open(OVERRIDES_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    _CACHE = None
    return _load()


if __name__ == "__main__":
    o = all_overrides()
    print(f"overrides: {len(o.get('sources', {}))} source weights, "
          f"{len(o.get('sports', {}))} sport priors, "
          f"{len(o.get('constraints', {}))} constraints, "
          f"{len(o.get('modules', {}))} module toggles")
