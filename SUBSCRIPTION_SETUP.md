# Subscription backend — setup & deploy

The full subscription path is **built and wired** (code-complete). It ships
**inert** until you connect a Stripe account and deploy. This is the ~30-minute
checklist to turn it on. Prereq: the LLC (so Stripe is in the business's name).

## What's already built
- **Worker billing** (`cloudflare-worker/src/billing.js`, mounted at `/billing/*` in
  `src/worker.js`): `POST /billing/create-checkout` (Stripe Checkout), `POST
  /billing/webhook` (Stripe-signature-verified), `GET /billing/status` (Supabase-JWT
  verified). Entitlements live in D1 (`schema_subscribers.sql`).
- **Client paywall** (`js/premium.js` + `js/premium-config.js`): `EdgeStatPremium`
  with `getStatus()`, `upgrade()`, and `gate()` (blurs `[data-premium]` content for
  non-Pro users). `pricing.html` is the storefront.
- All inert until configured — no fake checkout, no broken paywall.

## Step 1 — Accounts (Supabase, free)
If not done already, follow `js/auth-config.js`: create a free Supabase project,
enable Email (magic link), paste `SUPABASE_URL` + `SUPABASE_ANON_KEY`.
- Get the **JWT secret**: Supabase → Project Settings → API → "JWT Settings" → copy
  the `JWT Secret` (this is what the worker uses to verify the signed-in user).

## Step 2 — Stripe (after the LLC)
1. Create a Stripe account (business/LLC).
2. Product catalog → add a **Product** "EdgeStat Pro" → add a **recurring Price**
   (e.g. $12/mo). Copy the **price id** (`price_...`).
3. Developers → API keys → copy the **Secret key** (`sk_live_...` or `sk_test_...`).
4. Developers → Webhooks → add endpoint `https://<your-worker>/billing/webhook`,
   subscribe to: `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`. Copy the
   **signing secret** (`whsec_...`).

## Step 3 — Worker (Cloudflare)
From `cloudflare-worker/`:
```
wrangler d1 execute edgestat --file=schema_subscribers.sql --remote
wrangler secret put STRIPE_SECRET_KEY        # paste sk_...
wrangler secret put STRIPE_WEBHOOK_SECRET    # paste whsec_...
wrangler secret put STRIPE_PRICE_ID          # paste price_...
wrangler secret put SUPABASE_JWT_SECRET      # paste the Supabase JWT secret
# set SITE_URL (a [vars] entry in wrangler.toml or a secret), e.g. https://betting.bpleone.com
wrangler deploy
```
> Note: `billing.js` verifies the **HS256** Supabase access token (the default JWT
> secret). If your project uses asymmetric (ES256/RS256) keys, adapt
> `verifySupabaseJWT` to fetch the JWKS.

## Step 4 — Front-end
In `js/premium-config.js`: set `apiBase` to your Worker URL and `enabled: true`
(and `priceDisplay`/`pricePeriod` to match Stripe). Push. Done — `pricing.html`'s
"Go Pro" now opens Stripe Checkout; on success the webhook marks the account Pro.

## Step 5 — Gate premium content (product decision)
Mark any section/page Pro-only by adding `data-premium` (and optional
`data-premium-msg="…"`) to its container, and include
`<script src="js/premium.js"></script>` on that page. Non-Pro users see a clean
"EdgeStat Pro — See plans" teaser; Pro users see it normally. Decide *which*
boards are Pro (e.g. full prop edge boards, real-time alerts) — keep the free tier
genuinely useful.

## Test before launch
- Use Stripe **test mode** keys first; run a test card through `pricing.html`.
- Confirm `/billing/status` returns `pro:true` after the test purchase, and that a
  `data-premium` block unlocks.
- Switch to live keys + live price + live webhook when verified.

## Production hardening (optional, later)
- Handle `invoice.paid` to extend `current_period_end` precisely (the build
  currently sets a generous window on checkout and refines on subscription events).
- Add a Stripe **billing portal** link on `account.html` for self-serve cancel.
