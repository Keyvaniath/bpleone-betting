"""Totals study (2026-11-11) -- a recorded NEGATIVE result; see docs/ODDS-INTEGRITY.md.

Question: the moneyline desks give no NBA/NHL play. Do game totals?
Pre-registered before looking at this season:
  model = additive offence/defence EWMA (alpha, season carry) chosen on LAST
          season only (minimum squared error of the game total)
  test  = this season's DraftKings-priced games (data/dk_lines_<sport>.json,
          real over/under prices); pushes dropped
  gate  = the moneyline desk's gate on the over/under outcome: blend weight w
          fitted on a 0..1 grid in logit space against DraftKings' no-vig over
          probability; NO EDGE when w = 0
  bets  = over/under at the real DK price when EV >= 4%

Result on 2026-11-11: NFL / NBA / NHL all w = 0 (DK ~0.692 log loss, a coin
flip; the model 0.71-0.75). Compare against the PRICE, not the posted number:
the NHL book moves the juice on 6.5, so squared error vs the number misleads.

Run from the repo root:  python tools/totals_study.py
"""
import sys, os, json, math, random, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import game_lines_desk as gld

SEASON_START = {"nfl": "2026-08-01", "nba": "2026-10-01", "nhl": "2026-09-25"}


class OD:
    def __init__(self, sport, alpha, carry, mu0):
        self.sport, self.a, self.carry = sport, alpha, carry
        self.o, self.d, self.mu, self.season = {}, {}, mu0, None

    def new_season(self, s):
        if self.season is not None and s != self.season:
            self.o = {t: v * (1 - self.carry) for t, v in self.o.items()}
            self.d = {t: v * (1 - self.carry) for t, v in self.d.items()}
        self.season = s

    def pred(self, h, a):
        ph = self.mu + self.o.get(h, 0) + self.d.get(a, 0)
        pa = self.mu + self.o.get(a, 0) + self.d.get(h, 0)
        return ph + pa

    def update(self, g):
        h, a, hs, as_ = g["home"], g["away"], g["home_score"], g["away_score"]
        eh = hs - (self.mu + self.o.get(h, 0) + self.d.get(a, 0))
        ea = as_ - (self.mu + self.o.get(a, 0) + self.d.get(h, 0))
        self.o[h] = self.o.get(h, 0) + self.a * eh / 2
        self.d[a] = self.d.get(a, 0) + self.a * eh / 2
        self.o[a] = self.o.get(a, 0) + self.a * ea / 2
        self.d[h] = self.d.get(h, 0) + self.a * ea / 2
        self.mu += 0.01 * ((hs + as_) / 2 - self.mu)


def walk(sport, finals, alpha, carry, mu0):
    m, out = OD(sport, alpha, carry, mu0), {}
    i = 0
    for g in finals:
        while i < len(finals) and finals[i]["date"] < g["date"]:
            m.new_season(gld._season_key(sport, finals[i]["date"]))
            m.update(finals[i])
            i += 1
        m.new_season(gld._season_key(sport, g["date"]))
        out[(g["date"], g["away"], g["home"])] = m.pred(g["home"], g["away"])
    return out


def pois_cdf(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k) + 1))


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def study(sport):
    finals = gld.load_finals(sport)
    ss = SEASON_START[sport]
    prior = [g for g in finals if g["date"] < ss]
    mu0 = sum(g["home_score"] + g["away_score"] for g in prior[:200]) / (2 * min(200, len(prior)))
    best = None
    for alpha in (0.02, 0.04, 0.06, 0.08, 0.12, 0.16, 0.24):
        for carry in (0.0, 0.25, 0.5, 0.75):
            pr = walk(sport, prior, alpha, carry, mu0)
            burn = prior[len(prior) // 4:]
            mse = sum((g["home_score"] + g["away_score"] - pr[(g["date"], g["away"], g["home"])]) ** 2 for g in burn) / len(burn)
            if best is None or mse < best[0]:
                best = (mse, alpha, carry)
    mse_prior, alpha, carry = best
    pr = walk(sport, finals, alpha, carry, mu0)
    sd_prior = math.sqrt(mse_prior)
    fin = {(g["date"], g["away"], g["home"]): g for g in finals}
    lines = gld._load(os.path.join(gld.DATA_DIR, "dk_lines_%s.json" % sport)).get("events") or {}
    rows = []
    for eid, ev in lines.items():
        c = ev.get("close") or {}
        if c.get("total") is None:
            continue
        try:
            ct = dt.datetime.fromisoformat(str(ev.get("commence")).replace("Z", "+00:00"))
        except Exception:
            continue
        d = (ct - dt.timedelta(hours=4)).date().isoformat()
        k = (d, gld._norm_team(sport, ev.get("away")), gld._norm_team(sport, ev.get("home")))
        g = fin.get(k)
        if not g or k not in pr:
            continue
        rows.append({"d": d, "k": k, "y": g["home_score"] + g["away_score"], "dk": float(c["total"]), "m": pr[k],
                     "op": c.get("over_price"), "up": c.get("under_price")})
    rows.sort(key=lambda r: r["d"])
    rows = [r for r in rows if r["y"] != r["dk"] and gld._no_vig(r["op"], r["up"]) is not None]
    n = len(rows)
    sd = math.sqrt(sum((r["y"] - r["dk"]) ** 2 for r in rows) / n)
    def pm(r):
        if sport == "nhl":
            return 1 - pois_cdf(math.floor(r["dk"]), max(r["m"], 0.5))
        return 1 - ncdf((r["dk"] - r["m"]) / sd)
    L, S = gld._logit, gld._sig
    clip = lambda p: min(max(p, 0.02), 0.98)
    for r in rows:
        r["pk"] = gld._no_vig(r["op"], r["up"]); r["pmod"] = clip(pm(r)); r["o"] = 1.0 if r["y"] > r["dk"] else 0.0
    W = [i / 20 for i in range(21)]
    bl = lambda r, w: S(L(r["pk"]) + w * (L(r["pmod"]) - L(r["pk"])))
    ll = lambda rs, w: sum(gld._ll(bl(r, w), r["o"]) for r in rs) / len(rs)
    by_w = {w: ll(rows, w) for w in W}
    wb = min(by_w, key=by_w.get)
    half = n // 2
    wf = min(W, key=lambda w: ll(rows[:half], w))
    def sim(rs, w, edge=0.04):
        b = wn = 0; u = 0.0
        for r in rs:
            p = bl(r, w)
            for side, pp, px in (("o", p, r["op"]), ("u", 1 - p, r["up"])):
                dd = gld._dec(px)
                if dd and pp * dd - 1 >= edge:
                    won = (r["o"] == 1.0) == (side == "o"); b += 1; wn += won; u += (dd - 1) if won else -1.0
        return "%d bets %d-%d %+.2fu %s" % (b, wn, b - wn, u, ("%+.1f%%" % (u / b * 100)) if b else "")
    rng = random.Random(7)
    g = [gld._ll(r["pk"], r["o"]) - gld._ll(bl(r, wb), r["o"]) for r in rows]
    bo = sorted(sum(g[rng.randrange(n)] for _ in range(n)) / n for _ in range(1000))
    mll = sum(gld._ll(r["pmod"], r["o"]) for r in rows) / n
    print("== %s totals, n=%d (pushes dropped) | model alpha=%s carry=%s" % (sport.upper(), n, alpha, carry))
    print("   log loss: DK no-vig %.4f | model %.4f | blend %.4f at w=%s | coin flip 0.6931" % (by_w[0.0], mll, by_w[wb], wb))
    print("   gain 90%% CI [%.4f, %.4f] | w from first half %s" % (bo[50], bo[949], wf))
    print("   sim in-sample:", sim(rows, wb), "| OOS half:", sim(rows[half:], wf), "| w=1:", sim(rows, 1.0))
    verdict = "NO EDGE" if wb == 0 else ("PROMISING" if bo[50] > 0 else "UNPROVEN")
    print("   verdict under the desk's gate:", verdict)


for s in ("nfl", "nba", "nhl"):
    study(s)
