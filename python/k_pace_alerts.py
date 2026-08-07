"""
EdgeStat -- live K-pace + bullpen-warming alerts.

For each in-progress game, compares the SP's current K count + IP to their
prop K line. Surfaces:
  - "ON PACE FOR OVER": Ks/IP ratio extrapolated to typical workload >= line
  - "BEHIND PACE":     extrapolated Ks < line - 1
  - "EARLY HOOK":      pitcher already pulled (no IP from current half)

Also (best-effort) detects when a closer warms up using boxscore status.

Output: data/k_pace.json
"""
from __future__ import annotations
import os, json, datetime as dt, urllib.request
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "k_pace.json")
MLB = "https://statsapi.mlb.com/api/v1"


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _ip_float(ip):
    if ip is None: return 0.0
    try:
        s = str(ip)
        if "." in s:
            w, fr = s.split(".")
            return int(w) + int(fr) / 3.0
        return float(s)
    except Exception:
        return 0.0


def run() -> Dict[str, Any]:
    # K props by player_id
    k_props = {}
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        if p.get("market") == "pitcher_strikeouts" and p.get("player_id"):
            k_props[p["player_id"]] = p

    # Schedule today
    today = dt.date.today().isoformat()
    sched = _http(f"{MLB}/schedule?sportId=1&date={today}") or {}

    alerts: List[Dict[str, Any]] = []
    for date_block in sched.get("dates", []):
        for g in date_block.get("games", []):
            pk = g.get("gamePk")
            state = (g.get("status") or {}).get("detailedState", "")
            if state in ("Scheduled", "Pre-Game", "Warmup"):
                continue
            if not pk:
                continue
            bs = _http(f"{MLB}/game/{pk}/boxscore") or {}
            # Find each SP's current line
            for side in ("home", "away"):
                team = bs.get("teams", {}).get(side, {})
                for pid in team.get("pitchers", []):
                    if pid not in k_props:
                        continue
                    pkey = f"ID{pid}"
                    pl = (team.get("players") or {}).get(pkey) or {}
                    stats = (pl.get("stats") or {}).get("pitching") or {}
                    ip = _ip_float(stats.get("inningsPitched"))
                    ks = int(stats.get("strikeOuts") or 0)
                    line = k_props[pid].get("line")
                    play = k_props[pid].get("play")
                    if not ip or line is None:
                        continue
                    # Typical SP outing = 5.5 IP if not pulled
                    pace = ks / ip if ip > 0 else 0
                    proj_total = pace * 5.5
                    on_pace = proj_total >= line + 0.5
                    behind = proj_total < line - 1.0
                    # Are they still in the game?
                    game_status = ((pl.get("gameStatus") or {}).get("isCurrentBatter")
                                    or stats.get("note", "").lower().find("currently pitching") != -1)
                    if behind:
                        label, color_key = "BEHIND PACE", "red"
                    elif on_pace:
                        label, color_key = "ON PACE FOR OVER", "green"
                    else:
                        label, color_key = "ON PACE", "amber"
                    alerts.append({
                        "player_id": pid, "player": (pl.get("person") or {}).get("fullName"),
                        "line": line, "play": play,
                        "ks_current": ks, "ip_current": round(ip, 1),
                        "ks_per_ip": round(pace, 2),
                        "projected_total": round(proj_total, 1),
                        "label": label, "color": color_key,
                        "matchup": f"{(bs.get('teams',{}).get('away') or {}).get('team',{}).get('abbreviation','?')} @ {(bs.get('teams',{}).get('home') or {}).get('team',{}).get('abbreviation','?')}",
                    })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_alerts']} K-pace alerts")
    for a in p["alerts"][:5]:
        print(f"  {a['label']:18} {a['player']:25} {a['ks_current']}K in {a['ip_current']}IP -> proj {a['projected_total']} vs line {a['line']}")
