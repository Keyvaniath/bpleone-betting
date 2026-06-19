# GO-OFFICIAL — turning EdgeStat into a legitimate business

This is the checklist to take EdgeStat from "impressive analytics project" to an
**official sports-gambling analytics website**. It separates what's **already built**
(the compliance + reliability layer) from what **only you (Brandon) can do** (entity,
legal review, data licensing, payments).

> ⚠️ Not legal advice. Gambling/advertising rules are state-specific. Have a licensed
> **gaming/advertising attorney** review everything in Tier 1 before you publicly
> market or monetize. The `.html` legal pages are templates with `[BRACKETED]`
> placeholders for counsel to finalize.

Reminder of the model: **you are a content / analytics / affiliate business, not a
sportsbook.** You don't take bets or hold funds, which keeps you out of gaming-operator
licensing. The bar is **media + affiliate + advertising compliance** — achievable.

---

## ✅ Already built this pass (code-side, live on the site)

- **Legal/trust pages**: `terms.html`, `privacy.html`, `responsible-gambling.html`,
  `disclaimer.html`, `affiliate-disclosure.html`, `data-sources.html`.
- **Site-wide compliance layer** (`js/compliance.js`, auto-loaded by `nav.js` on every
  page): persistent 21+ / 1-800-GAMBLER / NCPG / legal-links footer **and** a first-visit
  **21+ age-verification gate** (remembered in `localStorage`).
- **Affiliate framework** (`js/affiliate-config.js` + `sportsbooks.html`): FTC-compliant,
  config-driven "Where to Bet" surface; links render `rel="sponsored nofollow noopener"`;
  ships **disabled** ("partners coming soon") until you add real affiliate links.
- **Reliability/monitoring**: `data_health.py` now has a season-independent **freshness
  canary**; `status.html` public status page; `.github/workflows/health-alert.yml` opens
  a GitHub issue if a feed goes dark (no more silent cron failures).
- **Subscription backend (Tier 2 #5) — code-complete, inert until you connect Stripe**:
  Worker Stripe billing (`cloudflare-worker/src/billing.js`: checkout + signature-verified
  webhook + Supabase-JWT-verified entitlement status, D1-backed), client paywall
  (`js/premium.js` / `premium-config.js`, gates `[data-premium]` content), and
  `pricing.html`. Turn it on via **SUBSCRIPTION_SETUP.md** (~30 min once the LLC + a
  Stripe account exist).

---

## TIER 1 — Legitimacy blockers (your action)

### 1. Form a legal entity
- Form an **LLC** (single-member is fine) in your state (CA) or a business-friendly
  state. ~$50–$800 to file + a registered agent. This is the liability shield — do it
  before you take a dollar of revenue or run paid ads.
- Get an **EIN** (free, IRS), a business bank account, and (optional) business insurance
  (general liability + media/E&O — media liability matters for a content site making
  performance claims).
- **Fill the placeholders** in the legal pages with the entity name, state, and a
  contact/mailing address: search the `.html` files for `[LEGAL ENTITY NAME]`, `[STATE]`,
  `[COUNTY, STATE]`, `[EFFECTIVE DATE]`, `[DATE]`, `[ARBITRATION BODY]`, `[MAILING ADDRESS]`.
- Set up role email addresses: `legal@bpleone.com`, `privacy@bpleone.com`,
  `support@bpleone.com` (referenced in the legal pages).

### 2. Legal review (gaming/advertising attorney)
- Have counsel review the ToS / Privacy / Disclaimer / Affiliate pages and your
  marketing claims (the **track-record / ROI claims** need to be FTC-defensible —
  substantiated, with the "past performance" disclaimer, which is in place).
- Confirm state rules for **paid sports-betting picks ("tout" services)** if you go
  subscription, and **affiliate registration** requirements in regulated states if you
  go affiliate (some states require affiliates to register or be disclosed by the operator).
- Confirm the arbitration/class-waiver clause is enforceable in your state.

### 3. Licensed data (your action + cost)
The free feeds (ESPN, Daum, bo3.gg, MLB Stats, PrizePicks public) are fine for a personal
project, but their ToS generally **prohibit commercial use**. For a commercial site:
- **Odds**: restore/upgrade **The Odds API** (paid tiers ~$30–$300+/mo) — this also
  un-darkens player-prop book lines and unlocks real book-vs-model edges + CLV. For scale,
  **OpticOdds** or **Sportradar** (enterprise, $$$$).
- **Stats / official data**: Sportradar / Genius Sports for licensed league data if you
  want official partnerships; otherwise keep MLB Stats API (its terms are relatively
  permissive) and budget for licensed odds first.
- Code is **already wired** to consume a paid odds key (`ODDS_API_KEY` GitHub secret) —
  set the secret and the prop/edge paths light up. See `data-sources.html`.

---

## TIER 2 — To be a business

### 4. Pick a monetization model (your decision) — DEFAULT BUILT = AFFILIATE
The site currently ships the **affiliate** path (compliant, low-infra, no payment
processor). To choose:
- **Affiliate** (recommended start): apply to operator affiliate programs (DraftKings,
  FanDuel, BetMGM, Caesars, Fanatics — often via their networks or income-access). Needs
  the LLC + sometimes state affiliate registration. Then set `enabled:true` and drop real
  tracking links into `js/affiliate-config.js`. Revenue = CPA / rev-share. **No payment
  processor needed.**
- **Subscription** (premium picks): higher revenue ceiling, more infra. Needs (a) a
  payment processor that allows "sports analytics / tout" — **Stripe** sometimes allows it
  but review their restricted-business list; specialists exist — and (b) real accounts +
  a paywall (see #5). Note `js/auth-config.js` / `auth.js` already scaffold passwordless
  accounts.
- You can do **both** later (free + affiliate now, premium tier on top).

### 5. Real backend — ✅ BUILT (needs your accounts + deploy)
The backend is **code-complete**. Today the public site is static (GitHub Pages) +
`localStorage` + cron; the dynamic layer runs on the existing **Cloudflare Worker**
(KV + D1 + R2) with **Supabase** for passwordless accounts.
- **Auth + DB**: Supabase Auth (`js/auth.js`, magic-link) + the Worker's D1 for
  entitlements (`schema_subscribers.sql`). **Your action**: create the free Supabase
  project + paste keys into `js/auth-config.js`.
- **Payments**: Stripe Billing is fully wired (`cloudflare-worker/src/billing.js` +
  `js/premium.js` + `pricing.html`). **Your action**: create a Stripe account (after the
  LLC), set the Worker secrets, flip `enabled:true`. Full steps in **SUBSCRIPTION_SETUP.md**.
- **Host**: static analytics stay on GitHub Pages; auth/paywall/API already live on the
  Cloudflare Worker — nothing new to stand up.
- **Email (ESP)**: Formspree is wired for capture; for real sends use Buttondown /
  Mailchimp / ConvertKit (the morning digest "The Tape").

### 6. Reliability / monitoring — ✅ BUILT
- `status.html` + `data_health.py` freshness canary + `health-alert.yml` (opens an issue
  when a feed goes dark). **Your action**: after the LLC, optionally add uptime pings
  (UptimeRobot, free) and make sure GitHub notifications reach you.

---

## TIER 3 — Credibility polish (mostly built / optional)

7. **Verifiable track record** — the settled ledger + `calibration-map.html` are most of
   the way there. Optional: third-party verification (Pikkit / Action Network-style) for
   marketing credibility.
8. **Mobile QA, SEO, security review** — do a mobile pass, add meta/OG tags + a sitemap,
   and a basic security review before a public launch push.

---

## Suggested order of operations
1. Form the LLC + EIN + bank account. Fill the `[placeholders]` in the legal pages.
2. 1–2 hours with a gaming/advertising attorney on the pages + claims + your chosen model.
3. Decide **affiliate vs subscription** (start affiliate).
4. Restore the paid **odds key** (turns analytics into tradeable edges + CLV).
5. Affiliate path: apply to programs → set `enabled:true` + real links. Subscription path:
   stand up auth + Stripe + a host.
6. Mobile/SEO/security polish → public launch.

Everything in "Already built" is live and code-complete. The remaining items are
business/legal decisions and spend that only you can authorize.
