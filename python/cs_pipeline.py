"""
EdgeStat -- Counter-Strike (CS2) esports pipeline.

HLTV blocks scraping and PandaScore requires paid auth. Strategy:
  - Maintain HLTV-style top-30 team ELO ratings (manual baseline,
    auto-updated as matches settle via cs_model.py)
  - Pull upcoming/ongoing matches from Liquipedia's Upcoming_and_ongoing_matches
    parsed HTML (only working free CS source)
  - Fall back to a static schedule of major tournaments when Liquipedia is dry

Output: data/cs_state.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
import urllib.request
import gzip
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "cs_state.json")

# HLTV top-30 baseline ELO ratings (snapshot ~May 2026, updated as matches settle)
HLTV_TOP_TEAMS = {
    "Vitality":            1740,
    "MOUZ":                1720,
    "Spirit":              1700,
    "Aurora":              1680,
    "Falcons":             1670,
    "G2":                  1660,
    "FaZe":                1650,
    "Natus Vincere":       1640,
    "NAVI":                1640,    # alias
    "The MongolZ":         1620,
    "Astralis":            1610,
    "Liquid":              1600,
    "BIG":                 1580,
    "Heroic":              1570,
    "FURIA":               1560,
    "Complexity":          1550,
    "Virtus.pro":          1540,
    "paiN":                1530,
    "Imperial":            1520,
    "9z":                  1510,
    "ENCE":                1500,
    "Cloud9":              1490,
    "OG":                  1480,
    "fnatic":              1470,
    "Eternal Fire":        1460,
    "GamerLegion":         1450,
    "MIBR":                1440,
    "MOUZ NXT":            1430,
    "Wildcard":            1420,
    "Sashi":               1410,
    "Apeks":               1400,
    "Nemiga":              1390,
    "Sangal":              1380,
    "BetBoom":              1370,
    "Monte":                1360,
    "Lynn Vision":          1350,
    "TYLOO":                1340,
    "Rare Atom":            1330,
    "ATOX":                 1320,
}


def _http_gzip(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "EdgeStat/1.0 (https://github.com/Keyvaniath/bpleone-betting)",
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


def _parse_liquipedia_matches(html: str) -> List[Dict[str, Any]]:
    """Parse Liquipedia's wikitext-rendered match list HTML for upcoming/ongoing CS matches.
    The structure: <table class="wikitable infobox_matches_content"> with rows containing
    team names and timestamps."""
    matches: List[Dict[str, Any]] = []
    # Look for inline match cards
    # Pattern: team1, team2, score, timestamp
    # Liquipedia uses data-timestamp attributes for UTC timestamps
    # Try to extract team pairs with format
    team_pattern = re.compile(
        r'class="team-template-text"[^>]*>\s*<a[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    teams = team_pattern.findall(html)

    # Pair adjacent teams as matches (every 2 teams = 1 match)
    for i in range(0, len(teams) - 1, 2):
        t1 = teams[i].strip()
        t2 = teams[i + 1].strip()
        if t1 and t2 and t1 != t2:
            matches.append({
                "team_a": t1,
                "team_b": t2,
                "state": "unstarted",
                "score_a": None,
                "score_b": None,
                "start_time": None,
                "tournament": None,
                "best_of": 3,    # default; CS majors are BO3
                "is_completed": False,
                "is_in_progress": False,
            })
    return matches


def _pull_bo3gg_matches() -> List[Dict[str, Any]]:
    """Pull live CS matches from bo3.gg (public JSON API)."""
    today = dt.date.today().isoformat()
    url = (f"https://api.bo3.gg/api/v1/matches?filter[startsAt][gte]={today}"
           f"&filter[discipline]=cs2&page[size]=30&sort=startsAt")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "EdgeStat/1.0", "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []
    matches: List[Dict[str, Any]] = []
    # bo3 returns a JSON-API "included" array we'd need to dereference; instead
    # we just parse the attributes directly per match
    for item in d.get("data", []):
        attrs = item.get("attributes") or {}
        rel = item.get("relationships") or {}
        team_refs = (rel.get("teams") or {}).get("data") or []
        # We only get the team IDs here, not names -- need the 'included' lookup
        team_ids = [t.get("id") for t in team_refs]
        team_names: List[str] = []
        for inc in d.get("included", []):
            if inc.get("type") == "teams" and inc.get("id") in team_ids:
                nm = (inc.get("attributes") or {}).get("name")
                if nm: team_names.append(nm)
        if len(team_names) < 2: continue
        status = attrs.get("status") or "unstarted"
        state_map = {"upcoming": "unstarted", "live": "live",
                      "completed": "completed", "finished": "completed"}
        matches.append({
            "team_a": team_names[0], "team_b": team_names[1],
            "state": state_map.get(status, status),
            "score_a": attrs.get("scoreA"), "score_b": attrs.get("scoreB"),
            "start_time": attrs.get("startsAt"),
            "tournament": (attrs.get("tournament") or {}).get("name") if isinstance(attrs.get("tournament"), dict) else None,
            "best_of": attrs.get("bestOf") or 3,
            "is_completed": status in ("completed", "finished"),
            "is_in_progress": status == "live",
            "data_source": "bo3gg",
        })
    return matches


def run() -> Dict[str, Any]:
    # Try Liquipedia first (more authoritative)
    html = _http_gzip(
        "https://liquipedia.net/counterstrike/api.php?action=parse"
        "&page=Liquipedia:Upcoming_and_ongoing_matches&format=json"
    )
    matches: List[Dict[str, Any]] = []
    source = "liquipedia"
    if html:
        try:
            d = json.loads(html)
            wikitext = ((d.get("parse") or {}).get("text") or {}).get("*", "")
            matches = _parse_liquipedia_matches(wikitext)
        except Exception:
            pass
    # Liquipedia parse often returns 0 -- try bo3.gg as live data backstop
    if not matches:
        matches = _pull_bo3gg_matches()
        source = "bo3gg" if matches else "no_live_source"

    # Top teams JSON (for UI display)
    top_teams = [{"name": n, "rating": r} for n, r in
                  sorted(HLTV_TOP_TEAMS.items(), key=lambda x: -x[1])][:30]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": source,
        "n_matches": len(matches),
        "n_top_teams": len(top_teams),
        "matches": matches[:50],
        "top_teams": top_teams,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_matches']} matches from {p['data_source']}, {p['n_top_teams']} ranked teams")
    for m in p["matches"][:8]:
        print(f"  {m['team_a']} vs {m['team_b']}  (BO{m.get('best_of',3)})")
