"""
EdgeStat -- canonical market taxonomy.

The same bet is surfaced under several names across modules and books, so the
learning loop FRAGMENTS it. A batter "to hit a HR (1+)" shows up as `1_plus_hr`,
`to_hit_hr_yes`, `pp_batter_home_runs`, AND the DraftKings key `batter_home_runs`
-- four families, one bet, learned four separate times (and none of the per-source
weights match a displayed candidate). This maps every variant to ONE canonical
key `mlb_<stat>_<line>_<side>` so:
  * self-learning pools all the evidence for a bet into a single weight,
  * the board can match a displayed candidate to its learned weight directly,
  * prop CLV (keyed by DK market) can join the ledger (keyed by module names).

SCOPE (deliberately narrow to stay safe): MLB batter/pitcher props, where the
cross-naming duplication actually lives. Game lines (ML / total / spread), other
sports, and anything we can't confidently parse fall through to the caller's
existing line-stripping normalization UNCHANGED -- so no existing family's stats
move unless it is a genuine duplicate of another.

Design rule that protects the learning signal: the LINE and SIDE are always
preserved. 1+ HR (over 0.5) and 2+ HR (over 1.5) are different bets and stay in
different canonical families; over and under never merge. Only same-stat /
same-line / same-side variants pool.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# "1+"-style yes/no props that ALWAYS sit on a 0.5 line (count >= 1). When such a
# market carries no explicit number we can safely assume the 0.5 line.
_ONE_PLUS_STATS = {"hr", "hit", "run", "rbi", "walk", "bk", "xbh"}
# Variable-line stats: only canonicalize when an explicit line is present; with no
# line we leave the line as "na" so we never mis-pool a 1.5-line bet with a 0.5.
_VARIABLE_LINE_STATS = {"tb", "hrr", "pk", "ph"}

_WORD_NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}


def _detect_stat(m: str) -> Optional[str]:
    """Identify the MLB prop stat from a lowercased market string, specific
    tokens first so 'hrr' beats 'hr' and 'pitcher_strikeouts' beats batter K."""
    if "hrr" in m:
        return "hrr"
    if "total_base" in m or "total_bases" in m or re.search(r"(^|_)tb(_|$)", m) or "plus_tb" in m:
        return "tb"
    # Pitcher K: explicit "pitcher", OR an over/under K line (batter K is only
    # ever the 1+ prop -- "k_over_4.5"/"k_under_5.5" lines are always pitchers).
    if (("pitcher" in m and ("strikeout" in m or re.search(r"(^|_)k(_|$)", m) or "_ks" in m))
            or re.search(r"(^|_)k_(over|under)", m)):
        return "pk"
    if ("hits_allowed" in m or "h_allowed" in m
            or re.search(r"(^|_)h_(over|under)", m)):
        return "ph"
    if "home_run" in m or "hit_hr" in m or re.search(r"(^|_)hr(_|$)", m):
        return "hr"
    if "xbh" in m or "extra_base" in m:
        return "xbh"
    if "record_hit" in m or "plus_hit" in m or re.search(r"(^|_)hits?(_|$)", m):
        return "hit"
    if "rbi" in m:
        return "rbi"
    if "score_run" in m or "runs_scored" in m or re.search(r"(^|_)runs?(_|$)", m):
        return "run"
    if "walk" in m or re.search(r"(^|_)bb(_|$)", m):
        return "walk"
    # batter strikeout is ONLY the 1+ prop (pitcher K over/under handled above)
    if "k_1plus" in m or "batter_strikeout" in m or re.search(r"(^|_)k_1plus", m):
        return "bk"
    return None


def _detect_side(m: str) -> Optional[str]:
    """over / under (yes==over, no==under). None when the name carries no side."""
    if re.search(r"(^|_)(no|under)(_|$)", m):
        return "under"
    if re.search(r"(^|_)(yes|over)(_|$)", m):
        return "over"
    return None


def _detect_line(m: str) -> Optional[float]:
    """The betting line. 'N_plus' -> N-0.5 (1+ -> 0.5); 'over_3.5'/'under_4.5' ->
    that number; bare yes/no -> 0.5. None when no line is determinable."""
    plus = re.search(r"(\d+)_?plus", m)
    if plus:
        return int(plus.group(1)) - 0.5
    num = re.search(r"(over|under)_?(\d+(?:\.\d+)?)", m)
    if num:
        return float(num.group(2))
    trail = re.search(r"_(\d+(?:\.\d+)?)$", m)
    if trail:
        return float(trail.group(1))
    return None


def canonical_components(market: str) -> Optional[Tuple[str, float, str]]:
    """(stat, line, side) for a recognized MLB prop, else None."""
    if not market:
        return None
    m = str(market).strip().lower().replace(" ", "_")
    for w, d in _WORD_NUM.items():           # one_plus -> 1_plus
        m = re.sub(rf"(^|_){w}_plus", rf"\g<1>{d}_plus", m)

    stat = _detect_stat(m)
    if stat is None:
        return None

    side = _detect_side(m)
    line = _detect_line(m)

    if line is None:
        if stat in _ONE_PLUS_STATS:
            line = 0.5                        # 1+ is the only line for these
        else:
            return None                       # variable-line stat w/o a line: don't guess

    if side is None:
        side = "over"                         # the surfaced bet is the over/yes by default

    return stat, line, side


def canonical_market(market: str, sport: Optional[str] = None) -> Optional[str]:
    """Canonical `mlb_<stat>_<line>_<side>` for a duplicated MLB prop, else None.

    Returns None (NOT a guess) for game lines, non-MLB sports, and unparseable
    markets -- the caller should fall back to its existing family normalization
    for those, so only genuine duplicates are pooled."""
    if sport and str(sport).upper() not in ("MLB", ""):
        return None
    comp = canonical_components(market)
    if comp is None:
        return None
    stat, line, side = comp
    line_s = f"{line:g}"                       # 0.5 -> "0.5", 1.5 -> "1.5"
    return f"mlb_{stat}_{line_s}_{side}"


# DraftKings prop-market keys (from props.json) -> the same canonical key, so prop
# CLV (keyed by DK market) joins the ledger. DK keys are always the 1+ / standard
# line for the yes side unless the row carries its own line (handled by caller).
_DK_TO_CANON = {
    "batter_home_runs": "mlb_hr_0.5_over",
    "batter_hits": "mlb_hit_0.5_over",
    "batter_runs_scored": "mlb_run_0.5_over",
    "batter_rbis": "mlb_rbi_0.5_over",
    "batter_walks": "mlb_walk_0.5_over",
}


def canonical_from_dk(dk_market: str, side: str = "over") -> Optional[str]:
    """Map a DraftKings market key + side to the canonical family (for prop CLV)."""
    base = _DK_TO_CANON.get((dk_market or "").strip().lower())
    if not base:
        return None
    if side == "under":
        return base.rsplit("_", 1)[0] + "_under"
    return base


if __name__ == "__main__":
    tests = ["1_plus_hr", "to_hit_hr_yes", "pp_batter_home_runs", "batter_home_runs",
             "2_plus_total_bases", "one_plus_tb", "3_plus_hrr", "pp_batter_hrr_under_3.5",
             "k_1plus_yes", "to_score_run_no", "walk_1plus_no", "ml_home", "over_8.5",
             "to_record_hit_no", "to_record_hit_yes", "1_plus_hit"]
    for t in tests:
        print(f"  {t:32s} -> {canonical_market(t)}")
