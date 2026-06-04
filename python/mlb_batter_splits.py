"""
EdgeStat -- MLB batter HOME/AWAY + PLATOON (vsL/vsR) split multipliers (shared).

The batter prop generators price off a batter's recent form and the park, but
ignore two real, already-collected splits:
  - HOME / AWAY  -- data/mlb_batter_advanced_splits.json: each batter's home and
    away Bayesian-shrunk AVG/SLG/OPS + K%/BB%.
  - PLATOON vsL/vsR -- data/mlb_batter_lvr_splits.json: each batter's OPS vs
    TODAY'S opposing starter hand (split_ops over split_pa).
This turns them into a small, auditable multiplier on the batter's projected
power rate, so a road masher on the road and a lefty-killer facing a LHP get
shaded the way a sharp would.

CLEAN BASELINE. We deliberately do NOT use lvr's `season_ops_estimate` -- it is a
last-14 proxy that collapses to a 0.5 floor for ~40% of batters (see the spawned
fix). The per-batter neutral is the PA-weighted mean of the batter's advanced
home/away shrunk split; if that batter is missing we fall back to the league
prior in the advanced file (~.726 OPS / ~.409 SLG). The platoon OPS is shrunk
toward that neutral by PA (80-PA prior) before forming a ratio, so a hot 60-PA
split can't swing the projection.

Both axes are independent of the park factor the generators already apply (this
is the batter-SPECIFIC residual skew), so multiplying does not double-count.
Everything degrades to 1.0 when the batter is absent from the split files, so
missing data leaves the projection untouched. Coefficients are module constants
for multiplier_tuner.py to grid-search as outcomes accumulate.

Usage (load once per run, then per batter):
    import mlb_batter_splits as _SPL
    spl = _SPL.load(DATA_DIR)
    tb_per_pa *= spl.power_mult(name, side == "home")
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional, Tuple

PLATOON_PRIOR_PA = 80      # shrink a vsL/vsR OPS split toward the batter's neutral
HA_DAMP = 0.6              # home/away SLG deviation is partly park/noise -> damp it
PLATOON_DAMP = 0.8        # platoon is already PA-shrunk; a light extra damp
POWER_CLAMP = (0.88, 1.14)
RATE_PRIOR_PA = 120        # shrink a home/away K%/BB% split toward the batter's overall

LEAGUE_OPS = 0.726
LEAGUE_SLG = 0.409


def _load_json(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _num(x) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


class BatterSplits:
    def __init__(self, adv_idx: Dict[str, Any], lvr_idx: Dict[str, Any],
                 league_ops: float, league_slg: float):
        self.adv = adv_idx
        self.lvr = lvr_idx
        self.league_ops = league_ops
        self.league_slg = league_slg

    # -- neutral per-batter baseline: PA-weighted home/away shrunk (ops, slg) --
    def _neutral(self, key: str) -> Tuple[float, float]:
        b = self.adv.get(key)
        if not b:
            return self.league_ops, self.league_slg
        sp = b.get("splits") or {}
        h, a = sp.get("home") or {}, sp.get("away") or {}
        hp, ap = _num(h.get("pa")) or 0.0, _num(a.get("pa")) or 0.0
        def wavg(field, league):
            hv, av = _num(h.get(field)), _num(a.get(field))
            if hv is not None and av is not None and (hp + ap) > 0:
                return (hp * hv + ap * av) / (hp + ap)
            return hv if hv is not None else av if av is not None else league
        return wavg("ops_shrunk", self.league_ops), wavg("slg_shrunk", self.league_slg)

    def _home_away_slg_mult(self, key: str, is_home: bool) -> float:
        b = self.adv.get(key)
        if not b:
            return 1.0
        sp = b.get("splits") or {}
        venue = sp.get("home" if is_home else "away") or {}
        vslg = _num(venue.get("slg_shrunk"))
        _, neutral_slg = self._neutral(key)
        if vslg is None or not neutral_slg:
            return 1.0
        raw = vslg / neutral_slg
        return 1.0 + HA_DAMP * (raw - 1.0)

    def _platoon_ops_mult(self, key: str) -> float:
        row = self.lvr.get(key)
        if not row:
            return 1.0
        split_ops = _num(row.get("split_ops"))
        split_pa = _num(row.get("split_pa")) or 0.0
        if split_ops is None or split_pa <= 0:
            return 1.0
        neutral_ops, _ = self._neutral(key)
        if not neutral_ops:
            return 1.0
        # shrink the split OPS toward the batter's neutral by PA
        shrunk = (split_pa * split_ops + PLATOON_PRIOR_PA * neutral_ops) / (split_pa + PLATOON_PRIOR_PA)
        raw = shrunk / neutral_ops
        return 1.0 + PLATOON_DAMP * (raw - 1.0)

    def power_mult(self, name: str, is_home: bool) -> float:
        """Combined home/away (SLG) x platoon (OPS) multiplier on a power rate
        (TB / HRR / XBH). 1.0 if the batter is absent from the split files."""
        key = (name or "").strip().lower()
        if not key:
            return 1.0
        m = self._home_away_slg_mult(key, is_home) * self._platoon_ops_mult(key)
        return round(_clamp(m, *POWER_CLAMP), 4)

    # -- real measured rate (K% / BB%) for the batter's venue, PA-regularized --
    def _venue_rate(self, key: str, is_home: bool, field: str) -> Optional[float]:
        """The batter's home (or away) split rate for `field` (k_rate/bb_rate),
        regularized by PA toward the batter's overall home+away rate. None if the
        batter isn't in the advanced-splits file (caller keeps its own fallback)."""
        b = self.adv.get(key)
        if not b:
            return None
        sp = b.get("splits") or {}
        h, a = sp.get("home") or {}, sp.get("away") or {}
        hv, av = _num(h.get(field)), _num(a.get(field))
        hp, ap = _num(h.get("pa")) or 0.0, _num(a.get("pa")) or 0.0
        venue = h if is_home else a
        vv, vp = _num(venue.get(field)), _num(venue.get("pa")) or 0.0
        if vv is None:
            vv, vp = (hv if hv is not None else av), 0.0
        if vv is None:
            return None
        if hv is not None and av is not None and (hp + ap) > 0:
            overall = (hp * hv + ap * av) / (hp + ap)   # batter's real overall rate
        else:
            overall = vv
        return (vp * vv + RATE_PRIOR_PA * overall) / (vp + RATE_PRIOR_PA)

    def k_rate(self, name: str, is_home: bool) -> Optional[float]:
        """Batter's real (venue, PA-regularized) strikeout rate per PA, or None."""
        return self._venue_rate((name or "").strip().lower(), is_home, "k_rate")

    def bb_rate(self, name: str, is_home: bool) -> Optional[float]:
        """Batter's real (venue, PA-regularized) walk rate per PA, or None."""
        return self._venue_rate((name or "").strip().lower(), is_home, "bb_rate")

    def breakdown(self, name: str, is_home: bool) -> Dict[str, Any]:
        key = (name or "").strip().lower()
        row = self.lvr.get(key) or {}
        return {
            "home_away_slg_mult": round(self._home_away_slg_mult(key, is_home), 4),
            "platoon_ops_mult": round(self._platoon_ops_mult(key), 4),
            "opp_hand": row.get("opp_hand"),
            "in_adv": key in self.adv,
            "in_lvr": key in self.lvr,
        }


def load(data_dir: str) -> BatterSplits:
    adv = _load_json(os.path.join(data_dir, "mlb_batter_advanced_splits.json"))
    lvr = _load_json(os.path.join(data_dir, "mlb_batter_lvr_splits.json"))
    adv_idx = {(b.get("name") or "").strip().lower(): b
               for b in (adv.get("batters") or []) if b.get("name")}
    lvr_idx = {(b.get("batter") or "").strip().lower(): b
               for b in (lvr.get("all_batters") or []) if b.get("batter")}
    pri = adv.get("priors") or {}
    return BatterSplits(adv_idx, lvr_idx,
                        _num(pri.get("ops")) or LEAGUE_OPS,
                        _num(pri.get("slg")) or LEAGUE_SLG)


if __name__ == "__main__":
    import sys
    dd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data")
    spl = load(dd)
    print(f"loaded adv={len(spl.adv)} lvr={len(spl.lvr)} league_ops={spl.league_ops} league_slg={spl.league_slg}")
    shown = 0
    for key in list(spl.adv.keys()):
        for is_home in (True, False):
            bd = spl.breakdown(key, is_home)
            if bd["in_lvr"]:
                print(f"  {key:24} home={is_home!s:5} power_mult={spl.power_mult(key, is_home):.4f}  {bd}")
                shown += 1
                break
        if shown >= 8:
            break
