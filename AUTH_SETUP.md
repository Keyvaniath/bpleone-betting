# Free customer accounts — 3-minute setup

EdgeStat has a complete, **free, passwordless** customer login already built and
live (Sign-In chip in the top bar, `login.html`, `account.html`). It uses
**Supabase Auth** (free tier: 50,000 monthly active users, no credit card).
No passwords are ever stored — sign-in is an email magic link (or Google).

Until you do the two-value setup below, the site shows an honest
"accounts launching shortly" message and never breaks.

## Why this is safe to ship publicly
The only value that goes in client code is the Supabase **anon (publishable)
key**. That key is *designed* to be public — it can only do what your
Row-Level-Security policies allow. This is the standard way Supabase is used
from a static site. (Never put the **service_role** key in the site.)

## Steps

1. **Create a free project** at <https://supabase.com> → "New project".
   Pick any name/region; no card required.

2. **Copy two values** from Project → Settings → **API**:
   - **Project URL** (looks like `https://abcdefgh.supabase.co`)
   - **anon public** key (a long JWT-looking string)

3. **Paste them** into [`js/auth-config.js`](js/auth-config.js):
   ```js
   SUPABASE_URL: "https://abcdefgh.supabase.co",
   SUPABASE_ANON_KEY: "eyJhbGci...your-anon-key...",
   ```
   Commit + push. GitHub Pages redeploys in ~30s and accounts go live.

4. **Enable sign-in methods** in the Supabase dashboard → **Authentication → Providers**:
   - Turn on **Email** (this is the magic-link method — on by default).
   - (Optional) Turn on **Google** for one-tap Google sign-in.

5. **Allow your site URL** under **Authentication → URL Configuration →
   Redirect URLs**: add
   - `https://betting.bpleone.com/account.html`
   - `https://keyvaniath.github.io/account.html` (the Pages default, as a backup)

That's it. The Sign-In button starts working immediately for every visitor.

## What customers get (free for now)
- One-tap, passwordless sign-in (email link or Google).
- An identity to attach saved bets / personalized boards to (coming soon).
- **No paywall** — every board on the site stays free to access.

## Cost
$0. Supabase free tier covers 50k monthly active users and 500MB database —
far beyond early needs. If you ever outgrow it, the same code works on the
paid tier with no changes.
