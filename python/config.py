"""
EdgeStat -- central tunable-parameter registry.

Every model knob lives here as a default. Brandon (or any operator) can
override any of them at runtime by editing data/runtime_config.json --
a flat JSON map of {key: value}. No code change, no PR, no deploy:
edit the JSON in the GitHub web editor, commit, and the next cron picks
it up.

Why a centralized config:
  - "tweak with constraints or parameters" is hard when knobs are sprinkled
    across 8 modules. One file means one place to look.
  - Surfaces every parameter on /config.html with description + default
    + override status so the operator can SEE what's being applied.
  - No magic: every default is in DEFAULTS below. Overrides only override
    what's explicitly set; everything else falls through to the default.

Usage in other modules:
    from config import get
    n_prior = get("calibration.n_prior_default")

The /config.html page reads DEFAULTS + runtime_config.json to render the
full table.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OVERRIDES_PATH = os.path.join(DATA_DIR, "runtime_config.json")


# Defaults + descriptions. Edit the description if the parameter's meaning
# changes; edit data/runtime_config.json (NOT this file) to override at runtime.
SCHEMA: Dict[str, Dict[str, Any]] = {
    # -------- Bayesian calibration (calibration_runner.py) --------
    "calibration.n_prior_default": {
        "default": 8,
        "type": "int",
        "min": 1, "max": 100,
        "desc": "Shrinkage anchor. n=N_PRIOR hits 50/50 data/prior weight. Lower = trust data faster (more aggressive learning, more variance).",
    },
    "calibration.n_prior_per_market": {
        "default": {
            "pitcher_strikeouts": 10,
            "batter_home_runs": 12,
            "batter_rbis": 10,
            "batter_total_bases": 6,
            "batter_hits": 6,
            "batter_singles": 6,
            "batter_doubles": 8,
            "batter_runs_scored": 8,
            "batter_hits_runs_rbis": 8,
        },
        "type": "dict[str,int]",
        "desc": "Per-market shrinkage override. Rare/noisy markets (HR, RBI) need higher; high-volume (hits/TB) lower.",
    },
    "calibration.max_correction": {
        "default": 1.35,
        "type": "float",
        "min": 1.05, "max": 2.0,
        "desc": "Maximum multiplicative correction (cap on bias adjustment per refresh). 1.35 = ±35% band.",
    },
    "calibration.min_sample_for_any_correction": {
        "default": 1,
        "type": "int",
        "min": 1, "max": 30,
        "desc": "Below this many settled outcomes, correction is forced to 1.0 (no change).",
    },

    # -------- Per-player bias overrides (player_bias.py) --------
    "player_bias.min_player_n": {
        "default": 3,
        "type": "int",
        "min": 2, "max": 20,
        "desc": "Minimum settled records on a player+market before a per-player override fires.",
    },
    "player_bias.z_threshold": {
        "default": 2.0,
        "type": "float",
        "min": 1.0, "max": 4.0,
        "desc": "Standard-deviations from market mean residual to flag a player as systematically off.",
    },
    "player_bias.max_boost": {
        "default": 1.20,
        "type": "float",
        "min": 1.05, "max": 1.50,
        "desc": "Cap on per-player multiplier (less aggressive than market-level because n is smaller).",
    },

    # -------- Live edge alerts (live_edges.py) --------
    "live_edges.edge_threshold_pp": {
        "default": 5.0,
        "type": "float",
        "min": 1.0, "max": 20.0,
        "desc": "Percentage-points divergence between model_p_win and book implied to trigger a live alert.",
    },

    # -------- Play selection (props_pipeline.py, pipeline.py) --------
    "plays.min_edge_pct": {
        "default": 3.0,
        "type": "float",
        "min": 0.5, "max": 15.0,
        "desc": "Minimum model-vs-book edge to surface a play (else SKIP). Higher = more selective.",
    },
    "plays.kelly_fraction": {
        "default": 0.25,
        "type": "float",
        "min": 0.05, "max": 1.0,
        "desc": "Fractional-Kelly stake. 0.25 = quarter-Kelly (defensive). 1.0 = full Kelly (aggressive).",
    },
    "plays.max_kelly_units": {
        "default": 1.5,
        "type": "float",
        "min": 0.25, "max": 5.0,
        "desc": "Hard cap on recommended stake per play in units, regardless of model confidence.",
    },
    "plays.pre_cal_edge_cap_pct": {
        "default": 15.0,
        "type": "float",
        "min": 5.0, "max": 50.0,
        "desc": "Edge above this is treated as pre-calibration noise -- Kelly forced to <=0.5u + display capped.",
    },

    # -------- Parlay engine (parlays.py) --------
    "parlays.max_leg_prob": {
        "default": 0.85,
        "type": "float",
        "min": 0.55, "max": 0.99,
        "desc": "Cap on per-leg probability used in parlay EV math. Prevents thin-sample 99% probs from compounding to absurd EVs.",
    },
    "parlays.suppress_edge_below_pct": {
        "default": 3.0,
        "type": "float",
        "min": 0.0, "max": 10.0,
        "desc": "Single-leg edges below this don't qualify as parlay legs.",
    },
    "parlays.suppress_edge_above_pct": {
        "default": 25.0,
        "type": "float",
        "min": 10.0, "max": 100.0,
        "desc": "Single-leg edges above this are likely pre-cal noise; rejected as parlay legs.",
    },
    "parlays.min_ev_pct": {
        "default": 8.0,
        "type": "float",
        "min": 0.0, "max": 30.0,
        "desc": "Minimum parlay EV to surface.",
    },
    "parlays.max_ev_pct": {
        "default": 50.0,
        "type": "float",
        "min": 10.0, "max": 200.0,
        "desc": "Maximum parlay EV to surface (over this is almost certainly noise).",
    },

    # -------- Model trainer (model_trainer.py) --------
    "trainer.min_train_sample": {
        "default": 15,
        "type": "int",
        "min": 5, "max": 500,
        "desc": "Per-market settled-outcome threshold before a market graduates to TRAINABLE.",
    },
    "trainer.blend_grid": {
        "default": [0.20, 0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80],
        "type": "list[float]",
        "desc": "Statcast-vs-season blend weights tried by the grid search.",
    },
    "trainer.amplifier_grid": {
        "default": [0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5],
        "type": "list[float]",
        "desc": "Multiplier amplifiers tried by multiplier_tuner on opp_mult / umpire_k_mult / park_hand_mult.",
    },

    # -------- Props pipeline pull (props_pipeline.py) --------
    "props.max_games": {
        "default": 16,
        "type": "int",
        "min": 1, "max": 32,
        "desc": "Cap on # of games to fetch props for, to fit Odds API quota.",
    },

    # -------- Historical backfill (historical_backfill.py) --------
    "backfill.max_players_gamelog": {
        "default": 350,
        "type": "int",
        "min": 50, "max": 1000,
        "desc": "Cap on player gamelog pulls per cron run (MLB Stats API rate-limit guard).",
    },
    "backfill.gamelog_depth_games": {
        "default": 14,
        "type": "int",
        "min": 5, "max": 60,
        "desc": "How many games back to pull per-player gamelog for sparkline.",
    },

    # -------- Walk-forward backtest (walk_forward.py) --------
    "walk_forward.window_days": {
        "default": 3,
        "type": "int",
        "min": 1, "max": 14,
        "desc": "Rolling window size for walk-forward Brier evaluation.",
    },
    "walk_forward.min_window_samples": {
        "default": 30,
        "type": "int",
        "min": 5, "max": 200,
        "desc": "Skip windows with fewer than this many records.",
    },

    # -------- Learning curves (learning_curves.py) --------
    "learning_curves.window_days": {
        "default": 7,
        "type": "int",
        "min": 3, "max": 30,
        "desc": "Rolling window size for per-market Brier learning-curve chart.",
    },
    "learning_curves.stride_days": {
        "default": 1,
        "type": "int",
        "min": 1, "max": 7,
        "desc": "Window stride for learning-curve chart (1 = daily points).",
    },
    "learning_curves.min_per_window": {
        "default": 20,
        "type": "int",
        "min": 5, "max": 200,
        "desc": "Minimum records required in a window before plotting that point.",
    },

    # -------- Context calibration (context_calibration.py) --------
    "context_calibration.enabled": {
        "default": False,
        "type": "bool",
        "desc": "If true, props_pipeline applies context-conditional corrections (indoor/outdoor, day/night, etc.) on top of market + player bias. OFF by default until validated.",
    },
    "context_calibration.min_slice_n": {
        "default": 80,
        "type": "int",
        "min": 20, "max": 500,
        "desc": "Minimum settled records in a context slice before reporting a correction.",
    },
    "context_calibration.bias_threshold": {
        "default": 0.04,
        "type": "float",
        "min": 0.01, "max": 0.20,
        "desc": "Slice must show |extra_residual| >= this (above bulk-market bias) to qualify.",
    },
    "context_calibration.z_threshold": {
        "default": 1.5,
        "type": "float",
        "min": 1.0, "max": 4.0,
        "desc": "Z-score threshold (binomial std) for slice significance.",
    },
    "context_calibration.max_correction": {
        "default": 1.20,
        "type": "float",
        "min": 1.05, "max": 1.50,
        "desc": "Cap on slice-level correction (tighter than market-level because n is smaller).",
    },

    # -------- Anomaly detector (anomalies.py) --------
    "anomalies.systematic_z_threshold": {
        "default": 2.0,
        "type": "float",
        "min": 1.0, "max": 4.0,
        "desc": "Z-score threshold to flag a player+market pair as a systematic anomaly.",
    },
    "anomalies.outlier_z_threshold": {
        "default": 3.0,
        "type": "float",
        "min": 1.5, "max": 5.0,
        "desc": "Z-score threshold for a single-day outlier (freak game).",
    },

    # -------- Rationale generation (rationales.py) --------
    "rationales.max_props_props_path": {
        "default": 300,
        "type": "int",
        "min": 50, "max": 2000,
        "desc": "Max rationales to generate from props.json per cron run (HTTP-bound).",
    },
    "rationales.max_props_pickem_path": {
        "default": 200,
        "type": "int",
        "min": 50, "max": 2000,
        "desc": "Max rationales to generate from pickem.json per cron run.",
    },
}


def _load_overrides() -> Dict[str, Any]:
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    try:
        with open(OVERRIDES_PATH) as f:
            return json.load(f) or {}
    except Exception:
        return {}


def get(key: str, default: Optional[Any] = None) -> Any:
    """Return runtime override if set; else SCHEMA default; else `default` arg."""
    overrides = _load_overrides()
    if key in overrides:
        return overrides[key]
    if key in SCHEMA:
        return SCHEMA[key]["default"]
    return default


def schema() -> Dict[str, Dict[str, Any]]:
    """Return the full schema (for /config.html and tests)."""
    return SCHEMA


def overrides() -> Dict[str, Any]:
    """Return current overrides verbatim."""
    return _load_overrides()


def dump_schema_with_current() -> Dict[str, Any]:
    """For /config.html: write schema + current values + override flag to JSON."""
    ovr = _load_overrides()
    out: Dict[str, Any] = {"keys": {}}
    for k, v in SCHEMA.items():
        is_overridden = k in ovr
        out["keys"][k] = {
            **v,
            "current": ovr[k] if is_overridden else v["default"],
            "is_overridden": is_overridden,
        }
    out["overrides_path"] = "data/runtime_config.json"
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        # Write the schema-with-current snapshot for /config.html
        snap = dump_schema_with_current()
        out_path = os.path.join(DATA_DIR, "config_snapshot.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(snap, f, indent=2)
        print(f"Wrote {out_path}: {len(snap['keys'])} keys")
    else:
        print(f"Schema keys: {len(SCHEMA)}")
        ovr = _load_overrides()
        print(f"Overrides loaded: {len(ovr)} -- {list(ovr.keys()) if ovr else 'none'}")
        for k, v in SCHEMA.items():
            current = get(k)
            flag = " (override)" if k in ovr else ""
            print(f"  {k:55} = {current}{flag}")
