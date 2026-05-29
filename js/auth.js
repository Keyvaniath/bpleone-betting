/* EdgeStat — customer auth (Supabase, passwordless).
 *
 * Loads the Supabase JS client from CDN ONLY when accounts are configured
 * (js/auth-config.js). Exposes window.EdgeStatAuth and injects a Sign-In /
 * Account chip into the top bar on every page (via nav.js). No passwords are
 * ever handled here — sign-in is an email magic link or Google OAuth.
 *
 * Free for now: signing in just creates a free account (identity +
 * future personalization like saved bets). No content is gated behind it.
 */
(function () {
  "use strict";
  var CFG = window.EDGESTAT_AUTH || {};
  var CONFIGURED = typeof CFG.isConfigured === "function" ? CFG.isConfigured() : false;
  var _client = null;

  function redirectTo() {
    var path = (CFG.REDIRECT_PATH || "/account.html");
    return window.location.origin + path;
  }

  // Lazily create the Supabase client (dynamic import — no build step).
  async function getClient() {
    if (_client) return _client;
    if (!CONFIGURED) return null;
    var mod = await import("https://esm.sh/@supabase/supabase-js@2");
    _client = mod.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
    });
    return _client;
  }

  async function getUser() {
    try {
      var c = await getClient();
      if (!c) return null;
      var res = await c.auth.getUser();
      return (res && res.data && res.data.user) ? res.data.user : null;
    } catch (e) { return null; }
  }

  // Passwordless email magic link.
  async function signInWithEmail(email) {
    var c = await getClient();
    if (!c) throw new Error("Accounts are not enabled yet.");
    var res = await c.auth.signInWithOtp({
      email: email,
      options: { emailRedirectTo: redirectTo() }
    });
    if (res.error) throw res.error;
    return true;
  }

  // Optional Google OAuth (only works if enabled in the Supabase dashboard).
  async function signInWithGoogle() {
    var c = await getClient();
    if (!c) throw new Error("Accounts are not enabled yet.");
    var res = await c.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: redirectTo() }
    });
    if (res.error) throw res.error;
    return true;
  }

  async function signOut() {
    try { var c = await getClient(); if (c) await c.auth.signOut(); } catch (e) {}
    window.location.href = "index.html";
  }

  // Top-bar chip: "Sign In" when signed out, "👤 email" when signed in.
  // Hidden entirely until accounts are configured, so the live site never
  // shows a dead button.
  async function renderChip() {
    if (!CONFIGURED) return;
    var bar = document.querySelector(".topbar-actions");
    if (!bar || document.getElementById("authChip")) return;
    var chip = document.createElement("a");
    chip.id = "authChip";
    chip.style.cssText =
      "display:inline-flex;align-items:center;gap:6px;margin-left:10px;padding:6px 12px;" +
      "border-radius:6px;font-size:12px;font-weight:600;text-decoration:none;" +
      "border:1px solid rgba(255,255,255,0.16);color:var(--text,#eaeaea);white-space:nowrap;";
    var user = await getUser();
    if (user) {
      chip.href = "account.html";
      chip.textContent = "👤 " + (user.email ? user.email.split("@")[0] : "Account");
      chip.title = "Your account";
    } else {
      chip.href = "login.html";
      chip.textContent = "Sign In";
      chip.style.background = "var(--accent,#4ade80)";
      chip.style.color = "#04210f";
      chip.style.borderColor = "transparent";
    }
    bar.appendChild(chip);
  }

  window.EdgeStatAuth = {
    configured: CONFIGURED,
    getClient: getClient,
    getUser: getUser,
    signInWithEmail: signInWithEmail,
    signInWithGoogle: signInWithGoogle,
    signOut: signOut
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderChip);
  } else {
    renderChip();
  }
})();
