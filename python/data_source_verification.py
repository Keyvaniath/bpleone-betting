"""
EdgeStat -- Data source verification.

Pings every external API we depend on, records:
  - Status (UP / DOWN / DEGRADED)
  - HTTP code + response time
  - Sample payload size + a few raw fields
  - Last-success timestamp

Output: data/data_source_health.json

This is the page Brandon checks to PROVE the data is real and live.
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
except Exception:
    Request = urlopen = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "data_source_health.json")

USER_AGENT = "Mozilla/5.0 EdgeStat/1.0 (research; betting.bpleone.com)"

# Each source: (label, sample-URL, sport, free)
SOURCES = [
    ("MLB Stats API (gumbo)",
     "https://statsapi.mlb.com/api/v1/schedule?sportId=1",
     "mlb", True),
    ("ESPN MLB scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
     "mlb", True),
    ("ESPN NHL scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
     "nhl", True),
    ("ESPN NBA scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
     "nba", True),
    ("ESPN WNBA scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
     "wnba", True),
    ("ESPN PGA Golf scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard",
     "golf", True),
    ("ESPN UFC scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard",
     "ufc", True),
    ("ESPN F1 scoreboard",
     "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard",
     "f1", True),
    ("Bovada MLB lines",
     "https://www.bovada.lv/services/sports/event/coupon/events/A/description/baseball/mlb",
     "mlb", True),
    ("Baseball Savant (Statcast)",
     "https://baseballsavant.mlb.com/leaderboard/custom?year=2025&type=batter&filter=&min=q&selections=ab_hr&chart=false&x=ab_hr&y=ab_hr&r=no&chartType=beeswarm",
     "mlb", True),
    ("PrizePicks projections",
     "https://api.prizepicks.com/projections?league_id=2",
     "props", True),
    ("Open-Meteo (weather)",
     "https://api.open-meteo.com/v1/forecast?latitude=40&longitude=-74&hourly=temperature_2m",
     "weather", True),
    ("Jolpica F1 (Ergast)",
     "https://api.jolpi.ca/ergast/f1/current.json",
     "f1", True),
    ("The Odds API",
     "https://api.the-odds-api.com/v4/sports",
     "odds_aggregator", False),
]


def _ping(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Ping a URL, return health blob."""
    if not urlopen:
        return {"status": "DOWN", "error": "urllib not available"}

    start = time.time()
    try:
        ua = "EdgeStat/1.0" if "espn.com" in url else USER_AGENT
        req = Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            elapsed_ms = int((time.time() - start) * 1000)
            code = r.getcode()
            data = r.read()
            size = len(data)
            # Parse a sample field if JSON
            sample = None
            try:
                obj = json.loads(data.decode("utf-8", errors="ignore"))
                if isinstance(obj, dict):
                    sample = {k: type(v).__name__ for k, v in list(obj.items())[:5]}
                elif isinstance(obj, list):
                    sample = {"_list_len": len(obj), "_first_keys":
                              list(obj[0].keys())[:5] if obj and isinstance(obj[0], dict) else None}
            except Exception:
                sample = {"_raw_size": size}
            status = "UP" if code == 200 else ("DEGRADED" if code < 500 else "DOWN")
            return {
                "status": status,
                "http_code": code,
                "response_ms": elapsed_ms,
                "payload_bytes": size,
                "sample": sample,
            }
    except HTTPError as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "DEGRADED" if e.code < 500 else "DOWN",
            "http_code": e.code,
            "response_ms": elapsed_ms,
            "error": str(e),
        }
    except (URLError, Exception) as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "DOWN",
            "http_code": None,
            "response_ms": elapsed_ms,
            "error": str(e)[:120],
        }


def _load_prev() -> Dict[str, Any]:
    if not os.path.exists(OUT): return {}
    try:
        with open(OUT) as f: return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    prev = _load_prev()
    prev_sources = {s["url"]: s for s in (prev.get("sources") or [])}

    rows: List[Dict[str, Any]] = []
    n_up, n_down, n_degraded = 0, 0, 0
    now = dt.datetime.utcnow().isoformat(timespec="seconds")

    for label, url, sport, is_free in SOURCES:
        # Skip The Odds API if we know there's no key
        skip = False
        if "the-odds-api" in url and not os.environ.get("ODDS_API_KEY"):
            health = {"status": "DEGRADED", "skip_reason": "ODDS_API_KEY not set"}
            skip = True
        else:
            health = _ping(url)

        prev_row = prev_sources.get(url, {})
        last_up = prev_row.get("last_up") or (now if health.get("status") == "UP" else None)
        if health.get("status") == "UP":
            last_up = now

        rows.append({
            "label": label,
            "url": url,
            "sport": sport,
            "is_free": is_free,
            "last_check": now,
            "last_up": last_up,
            **health,
        })

        if health["status"] == "UP": n_up += 1
        elif health["status"] == "DOWN": n_down += 1
        else: n_degraded += 1

    overall = "OK"
    if n_down >= 3 or n_up < len(rows) * 0.5:
        overall = "CRITICAL"
    elif n_down >= 1 or n_degraded >= 2:
        overall = "DEGRADED"

    out = {
        "generated_at": now,
        "overall_status": overall,
        "n_sources_checked": len(rows),
        "n_up": n_up,
        "n_degraded": n_degraded,
        "n_down": n_down,
        "sources": rows,
        "note": "Live verification of every external API EdgeStat depends on. Proof data is real-time.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[data-sources] {o['overall_status']}: {o['n_up']} UP, "
          f"{o['n_degraded']} DEGRADED, {o['n_down']} DOWN -> {OUT}")
