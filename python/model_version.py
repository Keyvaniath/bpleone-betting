"""
EdgeStat -- Model version tagging.

Writes data/model_version.json with:
  - version: short git commit SHA + UTC date (e.g. "abc1234@2026-05-20")
  - generated_at: ISO timestamp
  - modules_loaded: count of Python modules available
  - sources_active: count of distinct pick sources in PRIOR_WEIGHTS

Every pick that goes into D1 gets stamped with this version so we can later
audit "how did model_abc1234 perform vs model_def5678" with a single SQL
query. This is foundational for multi-year operation and champion/challenger
A/B testing.
"""
from __future__ import annotations

import os
import json
import subprocess
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "model_version.json")


def _git_short_sha() -> str:
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5,
        ).decode("utf-8").strip()
        return sha
    except Exception:
        return "unknown"


def _git_last_commit_date() -> str:
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        d = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI"],
            cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5,
        ).decode("utf-8").strip()
        return d
    except Exception:
        return ""


def _count_modules() -> int:
    py_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        return sum(1 for f in os.listdir(py_dir) if f.endswith(".py") and not f.startswith("_"))
    except Exception:
        return 0


def _count_sources() -> int:
    """Count distinct sources tracked in PRIOR_WEIGHTS."""
    try:
        import self_learn_weights as slw
        return len(slw.PRIOR_WEIGHTS or {})
    except Exception:
        return 0


def get_version() -> str:
    """Stable string used to tag every pick."""
    sha = _git_short_sha()
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    return f"{sha}@{today}"


def run() -> Dict[str, Any]:
    payload = {
        "version": get_version(),
        "git_sha": _git_short_sha(),
        "last_commit_iso": _git_last_commit_date(),
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "modules_loaded": _count_modules(),
        "sources_active": _count_sources(),
        "schema_version": 1,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    v = run()
    print(f"[model-version] version={v['version']} modules={v['modules_loaded']} sources={v['sources_active']}")
