"""Build data/pod_pl_regrade_2026_10.json -- grades for Play-of-the-Day entries in
data/pod_pl.json that have NO row in the graded ledger.

WHY (2026-10-26): pod_pl.json ("the primary track record", on the homepage and
/pod-history) graded itself: matchup-string matching against a rolling
historical_mlb window (3 of 47 ledger-matched results were wrong -- e.g.
9/01 CHW ML "won" when CHW lost 3-6), its own recorded prices (in-play +940,
placeholder +100/-110, 8.5 totals), and it recorded the off-day DEMO_SLATE game
(CIN @ COL -110) as real PODs. From 10/26 pod_pl mirrors the ledger row for each
POD; this seed covers the entries the ledger never carried.

Method, per entry (all from git history, exact ids, no string guessing):
  1. DraftKings pre-game snapshot for (matchup, ET date of first pitch) from
     espn_odds.json -> ESPN event_id + the DK moneyline / total + juice.
  2. Final score for that event_id from historical_mlb.json's history.
  3. ML  -> graded at the DK pre-game moneyline.
     TOT -> graded at DK's juice when the line is DK's; voided when DK's total
            was a different number (the 10/26 totals rule: a line nobody
            posted has no honest result).
  No DK game that day (DEMO_SLATE, All-Star) -> voided 'no real game'.
  Game found but no final on record -> voided 'unverifiable'.

Usage: python tools/build_pod_pl_regrade.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO, "data", "pod_pl_regrade_2026_10.json")


def _load(p):
    with open(os.path.join(REPO, p), encoding="utf-8") as f:
        return json.load(f)


def _commits(path):
    log = subprocess.run(["git", "-C", REPO, "log", "--format=%H %cI", "--", path],
                         capture_output=True, text=True).stdout.split("\n")
    out = []
    for l in log:
        if l.strip():
            h, t = l.split()
            u = dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc)
            out.append((h, (u - dt.timedelta(hours=4)).date().isoformat()))
    return out


def _show(h, path):
    try:
        return json.loads(subprocess.run(["git", "-C", REPO, "show", f"{h}:{path}"],
                                         capture_output=True).stdout.decode("utf-8"))
    except Exception:
        return None


def _dec(a):
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def ledger_index():
    """(date, matchup, market) of every ledger row a POD maps to (source pod, or
    a curated row that absorbed the POD via also_sources)."""
    rows = _load("data/all_picks_ledger.json")["picks"] + (_load("data/ledger_archive.json").get("picks") or [])
    return {(str(p.get("date"))[:10], p.get("player_or_matchup"), p.get("market"))
            for p in rows if p.get("source") == "pod" or "pod" in (p.get("also_sources") or [])}


def main():
    have = ledger_index()
    todo = [h for h in _load("data/pod_pl.json").get("history") or []
            if (h.get("date"), h.get("matchup"), h.get("label")) not in have
            and h.get("date") < dt.date.today().isoformat()]
    want = {(h["matchup"], h["date"]) for h in todo}
    days = {d for _, d in want}
    print("pod_pl entries without a ledger row:", len(todo))

    dk = defaultdict(list)
    for h, d in _commits("data/espn_odds.json"):
        nd = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
        if d not in days and nd not in days:
            continue
        o = _show(h, "data/espn_odds.json") or {}
        ga = str(o.get("generated_at"))[:19]
        for g in o.get("games") or []:
            try:
                ct = dt.datetime.fromisoformat(str(g.get("commence_time")).replace("Z", "+00:00"))
            except Exception:
                continue
            k = (g.get("matchup"), (ct - dt.timedelta(hours=4)).date().isoformat())
            if g.get("sport") == "MLB" and k in want and g.get("status") == "pre" and g.get("market"):
                dk[k].append((ga, g.get("event_id"), g["market"]))
    rec = {(e["matchup"], e["date"]): str(e.get("recorded_at") or "")[:19] for e in todo}
    pick = {}
    for k, snaps in dk.items():   # last pre-game line at/before the pick, else the first after
        snaps.sort(key=lambda s: s[0])
        before = [s for s in snaps if s[0] <= rec.get(k, "")]
        s0 = before[-1] if before else snaps[0]
        pick[k] = (s0[1], s0[2])
    dk = pick
    ids = {str(v[0]) for v in dk.values()}
    finals = {}
    for h, d in _commits("data/historical_mlb.json"):
        for g in (_show(h, "data/historical_mlb.json") or {}).get("games") or []:
            if str(g.get("id")) in ids and g.get("home_score") is not None:
                finals.setdefault(str(g["id"]), g)
        if len(finals) == len(ids):
            break

    verified = defaultdict(set)
    led = _load("data/all_picks_ledger.json")["picks"] + (_load("data/ledger_archive.json").get("picks") or [])
    for p in led:
        o = p.get("outcome")
        k = (p.get("player_or_matchup"), str(p.get("date"))[:10])
        if p.get("sport") == "MLB" and isinstance(o, dict) and o.get("final_score") and k in want:
            mm = re.fullmatch(r"\s*(\S+)\s+(\d+)\s*@\s*(\S+)\s+(\d+)\s*", o["final_score"])
            if mm:
                verified[k].add((int(mm.group(2)), int(mm.group(4))))
    rows = []
    for e in todo:
        k = (e["matchup"], e["date"])
        lab = e["label"]
        r = {"date": e["date"], "matchup": e["matchup"], "label": lab,
             "recorded_price": e.get("market_price"), "old_result": e.get("result"),
             "old_payout": e.get("payout_units")}
        if k not in dk:
            r.update(status="void", reason="no real game: no sportsbook listed this matchup that day "
                                           "(off-day demo slate / exhibition)")
            rows.append(r)
            continue
        eid, m = dk[k]
        g = finals.get(str(eid)) if eid else None
        r["event_id"] = eid
        if g:
            hs, as_ = g["home_score"], g["away_score"]
            r["final_source"] = "historical_mlb event_id"
        else:
            # Older snapshots carry no event_id: use the ledger's VERIFIED final for
            # the same game-date (outcome.final_score on any graded row); two
            # different finals = a doubleheader we cannot pin -> void.
            fs = verified.get(k) or set()
            if len(fs) != 1:
                r.update(status="void", reason=("unverifiable: doubleheader, two finals on record" if fs
                                                else "unverifiable: no final score on record for the game"))
                rows.append(r)
                continue
            as_, hs = next(iter(fs))
            r["final_source"] = "ledger verified final"
        r["final"] = f"{e['matchup'].split(' @ ')[0]} {as_} @ {e['matchup'].split(' @ ')[1]} {hs}"
        if lab.endswith("_ML"):
            team = lab[:-3]
            away, home = [x.strip() for x in e["matchup"].split("@")]
            side = "home" if team == home else ("away" if team == away else None)
            px = m.get("ml_home" if side == "home" else "ml_away") if side else None
            if px is None:
                r.update(status="void", reason="no DraftKings pre-game moneyline on record")
            else:
                won = (hs > as_) if side == "home" else (as_ > hs)
                r.update(status="graded", book_american=px, result="won" if won else "lost",
                         payout_units=round(_dec(px) - 1, 4) if won else -1.0)
        else:
            side, line = lab.split("_", 1)
            line = float(line)
            tot = m.get("total")
            px = m.get("over_price" if side == "OVER" else "under_price")
            if tot is None or float(tot) != line:
                r.update(status="void", real_total=tot,
                         reason=f"unposted total: DraftKings' pre-game total was {tot}, not {line}")
            else:
                t = hs + as_
                res = "push" if t == line else ("won" if (t > line) == (side == "OVER") else "lost")
                px = px if px is not None else -110
                r.update(status="graded", book_american=px, result=res,
                         payout_units=(round(_dec(px) - 1, 4) if res == "won" else (-1.0 if res == "lost" else 0.0)))
        rows.append(r)

    c = Counter((r["status"], r.get("result")) for r in rows)
    print(dict(c))
    g = [r for r in rows if r["status"] == "graded"]
    print(f"graded {len(g)}: {sum(r['result'] == 'won' for r in g)}-{sum(r['result'] == 'lost' for r in g)} "
          f"{sum(r['payout_units'] for r in g):+.2f}u")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"note": ("2026-10-26: grades for pod_pl entries with no row in the graded ledger -- "
                            "exact ESPN event ids from DraftKings pre-game snapshots, finals from "
                            "historical_mlb.json, DK prices; built by tools/build_pod_pl_regrade.py."),
                   "n": len(rows), "rows": rows}, f, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
