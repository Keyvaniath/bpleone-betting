"""Build data/ml_reprice_2026_10d.json -- every settled MLB total (working ledger +
archive) checked against the lines books actually posted BEFORE first pitch.

WHY (2026-10-26): the 10/26 pass only voided Play-of-the-Day totals on the 8.5
placeholder. Top 25 and the Under Alerts read the same today.json total, and
POD's Bovada fallback could grab an in-play total ("UNDER 15.5", "OVER 4.5").
Half the curated totals were graded on a line DraftKings never posted; the
fake 8.5 manufactured UNDER edges whenever the real total was 6.5-7.

Evidence, all from git history:
  * DraftKings pre-game totals + juice  -- data/espn_odds.json (status "pre")
  * Odds API pre-game polling           -- data/odds_history.json
  * multi-book board (Bovada, DK)       -- data/multi_book_lines.json; a line
    counts only if a snapshot showing it was committed before first pitch.

Classes -> status in the seed:
  same               line == DK total at the pick's snapshot -> repriced_total
                     (graded at DK's real over/under juice, the house standard)
  dk_other_snapshot / oddsapi / bovada_pregame / no_dk -> not in the seed
                     (a real line some book posted pre-game, or no evidence:
                     kept as recorded, same rule as the 10/26 moneylines)
  never_posted / bovada_inplay -> unposted_total (voided: no book posted that
                     line pre-game, so the bet has no honest result)

Usage: python tools/build_total_lines_audit.py  [--report out.json]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO, "data", "ml_reprice_2026_10d.json")


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
            out.append((h, (u - dt.timedelta(hours=4)).date().isoformat(), u))
    return out


def _show(h, path):
    try:
        return json.loads(subprocess.run(["git", "-C", REPO, "show", f"{h}:{path}"],
                                         capture_output=True).stdout.decode("utf-8"))
    except Exception:
        return None


def _et_date(ct):
    return (ct - dt.timedelta(hours=4)).date().isoformat()


def _ct(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _dec(a):
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def main(report=None):
    L = _load("data/all_picks_ledger.json")["picks"]
    A = _load("data/ledger_archive.json").get("picks") or []
    C, seen_ids = [], set()
    for origin, rows in (("L", L), ("A", A)):
        for p in rows:
            if (p.get("sport") == "MLB" and str(p.get("market", "")).startswith(("OVER_", "UNDER_"))
                    and p.get("settled") and not p.get("voided") and p.get("pick_id") not in seen_ids
                    and p.get("result") in ("won", "lost", "push")):
                seen_ids.add(p["pick_id"])
                C.append((origin, p))
    want = {(str(p.get("player_or_matchup") or ""), str(p["date"])[:10]) for _, p in C}
    days = {d for _, d in want}
    near = days | {(dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat() for d in days}
    print("settled MLB totals", len(C))

    # DraftKings pre-game snapshots, keyed by (matchup, ET date of first pitch)
    dk = defaultdict(list)
    for h, d, u in _commits("data/espn_odds.json"):
        if d not in near and (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat() not in near:
            continue
        o = _show(h, "data/espn_odds.json") or {}
        ga = str(o.get("generated_at"))[:19]
        for g in o.get("games") or []:
            ct = _ct(g.get("commence_time"))
            if g.get("sport") != "MLB" or not g.get("market") or g.get("status") != "pre" or not ct:
                continue
            k = (g.get("matchup"), _et_date(ct))
            if k in want:
                dk[k].append((ga, ct, g["market"]))
    # Odds API history (accumulating file: last snapshot per day is enough)
    oa, done = defaultdict(set), set()
    for h, d, u in _commits("data/odds_history.json"):
        if d not in days or d in done:
            continue
        done.add(d)
        for k, rows in ((_show(h, "data/odds_history.json") or {}).get("history") or {}).items():
            sp, mu, gd = (k.split("|") + ["", "", ""])[:3]
            if sp == "MLB" and (mu, gd) in want:
                oa[(mu, gd)].update(float(x["total"]) for x in rows if x.get("total") is not None)
    # Multi-book board, with commit time (compared to first pitch below)
    mb = defaultdict(list)
    for h, d, u in _commits("data/multi_book_lines.json"):
        if d not in days:
            continue
        for row in (_show(h, "data/multi_book_lines.json") or {}).get("rows") or []:
            k = (row.get("matchup"), d)
            if k in want:
                for b, v in (row.get("books") or {}).items():
                    if v.get("total_line") is not None:
                        mb[k].append((u, b, float(v["total_line"])))

    rows = []
    for origin, p in C:
        side, line = p["market"].split("_", 1)
        line = float(line)
        k = (str(p.get("player_or_matchup") or ""), str(p["date"])[:10])
        pre = sorted(dk.get(k, []), key=lambda s: s[0])
        rec = str(p.get("recorded_at") or "")[:19]
        before = [s for s in pre if s[0] <= rec]
        snap = before[-1] if before else (pre[0] if pre else None)
        m = snap[2] if snap else {}
        start = min((s[1] for s in pre), default=None)
        dk_total = m.get("total")
        dk_all = sorted({s[2].get("total") for s in pre if s[2].get("total") is not None})
        mb_pre = any(l == line and start and u < start for u, b, l in mb.get(k, []))
        mb_any = any(l == line for u, b, l in mb.get(k, []))
        if dk_total is None:
            cls = "no_dk"
        elif line == dk_total:
            cls = "same"
        elif line in dk_all:
            cls = "dk_other_snapshot"
        elif line in oa.get(k, ()):
            cls = "oddsapi"
        elif mb_pre:
            cls = "bovada_pregame"
        elif mb_any:
            cls = "bovada_inplay"
        else:
            cls = "never_posted"
        r = {"pick_id": p["pick_id"], "origin": origin, "date": k[1], "matchup": k[0],
             "market": p["market"], "source": p.get("source"), "old_fair": p.get("fair_american"),
             "result": p.get("result"), "old_payout": p.get("payout_units"), "cls": cls,
             "dk_total": dk_total, "dk_totals_pregame": dk_all, "oddsapi_totals": sorted(oa.get(k, ())),
             "snapshot_at": snap[0] if snap else None, "chosen": ("before_pick" if before else
                                                                  ("first_pregame_after" if pre else None))}
        px = m.get("over_price" if side == "OVER" else "under_price")
        if cls == "same" and px is not None:
            r["status"] = "repriced_total"
            r["book_american"] = px
            r["new_payout"] = (round(_dec(px) - 1, 4) if r["result"] == "won"
                               else (-1.0 if r["result"] == "lost" else 0.0))
        elif cls in ("never_posted", "bovada_inplay"):
            r["status"] = "unposted_total"
            r["real_total"] = dk_total
        rows.append(r)

    if report:
        with open(report, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
    c = Counter(r["cls"] for r in rows)
    for name in c:
        b = [r for r in rows if r["cls"] == name]
        print(f"  {name:18s} n={len(b):3d} recorded {sum(float(r['old_payout'] or 0) for r in b):+7.2f}u",
              dict(Counter(r["source"] for r in b)))
    seed = [r for r in rows if r.get("status")]
    rp = [r for r in seed if r["status"] == "repriced_total"]
    print(f"seed: {len(rp)} repriced ({sum(float(r['old_payout'] or 0) for r in rp):+.2f}u -> "
          f"{sum(r['new_payout'] for r in rp):+.2f}u), "
          f"{sum(1 for r in seed if r['status'] == 'unposted_total')} voided")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"note": ("2026-10-26 totals pass: every settled MLB total checked against the lines "
                            "books posted before first pitch (DK espn_odds.json, Odds API odds_history.json, "
                            "multi_book_lines.json -- all from git history). repriced_total = the line was "
                            "DraftKings' and is graded at DK's real juice; unposted_total = no book posted "
                            "the line pre-game (pipeline 8.5 placeholder or an in-play total) -> voided. "
                            "Built by tools/build_total_lines_audit.py."),
                   "n": len(seed), "classes": dict(c), "rows": seed}, f, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[a.index("--report") + 1] if "--report" in a else None)
