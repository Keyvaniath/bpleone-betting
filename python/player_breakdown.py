"""
EdgeStat -- per-player deep-dive precomputation.

Builds a single JSON keyed by player_id that powers the /player page.
For every player either (a) on tonight's slate OR (b) with at least 5
settled props in our track_record, computes:

  - Season + career counting stats (from MLB Stats API)
  - Vs L / vs R splits, home / away splits (from MLB Stats API)
  - Last 7 / 14 / 30 day form (from player_gamelogs.json)
  - Hot / cold delta (recent vs season -- "trending up", "cold spell", etc.)
  - Tonight's matchup context (from matchups.json):
      * BvP career H2H (AB / H / HR / BB / SO / slash line)
      * Pitch-arsenal xwOBA matchup breakdown
  - Model accuracy on this player: hit-rate, ROI, RMSE (from track_record.json)
  - Per-market accuracy: which of this player's prop markets the model is
    best / worst at predicting
  - Last 20 settled props (date / market / line / actual / play / hit)
  - Any active per-player bias override (from player_bias.json)

Output: data/player_breakdowns.json
  {
    "generated_at": "...",
    "n_players": 247,
    "by_id": {
      "592450": {
        "name": "Aaron Judge",
        "team": "NYY",
        "position": "RF",
        "hand": "R",
        "season": {...},
        "career": {...},
        "splits": { "vs_L": {...}, "vs_R": {...}, "home": {...}, "away": {...} },
        "form": { "last_7": {...}, "last_14": {...}, "last_30": {...}, "hot_cold": "+0.085 OPS vs season" },
        "tonight": {
          "vs_pitcher": "Aaron Nola",
          "bvp_career": { "ab": 12, "h": 4, "hr": 2, ... },
          "arsenal_xwoba": [ ... ]
        },
        "model_accuracy": {
          "n_props": 47, "hits": 28, "hit_rate": 0.596,
          "roi_pct": 6.8, "trust_tier": "trusted",
          "by_market": [...]
        },
        "recent_props": [...]
      }
    }
  }

The /player page reads this and renders the deep-dive in 6 distinct cards.
Falls back gracefully when sub-sections lack data.
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
GAMELOGS_PATH = os.path.join(DATA_DIR, "player_gamelogs.json")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
BIAS_PATH = os.path.join(DATA_DIR, "player_bias.json")
OUT_PATH = os.path.join(DATA_DIR, "player_breakdowns.json")

MLB_API = "https://statsapi.mlb.com/api/v1"
HTTP_TIMEOUT = 8
MIN_TR_PROPS = 5    # minimum settled props to qualify a player not on tonight's slate

try:
    import config as _cfg
    MAX_PLAYERS_API = _cfg.get("player_breakdown.max_players_api", 60)
except Exception:
    MAX_PLAYERS_API = 60


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _http_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_splits(player_id: int, group: str = "hitting") -> Dict[str, Any]:
    """Pull season + career + L/R + home/away splits from MLB Stats API.
    The MLB Stats API requires multiple calls because stat types and
    statSplits sitCodes can't all be combined. Returns {} on total failure --
    safe to fall through."""
    out: Dict[str, Any] = {}
    season = dt.date.today().year

    # 1) Season totals
    url = f"{MLB_API}/people/{player_id}/stats?stats=season&group={group}&season={season}&sportId=1"
    data = _http_json(url)
    if data and data.get("stats"):
        splits = data["stats"][0].get("splits") or []
        if splits:
            out["season"] = splits[-1].get("stat") or {}

    # 2) Career totals
    url = f"{MLB_API}/people/{player_id}/stats?stats=career&group={group}&sportId=1"
    data = _http_json(url)
    if data and data.get("stats"):
        splits = data["stats"][0].get("splits") or []
        if splits:
            out["career"] = splits[-1].get("stat") or {}

    # 3) L/R + home/away
    url = (f"{MLB_API}/people/{player_id}/stats?stats=statSplits&sitCodes=vl,vr,h,a"
           f"&group={group}&season={season}&sportId=1")
    data = _http_json(url)
    if data and data.get("stats"):
        for sp in data["stats"][0].get("splits") or []:
            code = (sp.get("split") or {}).get("code")
            stat = sp.get("stat") or {}
            if code == "vl":
                out["vs_L"] = stat
            elif code == "vr":
                out["vs_R"] = stat
            elif code == "h":
                out["home"] = stat
            elif code == "a":
                out["away"] = stat

    return out


def _fetch_year_by_year(player_id: int, group: str = "hitting") -> List[Dict[str, Any]]:
    """Year-over-year trend: last 3 seasons. Used for the YOY card."""
    url = f"{MLB_API}/people/{player_id}/stats?stats=yearByYear&group={group}&sportId=1"
    data = _http_json(url)
    if not data or not data.get("stats"):
        return []
    splits = (data["stats"][0].get("splits") or [])
    out = []
    for sp in splits[-3:]:   # last 3 seasons
        out.append({"season": sp.get("season"), **(sp.get("stat") or {})})
    return out


def _fetch_situational(player_id: int, group: str = "hitting") -> Dict[str, Any]:
    """Game-state splits: RISP / RISP+2outs / Late&Close / Leading off / Day / Night.
    Verified sitCodes (probed against the live API):
      risp  = Scoring Position
      risp2 = Scoring Position - 2 Outs
      lc    = Late / Close
      lo    = Leading Off Inning
      d     = Day Games
      n     = Night Games"""
    season = dt.date.today().year
    url = (f"{MLB_API}/people/{player_id}/stats?stats=statSplits"
           f"&sitCodes=risp,risp2,lc,lo,d,n&group={group}&season={season}&sportId=1")
    data = _http_json(url)
    if not data or not data.get("stats"):
        return {}
    out: Dict[str, Any] = {}
    for sp in data["stats"][0].get("splits") or []:
        code = (sp.get("split") or {}).get("code")
        desc = (sp.get("split") or {}).get("description")
        if not code:
            continue
        out[code] = {"description": desc, **(sp.get("stat") or {})}
    return out


def _fetch_lineup_spot(player_id: int, group: str = "hitting") -> Dict[str, Any]:
    """By batting-order position. sitCodes 1..9 = 1st through 9th in order."""
    season = dt.date.today().year
    url = (f"{MLB_API}/people/{player_id}/stats?stats=statSplits"
           f"&sitCodes=1,2,3,4,5,6,7,8,9&group={group}&season={season}&sportId=1")
    data = _http_json(url)
    if not data or not data.get("stats"):
        return {}
    out: Dict[str, Any] = {}
    for sp in data["stats"][0].get("splits") or []:
        code = (sp.get("split") or {}).get("code")
        if code in {"1","2","3","4","5","6","7","8","9"}:
            out[code] = sp.get("stat") or {}
    return out


def _pitch_type_from_arsenal(tonight: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pitch-type performance for tonight's batter matchup, derived from the
    arsenal_xwoba breakdown we already cache per batter in matchups.json.
    Each row: {pitch, pitcher_usage_pct, batter_xwoba_vs, pitcher_xwoba_allowed_overall}.

    MLB Stats API doesn't expose vs-pitch-type splits directly; this approach
    uses the Statcast-derived data already on the slate, which is more
    actionable anyway (it's specific to TONIGHT's pitcher, not all pitchers)."""
    if not tonight:
        return []
    ax = tonight.get("arsenal_xwoba") or {}
    return ax.get("breakdown") or []


def _ip_to_float(ip_val: Any) -> float:
    """Convert MLB 'X.Y' inning notation (where Y is outs/3) to a real float.
    '5.2' = 5 and 2/3 innings = 5.667. None / non-numeric -> 0."""
    if ip_val is None:
        return 0.0
    if isinstance(ip_val, (int, float)):
        return float(ip_val)
    s = str(ip_val).strip()
    try:
        if "." in s:
            whole, frac = s.split(".")
            return int(whole) + int(frac) / 3.0
        return float(s)
    except Exception:
        return 0.0


def _safe_num(g, key, default=0):
    v = g.get(key)
    return v if isinstance(v, (int, float)) else default


def _park_splits_from_gamelog(games: List[Dict[str, Any]], tonight_park: Optional[str], is_pitcher: bool = False) -> Dict[str, Any]:
    """Slice player_gamelogs by venue. With the enriched gamelog (PR #43), every
    row tags `venue`. Surfaces 'do they crush at THIS park or struggle?'."""
    if not games or not tonight_park:
        return {}
    here, away = [], []
    for g in games:
        venue = (g.get("venue") or g.get("park") or "").strip()
        if not venue:
            continue
        (here if venue.lower() == tonight_park.lower() else away).append(g)
    def _agg(rows):
        if not rows:
            return None
        if is_pitcher:
            ip = sum(_ip_to_float(g.get("ip")) for g in rows)
            er = sum(_safe_num(g, "er") for g in rows)
            k = sum(_safe_num(g, "k") for g in rows)
            bb = sum(_safe_num(g, "bb") for g in rows)
            return {"n_games": len(rows), "ip": round(ip, 1),
                    "era": round((er * 9) / ip, 2) if ip > 0 else None,
                    "k9":  round((k * 9) / ip, 2) if ip > 0 else None,
                    "bb9": round((bb * 9) / ip, 2) if ip > 0 else None}
        ab = sum(_safe_num(g, "ab") for g in rows)
        h = sum(_safe_num(g, "hits") for g in rows)
        hr = sum(_safe_num(g, "hr") for g in rows)
        tb = sum(_safe_num(g, "tb") for g in rows)
        return {"n_games": len(rows), "ab": ab, "h": h, "hr": hr, "tb": tb,
                "avg": round(h / ab, 3) if ab else None,
                "slg": round(tb / ab, 3) if ab else None,
                "hr_per_game": round(hr / len(rows), 3) if rows else None}
    return {"at_park": _agg(here), "at_other_parks": _agg(away),
            "park_name": tonight_park}


def _day_night_from_gamelog(games: List[Dict[str, Any]], is_pitcher: bool = False) -> Dict[str, Any]:
    """Day vs night splits from the enriched gamelog (`is_night` tag)."""
    if not games:
        return {}
    day_g, night_g = [], []
    for g in games:
        v = g.get("is_night")
        if v is True:  night_g.append(g)
        elif v is False: day_g.append(g)
    def _agg(rows):
        if not rows:
            return None
        if is_pitcher:
            ip = sum(_ip_to_float(g.get("ip")) for g in rows)
            er = sum(_safe_num(g, "er") for g in rows)
            k = sum(_safe_num(g, "k") for g in rows)
            return {"n": len(rows), "era": round((er * 9) / ip, 2) if ip > 0 else None,
                    "k9": round((k * 9) / ip, 2) if ip > 0 else None}
        ab = sum(_safe_num(g, "ab") for g in rows)
        h = sum(_safe_num(g, "hits") for g in rows)
        tb = sum(_safe_num(g, "tb") for g in rows)
        return {"n": len(rows), "ab": ab, "avg": round(h / ab, 3) if ab else None,
                "slg": round(tb / ab, 3) if ab else None}
    return {"day": _agg(day_g), "night": _agg(night_g)}


def _travel_from_gamelog(games: List[Dict[str, Any]], is_pitcher: bool = False) -> Dict[str, Any]:
    """Slice games by inter-game gap: 0-day (back-to-back), 1-day (normal),
    2+ day (rested). Plus day-after-night (early-arrival fatigue proxy)."""
    if not games:
        return {}
    dated = []
    for g in games:
        d = g.get("date")
        if not d:
            continue
        try:
            dt_o = dt.date.fromisoformat(d)
            dated.append((dt_o, g))
        except Exception:
            continue
    dated.sort(key=lambda x: x[0])
    b2b, normal, rested = [], [], []
    day_after_night = []
    for i in range(1, len(dated)):
        gap = (dated[i][0] - dated[i-1][0]).days
        g = dated[i][1]
        if gap == 0:        b2b.append(g)
        elif gap == 1:      normal.append(g)
        else:               rested.append(g)
        # day-after-night: yesterday was night, today is day
        prev_night = dated[i-1][1].get("is_night") is True
        today_day = dated[i][1].get("is_night") is False
        if prev_night and today_day and gap <= 1:
            day_after_night.append(g)
    def _agg(rows):
        if not rows:
            return None
        if is_pitcher:
            ip = sum(_ip_to_float(g.get("ip")) for g in rows)
            er = sum(_safe_num(g, "er") for g in rows)
            return {"n": len(rows), "era": round((er * 9) / ip, 2) if ip > 0 else None}
        ab = sum(_safe_num(g, "ab") for g in rows)
        h = sum(_safe_num(g, "hits") for g in rows)
        return {"n": len(rows), "ab": ab, "avg": round(h / ab, 3) if ab else None}
    return {
        "back_to_back": _agg(b2b),
        "normal_gap_1d": _agg(normal),
        "rested_2plus_d": _agg(rested),
        "day_after_night": _agg(day_after_night),
    }


def _vs_umpire_from_tr(tr_props: List[Dict[str, Any]], pid: int) -> List[Dict[str, Any]]:
    """If track_record records have an `ump` field (added at settle time --
    populated forward-looking from outcomes.py going forward), aggregate
    this player's hit rate by HP umpire. Returns sorted list of ump rows."""
    mine = [r for r in tr_props if r.get("player_id") == pid
            and r.get("ump") and (r.get("play_hit") is True or r.get("play_hit") is False)]
    if not mine:
        return []
    by_ump: Dict[str, Dict[str, int]] = {}
    for r in mine:
        u = r["ump"]
        if u not in by_ump:
            by_ump[u] = {"n": 0, "wins": 0}
        by_ump[u]["n"] += 1
        if r["play_hit"] is True:
            by_ump[u]["wins"] += 1
    rows = [{"ump": u, "n": v["n"], "wins": v["wins"],
              "hit_rate": round(v["wins"] / v["n"], 3) if v["n"] else None}
            for u, v in by_ump.items() if v["n"] >= 2]
    rows.sort(key=lambda x: -(x["hit_rate"] or 0))
    return rows[:10]


def _days_rest_for_pitcher(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """For pitchers: bucket starts by days-of-rest gap, then aggregate ERA / K9.
    Buckets: <=3 (short), 4 (normal), 5 (extra), 6+ (long)."""
    if not games:
        return {}
    dated = []
    for g in games:
        d = g.get("date") or g.get("game_date")
        if not d:
            continue
        try:
            dt_o = dt.date.fromisoformat(d)
            dated.append((dt_o, g))
        except Exception:
            continue
    dated.sort(key=lambda x: x[0])
    buckets: Dict[str, List[Dict[str, Any]]] = {"short": [], "normal": [], "extra": [], "long": []}
    for i in range(1, len(dated)):
        gap = (dated[i][0] - dated[i-1][0]).days
        g = dated[i][1]
        if gap <= 3:    buckets["short"].append(g)
        elif gap == 4:  buckets["normal"].append(g)
        elif gap == 5:  buckets["extra"].append(g)
        else:           buckets["long"].append(g)
    def _safe(g, key, d=0):
        v = g.get(key)
        return v if isinstance(v, (int, float)) else d
    out: Dict[str, Any] = {}
    for bucket_name, rows in buckets.items():
        if not rows:
            out[bucket_name] = None
            continue
        ip = sum(_ip_to_float(g.get("ip")) for g in rows)
        er = sum(_safe(g, "er") for g in rows)
        k = sum(_safe(g, "k") for g in rows)
        bb = sum(_safe(g, "bb") for g in rows)
        out[bucket_name] = {
            "n_starts": len(rows),
            "ip": round(ip, 1),
            "era": round((er * 9) / ip, 2) if ip > 0 else None,
            "k9":  round((k  * 9) / ip, 2) if ip > 0 else None,
            "bb9": round((bb * 9) / ip, 2) if ip > 0 else None,
        }
    return out


def _form_from_gamelog(games: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=days)
    recent: List[Dict[str, Any]] = []
    for g in games:
        d_str = g.get("date") or g.get("game_date")
        if not d_str:
            continue
        try:
            d = dt.date.fromisoformat(d_str)
        except Exception:
            continue
        if d >= cutoff:
            recent.append(g)
    if not recent:
        return {"n_games": 0}
    # Common batter aggregates (guard against None values)
    def _safe(g, key, default=0):
        v = g.get(key)
        return v if isinstance(v, (int, float)) else default
    pa = sum(_safe(g, "pa") for g in recent)
    ab = sum(_safe(g, "ab") for g in recent)
    h = sum(_safe(g, "hits") for g in recent)
    hr = sum(_safe(g, "hr") for g in recent)
    rbi = sum(_safe(g, "rbi") for g in recent)
    bb = sum(_safe(g, "bb") for g in recent)
    so = sum(_safe(g, "k") for g in recent)
    tb = sum(_safe(g, "tb") for g in recent)
    return {
        "n_games": len(recent),
        "ab": ab, "h": h, "hr": hr, "rbi": rbi, "bb": bb, "so": so, "tb": tb, "pa": pa,
        "avg": round(h / ab, 3) if ab else None,
        "obp": round((h + bb) / (ab + bb), 3) if (ab + bb) else None,
        "slg": round(tb / ab, 3) if ab else None,
        "k_rate": round(so / pa, 3) if pa else None,
        "bb_rate": round(bb / pa, 3) if pa else None,
        "hr_per_game": round(hr / len(recent), 3),
    }


def _form_from_pitcher_gamelog(games: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=days)
    recent: List[Dict[str, Any]] = []
    for g in games:
        d_str = g.get("date") or g.get("game_date")
        if not d_str:
            continue
        try:
            d = dt.date.fromisoformat(d_str)
        except Exception:
            continue
        if d >= cutoff:
            recent.append(g)
    if not recent:
        return {"n_starts": 0}
    starts = len(recent)
    def _safe(g, k, d=0):
        v = g.get(k)
        return v if isinstance(v, (int, float)) else d
    # ip can come as "5.2" string from MLB API; convert through _ip_to_float
    ip = sum(_ip_to_float(g.get("ip")) for g in recent)
    er = sum(_safe(g, "er") for g in recent)
    k = sum(_safe(g, "k") for g in recent)
    bb = sum(_safe(g, "bb") for g in recent)
    h = sum(_safe(g, "hits") for g in recent)
    return {
        "n_starts": starts,
        "ip": round(ip, 1), "er": er, "k": k, "bb": bb, "h": h,
        "era": round((er * 9) / ip, 2) if ip else None,
        "k9":  round((k  * 9) / ip, 2) if ip else None,
        "bb9": round((bb * 9) / ip, 2) if ip else None,
        "whip": round((h + bb) / ip, 2) if ip else None,
    }


def _hot_cold_label(recent: Dict[str, Any], season: Dict[str, Any], kind: str) -> str:
    """Produce a one-line trend descriptor."""
    if kind == "pitcher":
        r_era = recent.get("era")
        s_era = (season or {}).get("era")
        if r_era is None or s_era is None:
            return ""
        try:
            s_era_f = float(s_era)
        except Exception:
            return ""
        delta = r_era - s_era_f
        if delta < -0.6:
            return f"hot: {r_era} ERA recent vs {s_era_f:.2f} season"
        if delta > 0.6:
            return f"cold: {r_era} ERA recent vs {s_era_f:.2f} season"
        return f"steady: {r_era} recent vs {s_era_f:.2f} season"
    # Batter -- use OPS proxy via slg + obp
    r_obp = recent.get("obp")
    r_slg = recent.get("slg")
    s_ops_str = (season or {}).get("ops")
    if r_obp is None or r_slg is None or s_ops_str is None:
        return ""
    r_ops = r_obp + r_slg
    try:
        s_ops = float(s_ops_str)
    except Exception:
        return ""
    delta = r_ops - s_ops
    if delta > 0.080:
        return f"heating up: {r_ops:.3f} OPS recent vs {s_ops:.3f} season ({delta:+.3f})"
    if delta < -0.080:
        return f"cooling: {r_ops:.3f} OPS recent vs {s_ops:.3f} season ({delta:+.3f})"
    return f"steady: {r_ops:.3f} recent vs {s_ops:.3f} season"


def _player_accuracy(tr_props: List[Dict[str, Any]], pid: int) -> Dict[str, Any]:
    mine = [r for r in tr_props if r.get("player_id") == pid
            and (r.get("play_hit") is True or r.get("play_hit") is False)]
    if not mine:
        return {"n_props": 0}
    wins = sum(1 for r in mine if r["play_hit"] is True)
    # ROI flat 1u
    def payout(price):
        if price is None:
            return 0
        return price / 100 if price >= 0 else 100 / abs(price)
    net = 0.0
    for r in mine:
        price = r.get("dk_over") if r.get("play") == "OVER" else r.get("dk_under") if r.get("play") == "UNDER" else -110
        if r["play_hit"] is True:
            net += payout(price if price is not None else -110)
        else:
            net -= 1
    n = len(mine)
    hit_rate = wins / n
    roi = (net / n) * 100
    by_market: Dict[str, Dict[str, Any]] = {}
    for r in mine:
        mk = r.get("market") or "?"
        if mk not in by_market:
            by_market[mk] = {"n": 0, "wins": 0}
        by_market[mk]["n"] += 1
        if r["play_hit"] is True:
            by_market[mk]["wins"] += 1
    by_market_arr = sorted(
        [{"market": m, "n": s["n"], "hit_rate": round(s["wins"] / s["n"], 3) if s["n"] else None}
         for m, s in by_market.items()],
        key=lambda x: -(x["hit_rate"] or 0),
    )
    # Trust tier
    if n >= 20 and hit_rate >= 0.58:
        tier = "trusted"
    elif n >= 20 and hit_rate <= 0.45:
        tier = "untrusted"
    elif n >= 8:
        tier = "watch"
    else:
        tier = "unproven"
    return {
        "n_props": n, "hits": wins, "hit_rate": round(hit_rate, 3),
        "net_units": round(net, 2), "roi_pct": round(roi, 2),
        "trust_tier": tier, "by_market": by_market_arr,
    }


def _tonight_for_player(matchups: Dict[str, Any], pid: int, name: str) -> Optional[Dict[str, Any]]:
    """Find tonight's matchup card for this player + return BvP + arsenal info."""
    for g in matchups.get("games") or []:
        for side in ("home", "away"):
            lineup = (g.get("lineups") or {}).get(side) or []
            for b in lineup:
                if b.get("id") == pid or b.get("name") == name:
                    opp = "home_pitcher" if side == "away" else "away_pitcher"
                    op = g.get(opp) or {}
                    return {
                        "matchup": g.get("matchup"),
                        "park": g.get("park"),
                        "game_time": g.get("time"),
                        "vs_pitcher": op.get("name"),
                        "vs_pitcher_id": op.get("id"),
                        "vs_pitcher_hand": op.get("hand"),
                        "lineup_order": b.get("order"),
                        "position": b.get("pos"),
                        "bvp_career": b.get("vs_pitcher_career") or {},
                        "arsenal_xwoba": b.get("vs_pitcher_xwoba_matchup") or {},
                    }
        # Pitcher side
        for p_side in ("home_pitcher", "away_pitcher"):
            p = g.get(p_side) or {}
            if p.get("id") == pid or p.get("name") == name:
                # This player IS the pitcher tonight
                opp_side = "away" if p_side == "home_pitcher" else "home"
                opp_lineup = (g.get("lineups") or {}).get(opp_side) or []
                return {
                    "matchup": g.get("matchup"),
                    "park": g.get("park"),
                    "game_time": g.get("time"),
                    "is_starting_pitcher": True,
                    "season_stats": p.get("season") or {},
                    "career_stats": p.get("career") or {},
                    "arsenal": p.get("arsenal") or [],
                    "narrative": p.get("narrative") or [],
                    "opposing_lineup": [{"name": b.get("name"), "id": b.get("id"),
                                          "order": b.get("order"), "pos": b.get("pos")}
                                          for b in opp_lineup[:9]],
                }
    return None


def run() -> Dict[str, Any]:
    today = _load(TODAY_PATH)
    matchups = _load(MATCHUPS_PATH)
    props_data = _load(PROPS_PATH)
    pickem = _load(PICKEM_PATH)
    gamelogs = _load(GAMELOGS_PATH)
    tr = _load(TR_PATH)
    bias = _load(BIAS_PATH)
    bias_map = bias.get("by_pid_market") or {}

    # Gather player IDs we care about
    player_ids: Dict[int, Dict[str, Any]] = {}

    # From tonight's matchups (lineups + starting pitchers)
    for g in matchups.get("games") or []:
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                pid = b.get("id")
                if pid:
                    player_ids[pid] = {"name": b.get("name"), "team": None,
                                        "kind": "batter", "on_slate": True}
        for p_side in ("home_pitcher", "away_pitcher"):
            p = g.get(p_side) or {}
            if p.get("id"):
                player_ids[p["id"]] = {"name": p.get("name"), "team": None,
                                        "kind": "pitcher", "on_slate": True}

    # From open props
    for p in ((props_data.get("top_edges") or []) + (pickem.get("props") or [])):
        pid = p.get("player_id")
        if pid and pid not in player_ids:
            player_ids[pid] = {"name": p.get("player"), "team": p.get("team"),
                                "kind": "pitcher" if (p.get("market") or "").startswith("pitcher_") else "batter",
                                "on_slate": True}
        elif pid and pid in player_ids and not player_ids[pid].get("team"):
            player_ids[pid]["team"] = p.get("team")

    # From track record (players with 5+ settled props -- even if not on slate)
    tr_props = tr.get("props") or []
    counts: Dict[int, int] = {}
    name_by_id: Dict[int, str] = {}
    for r in tr_props:
        pid = r.get("player_id")
        if not pid:
            continue
        counts[pid] = counts.get(pid, 0) + 1
        if pid not in name_by_id:
            name_by_id[pid] = r.get("player") or ""
    for pid, n in counts.items():
        if n >= MIN_TR_PROPS and pid not in player_ids:
            player_ids[pid] = {"name": name_by_id.get(pid, ""), "team": None,
                                "kind": "batter", "on_slate": False}

    gl_by_id = gamelogs.get("by_player_id") or {}

    by_id: Dict[str, Dict[str, Any]] = {}
    # API fetch budget: only spend on players on tonight's slate (limited)
    api_budget = MAX_PLAYERS_API
    for pid, meta in player_ids.items():
        kind = meta.get("kind") or "batter"
        glog = gl_by_id.get(str(pid)) or gl_by_id.get(pid) or {}
        games = glog.get("games") or []
        if kind == "pitcher":
            form_7 = _form_from_pitcher_gamelog(games, 7)
            form_14 = _form_from_pitcher_gamelog(games, 14)
            form_30 = _form_from_pitcher_gamelog(games, 30)
        else:
            form_7 = _form_from_gamelog(games, 7)
            form_14 = _form_from_gamelog(games, 14)
            form_30 = _form_from_gamelog(games, 30)
        # API pulls -- only on slate AND within budget. Each on-slate player
        # consumes 1 budget unit but triggers up to 4 API endpoints (splits,
        # yoy, situational, lineup-spot, pitch-type). MLB Stats API is fast
        # enough that batching this way is fine.
        splits: Dict[str, Any] = {}
        yoy: List[Dict[str, Any]] = []
        situational: Dict[str, Any] = {}
        lineup_spot: Dict[str, Any] = {}
        if meta.get("on_slate") and api_budget > 0:
            group = "pitching" if kind == "pitcher" else "hitting"
            splits = _fetch_splits(pid, group) or {}
            yoy = _fetch_year_by_year(pid, group) or []
            situational = _fetch_situational(pid, group) or {}
            lineup_spot = _fetch_lineup_spot(pid, group) or {}
            api_budget -= 1
        season = splits.get("season") or {}
        hot_cold = _hot_cold_label(form_14, season, kind)
        tonight = _tonight_for_player(matchups, pid, meta.get("name") or "") if meta.get("on_slate") else None
        # Pitch-type performance: derived from cached arsenal_xwoba in tonight's matchup
        pitch_type = _pitch_type_from_arsenal(tonight)
        # Pitcher rest buckets (gamelog-only, no API)
        rest_buckets = _days_rest_for_pitcher(games) if kind == "pitcher" else {}
        # NEW: park splits from enriched gamelog
        tonight_park = (tonight or {}).get("park")
        park_splits = _park_splits_from_gamelog(games, tonight_park, is_pitcher=(kind == "pitcher"))
        # NEW: day vs night splits from enriched gamelog
        day_night = _day_night_from_gamelog(games, is_pitcher=(kind == "pitcher"))
        # NEW: travel + back-to-back from gamelog date gaps
        travel = _travel_from_gamelog(games, is_pitcher=(kind == "pitcher"))
        # NEW: vs-umpire from track_record (requires ump field on settled props)
        vs_ump = _vs_umpire_from_tr(tr_props, pid)
        acc = _player_accuracy(tr_props, pid)
        # Active per-player bias override (if any)
        biases = []
        for k, v in bias_map.items():
            if v.get("player_id") == pid:
                biases.append({"market": v.get("market"), "boost_factor": v.get("boost_factor"),
                                "z_score": v.get("z_score"), "n": v.get("n"), "note": v.get("note")})
        # Last 20 settled props (chronological)
        mine = [r for r in tr_props if r.get("player_id") == pid]
        mine = sorted(mine, key=lambda r: r.get("date") or "", reverse=True)[:20]
        by_id[str(pid)] = {
            "id": pid,
            "name": meta.get("name"),
            "team": meta.get("team"),
            "kind": kind,
            "on_slate": meta.get("on_slate", False),
            "season":  season,
            "career":  splits.get("career") or {},
            "splits": {
                "vs_L": splits.get("vs_L") or {},
                "vs_R": splits.get("vs_R") or {},
                "home": splits.get("home") or {},
                "away": splits.get("away") or {},
            },
            "form": {
                "last_7":  form_7,
                "last_14": form_14,
                "last_30": form_30,
                "hot_cold": hot_cold,
            },
            "tonight": tonight,
            "year_by_year": yoy,
            "situational": situational,
            "lineup_spot": lineup_spot,
            "pitch_type": pitch_type,
            "days_rest": rest_buckets,
            "park_splits": park_splits,
            "day_night_gamelog": day_night,
            "travel": travel,
            "vs_umpire": vs_ump,
            "model_accuracy": acc,
            "recent_props": mine,
            "active_bias_overrides": biases,
        }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_players": len(by_id),
        "api_budget_used": MAX_PLAYERS_API - api_budget,
        "by_id": by_id,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_players']} players")
    print(f"  api_budget_used: {p['api_budget_used']}")
    on_slate = sum(1 for v in p['by_id'].values() if v.get('on_slate'))
    print(f"  on tonight's slate: {on_slate}")
    trusted = sum(1 for v in p['by_id'].values() if (v.get('model_accuracy') or {}).get('trust_tier') == 'trusted')
    print(f"  trusted (model has 58%+ hit rate, n>=20): {trusted}")
