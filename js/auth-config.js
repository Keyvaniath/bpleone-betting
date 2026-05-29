/* EdgeStat — customer accounts config (FREE tier, Supabase Auth).
 *
 * ONE-TIME SETUP (~3 min, no credit card) — full steps in AUTH_SETUP.md:
 *   1. Create a free project at https://supabase.com
 *   2. Project Settings → API: copy the "Project URL" and the "anon public" key
 *   3. Paste them below and commit/push
 *   4. Authentication → Providers: enable "Email" (magic link).
 *      Optionally enable Google. Under Authentication → URL Configuration,
 *      add your site URL(s) (e.g. https://betting.bpleone.com) to the
 *      redirect allow-list.
 *
 * The anon key is SAFE to expose in client-side code — it only grants what
 * your Supabase Row-Level-Security policies allow. (This is exactly how
 * Supabase is designed to be used from a static site.)
 *
 * Until these two values are filled in, the site shows an honest
 * "accounts launching shortly" state and never breaks. No password is ever
 * handled by this site — sign-in is a passwordless email magic-link (or
 * Google), so there are no credentials to store or leak.
 */
window.EDGESTAT_AUTH = {
  SUPABASE_URL: "",        // e.g. "https://abcdefgh.supabase.co"
  SUPABASE_ANON_KEY: "",   // the "anon public" key (safe for the browser)

  // Where to send users after they click their magic link / finish OAuth.
  // Left blank => uses <origin>/account.html automatically.
  REDIRECT_PATH: "/account.html",

  isConfigured: function () {
    return !!(this.SUPABASE_URL && this.SUPABASE_ANON_KEY);
  }
};
