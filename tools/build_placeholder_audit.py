"""Build data/ml_reprice_2026_11e.json -- every SETTLED pick still graded at a
placeholder price, re-priced at a real pre-game book price or voided.

WHY (2026-11-03, Brandon: "the odds must be perfect"): the grader falls back to
-110 (decimal 1.91) when a pick has no price, and several boards stamped a flat
fair_american -110 when the line was missing. The 10/23-10/26 passes fixed MLB
moneylines and the totals that matched DraftKings' line at the pick's own
snapshot, but kept "as recorded" the totals whose line was real at another
snapshot / another book, the props, and everything with no evidence: 210
settled picks (199 MLB, 11 World Cup) were still graded at -110.

Placeholder = no price at all, or fair_american == -110 with no book price AND
a model probability that is not ~52.4% (a model whose fair price really is
-110 is left alone).

Evidence, all from git history, PRE-GAME only (snapshot no later than
max(recorded_at, game day 15:59 UTC) -- before any MLB first pitch):
  * DraftKings (house standard) -- data/espn_odds.json, status "pre"
  * Odds API polling            -- data/odds_history.json (over/under, ml)
  * multi-book board (Bovada)   -- data/multi_book_lines.json
A total is re-priced only on a snapshot showing that exact line; a moneyline on
the side's price. No real price on record (all player props: no sportsbook prop
history exists) -> voided, never graded at an invented number.

Writes the seed (applied by ml_reprice.apply_ledger on every ledger build) and
applies it to data/ledger_archive.json directly (the archive is not rebuilt).

Usage: python tools/build_placeholder_audit.py [--dry]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO, "data", "ml_reprice_2026_11e.json")
ARCHIVE = os.path.join(REPO, "data", "ledger_archive.json")


def _load(p):
    with open(os.path.join(REPO, p), encoding="utf-8") as f:
        return json.load(f)


def _commits(path):
    out = []
    for l in subprocess.run(["git", "-C", REPO, "log", "--format=%H %cI", "--", path],
                            capture_output=True, text=True).stdout.split("\n"):
        if l.strip():
            h, t = l.split()
            out.append((h, dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc)))
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


def _utc(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


CURATED = ("lock_of_day", "top_25_board", "whale_", "consensus_hit", "sharp_", "mlb_under_alert", "pod")


def curated_model_priced(p) -> bool:
    """2026-11-03 (second pass): a CURATED MLB game line (moneyline / total)
    graded at the model's own fair price because no book price was stamped --
    the curated record is graded at the house price, so it needs a real one."""
    cur = str(p.get("source", "")).startswith(CURATED) or any(str(x).startswith(CURATED) for x in p.get("also_sources") or [])
    mk = str(p.get("market") or "")
    game = mk.startswith(("OVER_", "UNDER_")) or "ml" in mk.lower()
    return (cur and game and p.get("sport") == "MLB" and p.get("book_american") is None
            and p.get("fair_american") is not None and not placeholder(p))


def placeholder(p) -> bool:
    b, f = p.get("book_american"), p.get("fair_american")
    if b is not None:
        return False
    if f is None:
        return True
    if f != -110:
        return False
    pr = p.get("prob")
    try:
        return not (abs(float(pr) - 0.5238) <= 0.02)
    except (TypeError, ValueError):
        return True


def _ml_side(p):
    m = str(p.get("market") or "").lower()
    if "ml_home" in m or m in ("home ml", "home_ml"):
        return "home"
    if "ml_away" in m or m in ("away ml", "away_ml"):
        return "away"
    t = re.fullmatch(r"([a-z]{2,4})_ml", m)
    mu = str(p.get("player_or_matchup") or "")
    if t and "@" in mu:
        aw, hm = [x.strip().lower() for x in mu.split("@", 1)]
        if hm.startswith(t.group(1)) or t.group(1).startswith(hm):
            return "home"
        if aw.startswith(t.group(1)) or t.group(1).startswith(aw):
            return "away"
    return None


def main(dry=False):
    L = _load("data/all_picks_ledger.json")["picks"]
    A = _load("data/ledger_archive.json").get("picks") or []
    cand, seen = [], set()
    for origin, rows in (("L", L), ("A", A)):
        for p in rows:
            if p.get("pick_id") in seen:
                continue
            seen.add(p.get("pick_id"))
            if p.get("voided") or p.get("repriced") or p.get("result") not in ("won", "lost", "push"):
                continue
            if origin == "L" and not p.get("settled"):
                continue
            if placeholder(p) or curated_model_priced(p):
                cand.append((origin, p))
    print("placeholder-priced settled picks:", len(cand), Counter(p.get("sport") for _, p in cand))

    mlb = [(o, p) for o, p in cand if p.get("sport") == "MLB"]
    want = {str(p.get("player_or_matchup") or "") for _, p in mlb}
    days = {str(p["date"])[:10] for _, p in mlb}
    near = days | {(dt.date.fromisoformat(d) + dt.timedelta(days=k)).isoformat() for d in days for k in (-1, 1)}

    # DraftKings snapshots: (matchup, ET game day) -> [(snapshot utc, market)]
    dk = defaultdict(list)
    start_of = defaultdict(set)
    for h, u in _commits("data/espn_odds.json"):
        if (u - dt.timedelta(hours=4)).date().isoformat() not in near:
            continue
        o = _show(h, "data/espn_odds.json") or {}
        for g in o.get("games") or []:
            ct = _utc(g.get("commence_time"))
            if g.get("sport") != "MLB" or not ct or g.get("matchup") not in want:
                continue
            start_of[(g["matchup"], (ct - dt.timedelta(hours=4)).date().isoformat())].add(ct)
            if g.get("status") != "pre":
                continue
            if u <= ct:
                dk[(g["matchup"], (ct - dt.timedelta(hours=4)).date().isoformat())].append((u, g.get("market") or {}))
    # Odds API: accumulating per-game snapshot trail
    oa = defaultdict(list)
    done = set()
    for h, u in _commits("data/odds_history.json"):
        d = (u - dt.timedelta(hours=4)).date().isoformat()
        if d not in near or d in done:
            continue
        done.add(d)
        for k, rows in ((_show(h, "data/odds_history.json") or {}).get("history") or {}).items():
            sp, mu, gd = (k.split("|") + ["", "", ""])[:3]
            if sp != "MLB" or mu not in want:
                continue
            for x in rows:
                t = _utc(x.get("ts"))
                if t:
                    oa[(mu, gd)].append((t, x))
    # Multi-book board: commit time = snapshot time
    mb = defaultdict(list)
    for h, u in _commits("data/multi_book_lines.json"):
        d = (u - dt.timedelta(hours=4)).date().isoformat()
        if d not in days:
            continue
        for row in (_show(h, "data/multi_book_lines.json") or {}).get("rows") or []:
            if row.get("matchup") in want:
                for b, v in (row.get("books") or {}).items():
                    mb[(row["matchup"], d)].append((u, b, v))

    rows = []
    for origin, p in cand:
        r = {"pick_id": p["pick_id"], "origin": origin, "sport": p.get("sport"), "source": p.get("source"),
             "kind": "model_fair" if curated_model_priced(p) else "placeholder",
             "date": str(p["date"])[:10], "matchup": p.get("player_or_matchup"), "market": p.get("market"),
             "old_fair": p.get("fair_american"), "result": p.get("result"), "old_payout": p.get("payout_units")}
        price, book, at = None, None, None
        if p.get("sport") == "MLB":
            gd = r["date"]
            rec = _utc(p.get("recorded_at")) or dt.datetime.fromisoformat(gd + "T00:00:00+00:00")
            # never past first pitch: DK's commence time when any DK snapshot of
            # the game exists, else 16:00 UTC (noon ET, before every MLB game) --
            # Bovada / Odds API rows carry no game time, and a pick recorded late
            # must not pick up an in-play line (LAA @ MIA 8/7: 22:37Z vs 22:40Z)
            starts = [s0 for s0 in start_of.get((r["matchup"], gd), [])]
            first_pitch = min(starts) if starts else dt.datetime.fromisoformat(gd + "T16:00:00+00:00")
            cutoff = min(max(rec, dt.datetime.fromisoformat(gd + "T15:59:00+00:00")),
                         first_pitch - dt.timedelta(minutes=5))
            mk = str(p.get("market") or "")
            tot = re.fullmatch(r"(OVER|UNDER)_(\d+(?:\.\d+)?)", mk)
            side = _ml_side(p)
            nxt = (dt.date.fromisoformat(gd) + dt.timedelta(days=1)).isoformat()

            def pick_snap(snaps):
                snaps = sorted(snaps, key=lambda s: s[0])
                before = [s for s in snaps if s[0] <= cutoff]
                return before[-1] if before else None

            if tot:
                ou, line = tot.group(1), float(tot.group(2))
                s = pick_snap([(u, m) for u, m in dk.get((r["matchup"], gd), [])
                               if m.get("total") is not None and float(m["total"]) == line
                               and m.get("over_price" if ou == "OVER" else "under_price") is not None])
                if s:
                    price, book, at = s[1]["over_price" if ou == "OVER" else "under_price"], "draftkings", s[0]
                if price is None:
                    s = pick_snap([(t, x) for key in ((r["matchup"], gd), (r["matchup"], nxt))
                                   for t, x in oa.get(key, [])
                                   if x.get("total") is not None and float(x["total"]) == line
                                   and x.get("over" if ou == "OVER" else "under") is not None])
                    if s:
                        price, book, at = s[1]["over" if ou == "OVER" else "under"], "odds_api", s[0]
                if price is None:
                    s = pick_snap([(u, v) for u, b, v in mb.get((r["matchup"], gd), [])
                                   if v.get("total_line") is not None and float(v["total_line"]) == line
                                   and v.get("total_over" if ou == "OVER" else "total_under") is not None])
                    if s:
                        price, book, at = s[1]["total_over" if ou == "OVER" else "total_under"], "bovada", s[0]
            elif side:
                key = "ml_home" if side == "home" else "ml_away"
                s = pick_snap([(u, m) for u, m in dk.get((r["matchup"], gd), []) if m.get(key) is not None])
                if s:
                    price, book, at = s[1][key], "draftkings", s[0]
                if price is None:
                    s = pick_snap([(t, x) for k2 in ((r["matchup"], gd), (r["matchup"], nxt))
                                   for t, x in oa.get(k2, []) if x.get(key) is not None])
                    if s:
                        price, book, at = s[1][key], "odds_api", s[0]
                if price is None:
                    s = pick_snap([(u, v) for u, b, v in mb.get((r["matchup"], gd), [])
                                   if v.get(side + "_ml") is not None])
                    if s:
                        price, book, at = s[1][side + "_ml"], "bovada", s[0]
        if price is not None:
            r.update(status="repriced_book", book_american=price, book=book,
                     snapshot_at=at.isoformat(timespec="seconds"),
                     new_payout=(round(_dec(price) - 1, 4) if r["result"] == "won"
                                 else (-1.0 if r["result"] == "lost" else 0.0)))
        else:
            r.update(status="unpriced_bet", new_payout=None)
        rows.append(r)

    c = Counter((r["status"], r.get("book")) for r in rows)
    print(dict(c))
    rp = [r for r in rows if r["status"] == "repriced_book"]
    vd = [r for r in rows if r["status"] == "unpriced_bet"]
    print(f"repriced {len(rp)}: {sum(float(r['old_payout'] or 0) for r in rp):+.2f}u -> "
          f"{sum(r['new_payout'] for r in rp):+.2f}u | voided {len(vd)} "
          f"(recorded {sum(float(r['old_payout'] or 0) for r in vd):+.2f}u, "
          f"{sum(r['result'] == 'won' for r in vd)}-{sum(r['result'] == 'lost' for r in vd)})")
    if dry:
        return rows
    try:
        prior = _load("data/ml_reprice_2026_11e.json").get("rows") or []
    except Exception:
        prior = []
    have = {r["pick_id"] for r in rows}
    seed = [r for r in prior if r["pick_id"] not in have] + rows      # append-only
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"note": ("2026-11-03 placeholder pass: every settled pick still graded at a placeholder "
                            "-110 (or no price) re-priced at a real pre-game book price from git history "
                            "(DraftKings first, then Odds API, then Bovada; exact line for totals), or voided "
                            "when no real price is on record (all player props). Built by "
                            "tools/build_placeholder_audit.py."),
                   "n": len(seed), "rows": seed}, f, indent=1)
    # The archive is not rebuilt by the ledger: apply to it here.
    arch = _load("data/ledger_archive.json")
    by = {r["pick_id"]: r for r in seed if r["origin"] == "A"}
    now = dt.datetime.now().isoformat(timespec="seconds")
    n = 0
    for p in arch.get("picks") or []:
        r = by.get(p.get("pick_id"))
        if not r or p.get("repriced") or p.get("voided"):
            continue
        if r["status"] == "repriced_book":
            p["repriced"] = {"at": now, "from_payout": p.get("payout_units"), "recorded_price": p.get("fair_american"),
                             "book": r["book"], "book_snapshot_at": r["snapshot_at"],
                             "reason": ((f"2026-11-03: curated, graded at the model's own fair price {r.get('old_fair')}; "
                                         if r.get("kind") == "model_fair" else
                                         f"2026-11-03: graded at a placeholder {r.get('old_fair') or -110}; ")
                                        + f"re-priced at {r['book']}'s real pre-game price")}
            p["book_american"] = r["book_american"]
            p["payout_units"] = r["new_payout"]
        else:
            p["voided"] = True
            p["voided_at"] = now
            p["voided_reason"] = ((f"unpriced: curated, graded at the model's own fair price {r.get('old_fair')}, "
                                   if r.get("kind") == "model_fair" else
                                   "unpriced: graded at a placeholder -110 and ")
                                  + "no real pre-game book price is on record for this bet -- no honest payout")
        n += 1
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(arch, f, indent=2)
    print(f"wrote {OUT} ({len(seed)} rows); applied {n} to the archive")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
