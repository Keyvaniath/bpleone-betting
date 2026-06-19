/**
 * EdgeStat billing -- Stripe subscriptions + entitlements (Cloudflare Worker).
 *
 * Routes (mounted under /billing by worker.js):
 *   POST /billing/create-checkout   Auth: Bearer <supabase access_token>
 *        -> creates a Stripe Checkout Session for the Pro plan, returns { url }.
 *   POST /billing/webhook           (called by Stripe; Stripe-Signature verified)
 *        -> on subscription events, upserts the subscribers row in D1.
 *   GET  /billing/status            Auth: Bearer <supabase access_token>
 *        -> { pro: bool, status, current_period_end } for the signed-in user.
 *
 * Security model:
 *   - The signed-in identity comes from the Supabase access token (HS256 JWT,
 *     verified here with SUPABASE_JWT_SECRET). We never trust a client-supplied
 *     email for entitlement.
 *   - The webhook is authenticated by Stripe's signature (STRIPE_WEBHOOK_SECRET).
 *   - Entitlement lives in D1 (subscribers table; see schema_subscribers.sql).
 *
 * All routes are INERT until configured: if the relevant env secret is missing
 * they return 503 "billing not configured", so the worker never half-works.
 *
 * Required secrets (wrangler secret put ...):
 *   STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID,
 *   SUPABASE_JWT_SECRET, SITE_URL (vars ok for the last two non-secrets).
 */

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64urlToBytes(s) {
  s = String(s).replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function bytesToHex(u) { return Array.from(u).map(b => b.toString(16).padStart(2, "0")).join(""); }
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a[i] ^ b[i];
  return r === 0;
}
async function hmacSha256Bytes(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
}

// Verify a Supabase HS256 access token; return its payload (with .email) or null.
async function verifySupabaseJWT(token, secret) {
  if (!token || !secret) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const expected = await hmacSha256Bytes(secret, parts[0] + "." + parts[1]);
  let got;
  try { got = b64urlToBytes(parts[2]); } catch (e) { return null; }
  if (!timingSafeEqual(expected, got)) return null;
  let payload;
  try { payload = JSON.parse(dec.decode(b64urlToBytes(parts[1]))); } catch (e) { return null; }
  if (payload.exp && Date.now() / 1000 > payload.exp) return null;
  return payload;
}

// Verify Stripe's webhook signature header (t=..,v1=..).
async function verifyStripeSig(rawBody, sigHeader, secret) {
  if (!sigHeader || !secret) return false;
  const parts = {};
  sigHeader.split(",").forEach(kv => { const i = kv.indexOf("="); if (i > 0) parts[kv.slice(0, i)] = kv.slice(i + 1); });
  if (!parts.t || !parts.v1) return false;
  if (Math.abs(Date.now() / 1000 - Number(parts.t)) > 300) return false;   // 5-min tolerance
  const expected = bytesToHex(await hmacSha256Bytes(secret, parts.t + "." + rawBody));
  return timingSafeEqual(enc.encode(expected), enc.encode(parts.v1));
}

function bearer(request) {
  const h = request.headers.get("Authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7) : "";
}

async function createCheckout(env, email, ref) {
  const form = new URLSearchParams();
  form.set("mode", "subscription");
  form.set("line_items[0][price]", env.STRIPE_PRICE_ID);
  form.set("line_items[0][quantity]", "1");
  form.set("customer_email", email);
  form.set("client_reference_id", ref || email);
  form.set("allow_promotion_codes", "true");
  const site = env.SITE_URL || "https://betting.bpleone.com";
  form.set("success_url", site + "/account.html?upgraded=1");
  form.set("cancel_url", site + "/pricing.html");
  const r = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: { Authorization: "Bearer " + env.STRIPE_SECRET_KEY, "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  return r.json();
}

async function upsertSubscriber(env, row) {
  const now = new Date().toISOString();
  await env.EDGESTAT_DB.prepare(
    `INSERT INTO subscribers (email, stripe_customer, stripe_subscription, status, current_period_end, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(email) DO UPDATE SET
       stripe_customer=COALESCE(excluded.stripe_customer, subscribers.stripe_customer),
       stripe_subscription=COALESCE(excluded.stripe_subscription, subscribers.stripe_subscription),
       status=excluded.status,
       current_period_end=COALESCE(excluded.current_period_end, subscribers.current_period_end),
       updated_at=excluded.updated_at`
  ).bind(row.email, row.customer || null, row.subscription || null, row.status,
         row.period_end || null, now, now).run();
}

export async function handleBilling(request, env, url, cors) {
  const path = url.pathname;
  const J = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: cors });

  if (!env.EDGESTAT_DB) return J({ error: "D1 not bound" }, 503);

  // ---- POST /billing/webhook (Stripe -> us) -------------------------------
  if (path === "/billing/webhook" && request.method === "POST") {
    if (!env.STRIPE_WEBHOOK_SECRET) return J({ error: "billing not configured" }, 503);
    const raw = await request.text();
    const ok = await verifyStripeSig(raw, request.headers.get("Stripe-Signature"), env.STRIPE_WEBHOOK_SECRET);
    if (!ok) return J({ error: "bad signature" }, 400);
    let ev;
    try { ev = JSON.parse(raw); } catch (e) { return J({ error: "bad json" }, 400); }
    const obj = (ev.data && ev.data.object) || {};
    try {
      if (ev.type === "checkout.session.completed") {
        const email = (obj.customer_details && obj.customer_details.email) || obj.customer_email;
        if (email) await upsertSubscriber(env, {
          email: email.toLowerCase(), customer: obj.customer, subscription: obj.subscription,
          status: "active", period_end: Math.floor(Date.now() / 1000) + 35 * 86400,
        });
      } else if (ev.type === "customer.subscription.updated" || ev.type === "customer.subscription.created") {
        const active = obj.status === "active" || obj.status === "trialing";
        const row = await env.EDGESTAT_DB.prepare("SELECT email FROM subscribers WHERE stripe_customer=?").bind(obj.customer).first();
        if (row && row.email) await upsertSubscriber(env, {
          email: row.email, customer: obj.customer, subscription: obj.id,
          status: active ? obj.status : "inactive", period_end: obj.current_period_end,
        });
      } else if (ev.type === "customer.subscription.deleted") {
        await env.EDGESTAT_DB.prepare("UPDATE subscribers SET status='canceled', updated_at=? WHERE stripe_customer=?")
          .bind(new Date().toISOString(), obj.customer).run();
      }
    } catch (e) { return J({ error: String(e) }, 500); }
    return J({ received: true });
  }

  // ---- POST /billing/create-checkout (signed-in user upgrades) ------------
  if (path === "/billing/create-checkout" && request.method === "POST") {
    if (!env.STRIPE_SECRET_KEY || !env.STRIPE_PRICE_ID) return J({ error: "billing not configured" }, 503);
    const claims = await verifySupabaseJWT(bearer(request), env.SUPABASE_JWT_SECRET);
    if (!claims || !claims.email) return J({ error: "not signed in" }, 401);
    const session = await createCheckout(env, claims.email.toLowerCase(), claims.sub);
    if (session && session.url) return J({ url: session.url });
    return J({ error: (session && session.error && session.error.message) || "stripe error" }, 502);
  }

  // ---- GET /billing/status (is this user Pro?) ----------------------------
  if (path === "/billing/status") {
    const claims = await verifySupabaseJWT(bearer(request), env.SUPABASE_JWT_SECRET);
    if (!claims || !claims.email) return J({ pro: false, reason: "not signed in" }, 200);
    const row = await env.EDGESTAT_DB.prepare("SELECT status, current_period_end FROM subscribers WHERE email=?")
      .bind(claims.email.toLowerCase()).first();
    const now = Math.floor(Date.now() / 1000);
    const pro = !!(row && (row.status === "active" || row.status === "trialing") &&
                   (!row.current_period_end || row.current_period_end > now));
    return J({ pro, status: (row && row.status) || "none", current_period_end: (row && row.current_period_end) || null });
  }

  return null;  // not a billing route -> let worker.js continue
}
