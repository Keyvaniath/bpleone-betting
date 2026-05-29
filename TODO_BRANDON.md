# Your action list — EdgeStat (betting.bpleone.com)

_Last audited: 2026-05-29. The platform is self-sustaining and tracking accurate
data (see "Verified" at the bottom). Everything below needs YOU — it's gated on
accounts/credentials/console settings I can't (and shouldn't) touch. Ordered by
impact. You have Cloudflare + GitHub open, so it's grouped by console._

---

## 🔴 1. GitHub — fix HTTPS on betting.bpleone.com  (highest impact)
The site currently only loads over **http://** — `https://betting.bpleone.com`
throws a cert error. GitHub Pages is stuck on its default cert and never issued
one for the custom domain (DNS is correct, so it's a stuck provisioning request).

**Do this:** GitHub → repo **Settings → Pages → Custom domain**
1. Delete `betting.bpleone.com`, click **Save**.
2. Wait ~1 minute, re-type `betting.bpleone.com`, **Save** again. This re-fires
   the Let's Encrypt request.
3. Wait for "DNS check successful" + the cert to issue (minutes–24h).
4. Once issued, tick **Enforce HTTPS**.

## 🔴 2. Cloudflare — keep the DNS record "DNS only" (supports #1)
Cloudflare → **DNS** → the `betting` CNAME (→ `keyvaniath.github.io`).
- Make sure the cloud icon is **grey (DNS only)**, NOT orange (Proxied).
  GitHub Pages cannot issue SSL through Cloudflare's proxy.
- (It currently resolves straight to GitHub's IPs, so it's probably already grey
  — just confirm while you're in there.)

---

## 🟡 3. Supabase — turn on free customer logins  (~3 min, optional but ready)
The login system is built and live; it just needs a provider connected.
1. Create a free project at <https://supabase.com> (no card).
2. Settings → API: copy **Project URL** + **anon public** key.
3. Paste both into `js/auth-config.js`, commit/push.
4. Supabase → Authentication → Providers: enable **Email** (magic link).
5. Authentication → URL Configuration → add `https://betting.bpleone.com/account.html`.

Full walkthrough: `AUTH_SETUP.md`. Cost: $0 (50k users free).

---

## ⚪ 4. Optional boosts (not required — site works without these)
- **GitHub → Settings → Secrets → `ODDS_API_KEY`**: renew at the-odds-api.com and
  update the secret for DraftKings-canonical lines. The Bovada fallback already
  serves real odds, so this is a nice-to-have, not a fix.
- **Cloudflare Worker (sub-minute live scores):** the repo has `cloudflare-worker/`.
  `npm i -g wrangler && cd cloudflare-worker && wrangler login && wrangler deploy`
  (free tier). Then set GitHub secret `EDGESTAT_WORKER_URL` to the deployed URL.
  Enables 1-minute live in-game updates + saved-model-override sync. Optional.
- **Re-enable `live-games` cron:** it was disabled to save Actions minutes, but the
  repo is **public = unlimited minutes**, so you can turn its cron back on for free
  if you want GitHub-side live polling. (The Worker above is the better path.)

---

## ✅ Verified self-sustaining + accurate (no action needed)
- **Automation runs itself:** daily-pipeline (6AM+6PM ET), heartbeat (every 2h,
  settles picks + self-learns), training-loop (every 3h), watchdog (every 4h).
  During this audit the **watchdog auto-detected a stale pipeline and re-triggered
  it with zero input** — self-healing confirmed.
- **No quota risk:** public repo → unlimited GitHub Actions minutes. The old
  "90% of 2,000 min" worry only applies to private repos.
- **Accurate data:** 2,261 real settled picks (graded vs box scores), 28 non-zero
  CLV captures (open/close lifecycle), learning quality STRONG, freshness ~60% and
  climbing, no fabricated numbers (synthetic backtest removed), honest data-integrity
  pages live.
- **Deploys itself:** every push auto-builds GitHub Pages (~30s).
