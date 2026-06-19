# Security

## Reporting a vulnerability
Email **security@bpleone.com** with details and steps to reproduce. Please don't
open a public issue for security reports. We aim to acknowledge within a few days.

## Posture (Tier 3 security review)
- **Static front-end.** The public site is static HTML/CSS/JS on GitHub Pages over
  HTTPS — no public server-side attack surface, no user input executed server-side.
- **No secrets in client code.** `js/*-config.js` hold only public-safe values
  (e.g. the Supabase **anon** key, which is gated by Row-Level-Security). All real
  secrets (Stripe secret/webhook keys, Supabase JWT secret) live only as **Cloudflare
  Worker secrets** (`wrangler secret put`), never committed. Verified: no `sk_live_`,
  `whsec_`, private keys, or tokens in the repo.
- **Passwordless auth.** Sign-in is a Supabase email magic link / OAuth — the site
  never handles or stores passwords, so there are no credentials to leak.
- **Payments.** Handled by **Stripe Checkout** (PCI-compliant, hosted by Stripe). No
  card data ever touches EdgeStat. The billing Worker **verifies Stripe webhook
  signatures** and **verifies the Supabase access-token JWT** before granting any
  entitlement (`cloudflare-worker/src/billing.js`).
- **Outbound links** to operators use `rel="sponsored nofollow noopener"`; the age
  gate + responsible-gambling footer load site-wide.

## Hardening checklist (before/after launch)
- [ ] Confirm GitHub Pages HTTPS + the custom domain cert (already valid).
- [ ] If you front the site with Cloudflare, add response headers:
      `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
      `Referrer-Policy: strict-origin-when-cross-origin`, a tuned
      `Content-Security-Policy` (the site uses inline styles, so CSP needs care).
- [ ] Restrict the Worker's CORS `Access-Control-Allow-Origin` to the site origin for
      the `/billing/*` and `/admin/*` routes once the domain is fixed.
- [ ] Keep the `/admin/*` Worker routes behind `MANUAL_TRIGGER_KEY` / auth (they are).
- [ ] Rotate any key that is ever exposed; secrets are Worker-only by design.
- [ ] Optional: Subresource Integrity (SRI) on CDN `<script>` tags (Chart.js).
