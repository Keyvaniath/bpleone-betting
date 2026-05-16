"""
EdgeStat -- daily picks CSV export.

Builds a clean CSV of tonight's top plays for external tracking
(spreadsheets / accounting / personal ledger software).

Output: data/picks_today.csv
"""
from __future__ import annotations
import os, json, csv, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BB_PATH = os.path.join(DATA_DIR, "best_bets.json")
PORTFOLIO_PATH = os.path.join(DATA_DIR, "portfolio.json")
OUT_PATH = os.path.join(DATA_DIR, "picks_today.csv")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    bb = _load(BB_PATH).get("bets") or []
    port = (_load(PORTFOLIO_PATH).get("picks") or [])
    port_keys = {(p.get("label"), p.get("market"), p.get("line"), p.get("play")) for p in port}

    cols = ["rank", "in_auto_portfolio", "source", "player", "market",
             "line", "play", "model_prob", "edge_pct", "quality_score",
             "stars", "url_anchor"]
    rows: List[List[Any]] = []
    for b in bb:
        in_port = (b.get("label"), b.get("market"), b.get("line"), b.get("play")) in port_keys
        rows.append([
            b.get("rank"), "yes" if in_port else "no",
            b.get("source"), b.get("player"), b.get("market"),
            b.get("line"), b.get("play"), b.get("model_prob"),
            b.get("edge_pct"), b.get("quality_score"),
            b.get("stars"), b.get("url_anchor"),
        ])

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "rows": len(rows), "path": OUT_PATH}


if __name__ == "__main__":
    p = run()
    print(f"Wrote {p['path']}: {p['rows']} picks")
