"""
EdgeStat -- data integrity audit.

Scans every prop-module output JSON for `<stat>_source` tags and reports
what fraction of projections are backed by REAL ESPN data vs hardcoded
PLAYER_DB fallback.

The audit is what gives Brandon confidence that the model is learning from
accurate inputs, not from numbers I typed in by hand.

Output: data/data_integrity_audit.json
  {
    "generated_at": "...",
    "modules": [
      {"module": "nba_player_points_props", "real": 187, "fallback": 8,
       "total": 195, "real_pct": 95.9}
      ...
    ],
    "totals": {"real": 1234, "fallback": 56, "real_pct": 95.7}
  }

Plus prints a human-readable summary table to stdout.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "data_integrity_audit.json")

# (output_filename, [list of *_source keys to count])
# Each entry corresponds to a refactored prop module.
MODULES = [
    ("nba_player_points_props.json",      ["ppg_source"]),
    ("nba_player_threes_props.json",      ["tpm_source"]),
    ("nba_player_rebounds_props.json",    ["rpg_source"]),
    ("nba_player_assists_props.json",     ["apg_source"]),
    ("nba_player_pra_props.json",         ["pra_source"]),
    ("nba_double_double_props.json",      ["dd_source"]),
    ("nba_triple_double_props.json",      ["td_source"]),
    ("nba_player_turnovers_props.json",   ["tov_source"]),
    ("nba_player_ft_attempts_props.json", ["fta_source"]),
    ("nba_player_blocks_steals_props.json", ["bpg_source", "spg_source"]),
    ("wnba_player_pts_props.json",        ["ppg_source"]),
    ("wnba_player_reb_ast_props.json",    ["rpg_source", "apg_source"]),
    ("wnba_player_threes_props.json",     ["tpm_source"]),
    ("wnba_player_blocks_steals_props.json", ["blk_stl_source"]),
    ("nhl_anytime_goal_props.json",       ["gpg_source"]),
    ("nhl_first_goalscorer_props.json",   ["gpg_source"]),
    ("nhl_skater_sog_props.json",         ["sogg_source"]),
    ("nhl_skater_points_props.json",      ["ppg_source"]),
    ("mlb_to_record_hit_yn.json",         ["hit_source"]),
    ("mlb_to_hit_hr_yn.json",             ["hr_source"]),
    ("mlb_total_bases_props.json",        ["tb_source"]),
    ("mlb_doubles_props.json",            ["xbh_source"]),
    ("mlb_to_score_run_yn.json",          ["run_source"]),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def audit_module(filename: str, source_keys: List[str]) -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, filename)
    d = _load(path)
    rows = d.get("rows") or d.get("reb_top_25") or d.get("ast_top_25") or []
    # Some modules have nested top-N lists rather than 'rows'
    if not rows:
        for k in ("rows_top_25", "all_rows", "all_players",
                  "top_25_by_xTB", "top_25_by_p_hit", "top_25_by_p_hr",
                  "top_25_by_xXBH", "top_25_by_p_scores"):
            if k in d and isinstance(d[k], list):
                rows = d[k]
                break

    # Real-vs-fallback classifier. Some modules use richer source labels:
    #   real / real_last_14 / lvr_adj  ->  REAL (live or shrunk-from-live data)
    #   fallback / ops_proxy / ops_fallback  ->  FALLBACK (hardcoded/estimated)
    #   missing  ->  MISSING (no source at all)
    REAL_TOKENS = {"real", "real_last_14", "lvr_adj"}
    FALLBACK_TOKENS = {"fallback", "ops_proxy", "ops_fallback"}
    real = 0
    fallback = 0
    missing = 0
    for r in rows:
        if not isinstance(r, dict): continue
        for sk in source_keys:
            src = r.get(sk)
            if src in REAL_TOKENS: real += 1
            elif src in FALLBACK_TOKENS: fallback += 1
            elif src == "missing": missing += 1
            # If the key isn't in the row at all, don't count it (module might
            # not have been refreshed since the migration)

    total = real + fallback + missing
    return {
        "module": filename.replace("_props.json", "").replace(".json", ""),
        "real": real,
        "fallback": fallback,
        "missing": missing,
        "total_tagged": total,
        "n_rows": len(rows),
        "real_pct": round(100 * real / total, 1) if total else None,
    }


def run() -> Dict[str, Any]:
    results = []
    for filename, source_keys in MODULES:
        results.append(audit_module(filename, source_keys))

    total_real = sum(m["real"] for m in results)
    total_fallback = sum(m["fallback"] for m in results)
    total_missing = sum(m["missing"] for m in results)
    grand_total = total_real + total_fallback + total_missing

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "modules": results,
        "totals": {
            "real": total_real,
            "fallback": total_fallback,
            "missing": total_missing,
            "grand_total_tagged": grand_total,
            "real_pct": round(100 * total_real / grand_total, 1) if grand_total else None,
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)

    # Print human summary
    print(f"\n  DATA INTEGRITY AUDIT  ({out['generated_at']})\n")
    print(f"  {'module':<36s} {'real':>5s}/{'total':>5s}   {'pct':>6s}")
    print(f"  {'-'*36} {'-'*5} {'-'*5}   {'-'*6}")
    for m in results:
        pct_str = f"{m['real_pct']:5.1f}%" if m['real_pct'] is not None else "  n/a "
        print(f"  {m['module']:<36s} {m['real']:>5d}/{m['total_tagged']:>5d}   {pct_str}")
    print(f"  {'-'*36} {'-'*5} {'-'*5}   {'-'*6}")
    tp = out['totals']['real_pct']
    tp_str = f"{tp:5.1f}%" if tp is not None else "  n/a "
    print(f"  {'TOTAL':<36s} {out['totals']['real']:>5d}/{grand_total:>5d}   {tp_str}\n")
    return out


if __name__ == "__main__":
    run()
