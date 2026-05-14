"""
EdgeStat -- snapshot writer.

Preserves today's projections (today.json, props.json, matchups.json) into
data/history/{YYYY-MM-DD}_{type}.json so outcomes.py can settle them tomorrow.

Idempotent: writing the same date twice just overwrites with the latest
projection. Called at the END of pipeline.py so projections reflect the
most-recent refresh (lineups/odds may move during the day).
"""
from __future__ import annotations

import os
import json
import shutil
import datetime as dt
from typing import List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

SNAPSHOT_FILES = ["today.json", "props.json", "matchups.json"]


def snapshot_today() -> List[str]:
    """Copy today's projections to data/history/{date}_{name}.json. Returns list of written paths."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    date = dt.date.today().isoformat()
    written = []
    for name in SNAPSHOT_FILES:
        src = os.path.join(DATA_DIR, name)
        if not os.path.exists(src):
            continue
        dest = os.path.join(HISTORY_DIR, f"{date}_{name}")
        shutil.copy2(src, dest)
        written.append(dest)
    return written


if __name__ == "__main__":
    paths = snapshot_today()
    print(f"Snapshotted {len(paths)} files to {HISTORY_DIR}/")
    for p in paths:
        print(f"  {p}")
