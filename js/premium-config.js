/* EdgeStat -- premium (subscription) config. NO-OP until configured.
 *
 * Pairs with the Stripe billing layer in the Cloudflare Worker (src/billing.js).
 * Until enabled, pricing.html shows the plan but the "Upgrade" button explains
 * it's launching shortly, and no content is gated. Nothing fake ships.
 *
 * To go live (after the LLC + a Stripe account):
 *   1. Stripe: create a recurring Price for the Pro plan; copy its price_id.
 *   2. Worker: `wrangler secret put STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`
 *      / `STRIPE_PRICE_ID` / `SUPABASE_JWT_SECRET`; set SITE_URL var. Apply
 *      schema_subscribers.sql. Add the /billing/webhook endpoint in Stripe.
 *   3. Fill apiBase below with your Worker URL and set enabled:true.
 *   (Full steps in SUBSCRIPTION_SETUP.md.)
 *
 * Every value here is PUBLIC-safe. NEVER put a Stripe SECRET key in this file.
 */
window.EDGESTAT_PREMIUM = {
  enabled: false,
  apiBase: "",                 // e.g. "https://edgestat-live.<you>.workers.dev"
  priceDisplay: "$12",         // cosmetic, shown on pricing.html
  pricePeriod: "/mo",
  planName: "EdgeStat Pro",

  isConfigured: function () { return !!(this.enabled && this.apiBase); },
};
