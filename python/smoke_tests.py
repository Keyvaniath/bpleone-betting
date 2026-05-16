"""
EdgeStat -- smoke tests.

Quick sanity checks on every critical module + data shape. Runs in CI
before the heavy pipeline steps so we catch obvious breakage early.

Designed to be fast (<10s total) and side-effect-free (reads data/*.json,
doesn't write). Exits non-zero on any failure so the workflow fails fast.
"""
from __future__ import annotations

import os
import sys
import json
import importlib
from typing import Any, Callable, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS: List[Tuple[str, str, str]] = []  # (test_name, status, message)


def ok(name: str, msg: str = "") -> None:
    RESULTS.append((name, "PASS", msg))
    print(f"  [ok] {name}: {msg}")


def fail(name: str, msg: str) -> None:
    RESULTS.append((name, "FAIL", msg))
    print(f"  [FAIL] {name}: {msg}")


def warn(name: str, msg: str) -> None:
    RESULTS.append((name, "WARN", msg))
    print(f"  [warn] {name}: {msg}")


def test_imports() -> None:
    """Every critical module imports without error.

    Two tiers: CORE (must always import) and EXTENDED (newer feature
    modules, allowed to fail soft on missing deps but logged)."""
    core_modules = [
        "probability", "features", "mlb_model", "data_fetcher",
        "stats_repo", "pipeline", "props_pipeline", "outcomes",
        "calibration_runner", "residuals", "perf_trend",
        "pipeline_health", "bovada", "snapshot",
    ]
    # Newer feature modules added in PR #40..#43. Soft-fail tolerated --
    # we log them but don't abort the smoke test on these alone.
    extended_modules = [
        "rationales", "anomalies", "drift_detector", "walk_forward",
        "player_bias", "model_trainer", "model_confidence",
        "player_gamelogs", "player_breakdown", "backfill_context",
        "live_props", "sgp_builder", "pitcher_fatigue",
        "weather_conditional", "slate_confidence", "best_bets",
        "lineup_churn", "bullpen_alert", "sharpe_ranking",
        "portfolio_optimizer", "bankroll_simulator", "line_timing",
        "clv_per_bet", "dow_pl", "hot_streaks", "cross_book_arb",
        "velocity_decay", "csv_export", "nba_stub", "nfl_stub",
        "notify_discord", "k_pace_alerts", "pipeline_audit",
    ]
    for m in core_modules:
        try:
            importlib.import_module(m)
            ok(f"import {m}", "loaded")
        except Exception as e:
            fail(f"import {m}", f"{type(e).__name__}: {e}")
    for m in extended_modules:
        try:
            importlib.import_module(m)
            ok(f"import {m}", "loaded (extended)")
        except ModuleNotFoundError:
            warn(f"import {m}", "module not present in this branch (may be on unmerged PR)")
        except Exception as e:
            warn(f"import {m}", f"{type(e).__name__}: {e}")


def test_data_shapes() -> None:
    """Critical artifacts exist and have the expected top-level shape."""
    checks = [
        ("today.json", ["games"]),
        ("calibration_live.json", ["markets"]),
        ("track_record.json", ["props"]),
        ("residuals.json", ["markets"]),
    ]
    for filename, required_keys in checks:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            warn(f"shape {filename}", "file missing -- pipeline hasn't generated yet")
            continue
        try:
            with open(path) as f:
                d = json.load(f)
        except Exception as e:
            fail(f"shape {filename}", f"json parse error: {e}")
            continue
        missing = [k for k in required_keys if k not in d]
        if missing:
            fail(f"shape {filename}", f"missing keys: {missing}")
        else:
            ok(f"shape {filename}", f"has {required_keys}")


def test_bovada_fetch() -> None:
    """Bovada is reachable + returns at least 1 MLB event."""
    try:
        from bovada import fetch_game_lines
        gl = fetch_game_lines()
        if not gl:
            warn("bovada", "0 games returned (may be off-day or rate limited)")
        else:
            ok("bovada", f"{len(gl)} games + lines")
    except Exception as e:
        fail("bovada", f"{type(e).__name__}: {e}")


def test_calibration_logic() -> None:
    """Bayesian shrinkage produces values in expected range."""
    try:
        from calibration_runner import correction_factor, N_PRIOR, MIN_CORRECTION, MAX_CORRECTION
        # n=0 -> 1.0 (no correction)
        cf = correction_factor({"n": 0, "bias": 2.0})
        assert cf == 1.0, f"n=0 should be 1.0, got {cf}"
        # huge n + strong bias -> approaches raw correction
        cf2 = correction_factor({"n": 10000, "bias": 1.5})
        assert MIN_CORRECTION <= cf2 <= MAX_CORRECTION, f"out of bounds: {cf2}"
        # weighted between extremes
        cf3 = correction_factor({"n": N_PRIOR, "bias": 1.5})
        assert MIN_CORRECTION < cf3 < 1.0, f"50/50 weight should be between min and 1: {cf3}"
        ok("calibration shrinkage", f"n=0:1.0, n={N_PRIOR}:{cf3:.4f}, n=10k:{cf2:.4f}")
    except Exception as e:
        fail("calibration shrinkage", f"{type(e).__name__}: {e}")


def test_mlb_stats_api() -> None:
    """MLB Stats API is reachable."""
    try:
        import requests
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1}, timeout=10,
        )
        if not r.ok:
            fail("mlb stats api", f"status {r.status_code}")
            return
        d = r.json()
        if "dates" not in d:
            fail("mlb stats api", "unexpected shape")
            return
        ok("mlb stats api", f"reachable, {sum(len(x['games']) for x in d.get('dates', []))} games today")
    except Exception as e:
        fail("mlb stats api", f"{type(e).__name__}: {e}")


def test_pipeline_health_runs() -> None:
    """pipeline_health.run() returns a payload with all expected keys."""
    try:
        import pipeline_health
        p = pipeline_health.run()
        for k in ("overall_status", "artifacts", "n_ok", "total_artifacts"):
            assert k in p, f"missing key {k}"
        ok("pipeline_health", f"overall={p['overall_status']}, {p['n_ok']}/{p['total_artifacts']} ok")
    except Exception as e:
        fail("pipeline_health", f"{type(e).__name__}: {e}")


def main() -> int:
    print("Running EdgeStat smoke tests...")
    print()
    test_imports()
    test_data_shapes()
    test_calibration_logic()
    test_pipeline_health_runs()
    test_bovada_fetch()
    test_mlb_stats_api()

    print()
    passes = sum(1 for _, s, _ in RESULTS if s == "PASS")
    fails = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    warns = sum(1 for _, s, _ in RESULTS if s == "WARN")
    print(f"Summary: {passes} pass / {warns} warn / {fails} fail / {len(RESULTS)} total")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
