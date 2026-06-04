"""
EdgeStat -- MLB weather -> pitcher run-environment factor (shared helper).

The pitcher prop generators (K / ER / hits) already adjust for the opposing
lineup (K-rate, OBP) and a STATIC park factor -- but they ignore the live
weather that the slate feed already carries per game. This module turns that
weather into small, auditable multipliers the generators apply on top of their
projection, so a cold wind-in night plays UNDER and a warm wind-out day plays
OVER the way a sharp would shade it.

Signal. Each game in matchups.json carries a `weather` dict:
    {temp_f, wind_mph, is_indoor, wind_dir_deg, carry_index, precip_pct}
`carry_index` is the canonical wind-to-CF signal in [-1, +1] (pipeline.py): +1 =
wind straight out (carry boost), -1 = straight in (suppress), 0 / None = indoor
or calm. We anchor the wind coefficient to the house convention already in
first_five.py (F5 total env_mult = 1 + 0.10*carry, "a bit less than full HR").
Temperature is independent of the wind-only carry, so it gets its own small term
(warm air carries the ball; references 70F).

Dampening reflects how wind/temp sensitivity falls off by outcome:
    HR  >>  runs (ER)  >  hits  >  strikeouts
HRs are very wind-sensitive (that's the HR index); runs less, hits less again
(much of the carry benefit is extra-base hits, not singles), and K barely at all
(good carry mildly favors the hitter). Walks are NOT weather-driven (command, not
carry) and intentionally get no adjustment.

Everything degrades to a neutral 1.0 when weather is missing or the roof is
closed, so off-season / no-data runs are unaffected. Coefficients are module
constants so multiplier_tuner.py can grid-search them as outcomes accumulate.

Usage in a generator's per-game loop:
    import mlb_weather_factor as _WX
    wf = _WX.pitcher_weather_factors(g.get("weather"))
    expected_er *= wf["er_mult"]      # or k_mult / hits_mult
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Wind (per unit of carry_index, which is in [-1, +1]).
CARRY_ER = 0.11      # earned runs ~ full run environment (>= F5 total's 0.10 anchor)
CARRY_HITS = 0.06    # hits less wind-sensitive than runs (carry helps XBH/HR most)
CARRY_K = 0.03       # good carry mildly suppresses K (favors the hitter); small + inverse

# Temperature (per degF above/below the 70F reference). Independent of carry,
# which is wind-only. Damped well below the HR index's 0.004/F (runs << HR).
TEMP_REF = 70.0
TEMP_ER = 0.0025
TEMP_HITS = 0.0015
TEMP_DELTA_CLAMP = 25.0   # ignore absurd forecast temps beyond +/-25F of ref

# Final clamps -- weather is a real but secondary factor; keep it modest.
ER_BAND = (0.90, 1.12)
HITS_BAND = (0.93, 1.08)
K_BAND = (0.96, 1.04)

NEUTRAL = {"er_mult": 1.0, "hits_mult": 1.0, "k_mult": 1.0,
           "carry": 0.0, "temp_f": None, "is_indoor": None, "active": False}


def _num(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _carry(weather: Dict[str, Any]) -> float:
    """Canonical carry_index in [-1, +1]; 0 when indoor / missing / calm."""
    if weather.get("is_indoor") or weather.get("roof_closed"):
        return 0.0
    c = _num(weather.get("carry_index"))
    if c is None:
        return 0.0
    return _clamp(c, -1.0, 1.0)


def _temp_delta(weather: Dict[str, Any]) -> float:
    t = _num(weather.get("temp_f") if weather.get("temp_f") is not None
             else weather.get("temperature"))
    if t is None:
        return 0.0
    return _clamp(t - TEMP_REF, -TEMP_DELTA_CLAMP, TEMP_DELTA_CLAMP)


def pitcher_weather_factors(weather: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Weather -> {er_mult, hits_mult, k_mult, ...} for a pitcher's projection.

    er_mult / hits_mult > 1 in a hitter's sky (warm, wind out); k_mult < 1 there.
    Returns the NEUTRAL (all-1.0) dict for missing weather or a closed roof, so
    callers can multiply unconditionally."""
    if not weather or not isinstance(weather, dict):
        return dict(NEUTRAL)
    is_indoor = bool(weather.get("is_indoor") or weather.get("roof_closed"))
    carry = _carry(weather)
    # A closed roof is a climate-controlled dome -> no wind AND no temp effect.
    td = 0.0 if is_indoor else _temp_delta(weather)

    er = 1.0 + CARRY_ER * carry + TEMP_ER * td
    hits = 1.0 + CARRY_HITS * carry + TEMP_HITS * td
    k = 1.0 - CARRY_K * carry          # temp effect on K is negligible/debated -> omit

    return {
        "er_mult": round(_clamp(er, *ER_BAND), 4),
        "hits_mult": round(_clamp(hits, *HITS_BAND), 4),
        "k_mult": round(_clamp(k, *K_BAND), 4),
        "carry": round(carry, 3),
        "temp_f": _num(weather.get("temp_f")),
        "is_indoor": is_indoor,
        # "active" = weather actually moved something (outdoor + a real signal).
        "active": (not is_indoor) and (abs(carry) > 1e-9 or abs(td) > 1e-9),
    }


if __name__ == "__main__":
    scenarios = {
        "indoor dome":            {"temp_f": 72, "wind_mph": 0, "is_indoor": True, "carry_index": 0.0},
        "neutral 70F calm":       {"temp_f": 70, "wind_mph": 2, "is_indoor": False, "carry_index": 0.0},
        "Wrigley wind OUT, warm":  {"temp_f": 84, "wind_mph": 14, "is_indoor": False, "carry_index": 0.55},
        "cold wind IN":           {"temp_f": 52, "wind_mph": 16, "is_indoor": False, "carry_index": -0.7},
        "missing weather":        None,
    }
    print(f"{'scenario':24} {'er_mult':>8} {'hits_mult':>10} {'k_mult':>8}  active")
    for name, wx in scenarios.items():
        f = pitcher_weather_factors(wx)
        print(f"{name:24} {f['er_mult']:>8} {f['hits_mult']:>10} {f['k_mult']:>8}  {f['active']}")
