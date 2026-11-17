"""Cross-check The Board's DraftKings prices against ESPN's live feed right now (2026-11-16).

For every upcoming NFL / NBA / NHL game on data/board.json: fetch the same event from ESPN's public
scoreboard, and compare the moneylines. Flags
  SWAP   - the board's home price matches ESPN's AWAY price and vice versa (a side-mapping bug)
  TEAMS  - the board's home/away teams are not ESPN's home/away teams for that event id
  DRIFT  - a price differs by more than DRIFT_PTS of no-vig probability (expected between board runs;
           listed with the snapshot age so a stale board is visible)
  PICK   - a logged bet's team is not one of the two teams in its game
Read-only. Run from the repo root:  python tools/board_price_check.py     (exit 1 on SWAP/TEAMS/PICK)
"""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PATH = {"NFL": "football/nfl", "NBA": "basketball/nba", "NHL": "hockey/nhl"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36"
DRIFT_PTS = 3.0


def nv(h, a):
    try:
        h, a = float(h), float(a)
        ph = 100 / (h + 100) if h > 0 else -h / (-h + 100)
        pa = 100 / (a + 100) if a > 0 else -a / (-a + 100)
        return ph / (ph + pa)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def espn(sport, ymd):
    u = f"https://site.api.espn.com/apis/site/v2/sports/{PATH[sport]}/scoreboard?dates={ymd}"
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    out = {}
    for e in json.load(urllib.request.urlopen(req, timeout=20)).get("events") or []:
        c = (e.get("competitions") or [{}])[0]
        side = {t.get("homeAway"): (t.get("team") or {}).get("abbreviation") for t in c.get("competitors") or []}
        o = next((x for x in c.get("odds") or [] if "draft" in str((x.get("provider") or {}).get("name", "")).lower()),
                 (c.get("odds") or [None])[0]) or {}
        ml = o.get("moneyline") or {}
        cur = lambda k: ((ml.get(k) or {}).get("close") or {}).get("odds")
        out[str(e.get("id"))] = {"home": side.get("home"), "away": side.get("away"),
                                 "ml_home": cur("home"), "ml_away": cur("away"),
                                 "state": ((e.get("status") or {}).get("type") or {}).get("state")}
    return out


def num(v):
    try:
        return float(str(v).replace("+", "")) if str(v).upper() not in ("EVEN", "") else 100.0
    except (TypeError, ValueError):
        return None


def main():
    B = json.load(open(os.path.join(ROOT, "data", "board.json"), encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    games = [g for g in B.get("games") or [] if g.get("sport") in PATH and g.get("odds")]
    feeds, bad, n, priced = {}, 0, 0, 0
    for g in games:
        key = (g["sport"], g["date"].replace("-", ""))
        if key not in feeds:
            try:
                feeds[key] = espn(*key)
            except Exception as ex:                       # noqa: BLE001
                print(f"  ESPN {key} unavailable: {ex}")
                feeds[key] = {}
        e = feeds[key].get(str(g["id"]))
        if not e:
            continue
        n += 1
        o = g["odds"]
        tag = f"{g['sport']} {g['date']} {g['matchup']} (id {g['id']})"
        if (e["home"], e["away"]) != (g.get("home"), g.get("away")):
            bad += 1
            print(f"TEAMS {tag}: board {g.get('away')} @ {g.get('home')} vs ESPN {e['away']} @ {e['home']}")
            continue
        bh, ba, eh, ea = o.get("ml_home"), o.get("ml_away"), num(e["ml_home"]), num(e["ml_away"])
        if None in (bh, ba, eh, ea) or e["state"] != "pre":
            continue
        pb, pe, px = nv(bh, ba), nv(eh, ea), nv(ea, eh)
        if pb is None or pe is None:
            continue
        priced += 1
        if abs(pb - pe) * 100 > DRIFT_PTS and abs(pb - px) * 100 < 1.0:
            bad += 1
            print(f"SWAP  {tag}: board home {bh}/away {ba} vs ESPN home {eh:+.0f}/away {ea:+.0f}")
        elif abs(pb - pe) * 100 > DRIFT_PTS:
            age = ""
            try:
                age = f", board snapshot {int((now - dt.datetime.fromisoformat(o['observed_at']).replace(tzinfo=dt.timezone.utc)).total_seconds() // 60)} min old"
            except Exception:                              # noqa: BLE001
                pass
            print(f"DRIFT {tag}: board {ba}/{bh} vs ESPN now {ea:+.0f}/{eh:+.0f} ({(pe - pb) * 100:+.1f} pts{age})")
    for p in B.get("picks") or []:
        g = next((x for x in games if x["sport"] == p["sport"] and str(x["id"]) == str(p["event_id"])), None)
        if g and p.get("team") not in (g.get("home"), g.get("away")):
            bad += 1
            print(f"PICK  {p['sport']} {p.get('matchup')}: bet on {p.get('team')}, not a team in this game")
    print(f"checked {n} games against ESPN ({priced} pre-start prices compared); {bad} mapping errors")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
