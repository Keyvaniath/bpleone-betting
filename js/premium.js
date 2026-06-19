/* EdgeStat -- premium paywall client (pairs with worker billing.js).
 *
 * Exposes window.EdgeStatPremium:
 *   getStatus()  -> { pro, status } using the signed-in Supabase session.
 *   upgrade()    -> starts Stripe Checkout (or routes to sign-in first).
 *   gate(root)   -> hides [data-premium] content for non-Pro users behind a
 *                   clean upgrade teaser. Runs automatically on DOMContentLoaded.
 *
 * Inert until BOTH accounts (js/auth-config.js) and billing (js/premium-config.js)
 * are configured -- so the live site never shows a broken paywall.
 */
(function () {
  "use strict";
  var P = window.EDGESTAT_PREMIUM || {};
  var configured = typeof P.isConfigured === "function" && P.isConfigured();
  var _cache = null;

  async function token() {
    try {
      if (!window.EdgeStatAuth || !window.EdgeStatAuth.getClient) return null;
      var c = await window.EdgeStatAuth.getClient();
      if (!c) return null;
      var s = await c.auth.getSession();
      return (s && s.data && s.data.session && s.data.session.access_token) || null;
    } catch (e) { return null; }
  }

  async function getStatus() {
    if (_cache) return _cache;
    if (!configured) return (_cache = { pro: false, configured: false });
    var t = await token();
    if (!t) return { pro: false, signedIn: false };   // not cached -> re-check after sign-in
    try {
      var r = await fetch(P.apiBase.replace(/\/$/, "") + "/billing/status", { headers: { Authorization: "Bearer " + t } });
      var d = await r.json();
      _cache = { pro: !!d.pro, status: d.status, signedIn: true, configured: true };
      return _cache;
    } catch (e) { return { pro: false, error: true }; }
  }

  async function upgrade() {
    if (!configured) { alert("Premium is launching shortly."); return; }
    var t = await token();
    if (!t) { window.location.href = "login.html?next=pricing.html"; return; }
    try {
      var r = await fetch(P.apiBase.replace(/\/$/, "") + "/billing/create-checkout", {
        method: "POST", headers: { Authorization: "Bearer " + t, "Content-Type": "application/json" }, body: "{}",
      });
      var d = await r.json();
      if (d && d.url) { window.location.href = d.url; return; }
      alert((d && d.error) || "Could not start checkout. Please try again.");
    } catch (e) { alert("Could not start checkout. Please try again."); }
  }

  // Hide premium-only content behind a teaser for non-Pro users.
  async function gate(root) {
    var nodes = (root || document).querySelectorAll("[data-premium]");
    if (!nodes.length) return;
    var st = await getStatus();
    if (st.pro) return;   // Pro user: leave everything visible
    nodes.forEach(function (el) {
      if (el.dataset.premiumLocked) return;
      el.dataset.premiumLocked = "1";
      el.style.position = "relative";
      var teaser = document.createElement("div");
      teaser.style.cssText =
        "position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;" +
        "background:linear-gradient(180deg,rgba(10,12,16,.55),rgba(10,12,16,.92));backdrop-filter:blur(4px);" +
        "border-radius:10px;text-align:center;padding:18px;z-index:5;";
      teaser.innerHTML =
        '<div style="font-size:12px;font-weight:700;color:#e9edf4;">🔒 EdgeStat Pro</div>' +
        '<div style="font-size:11.5px;color:#aab3c5;max-width:260px;line-height:1.5;">' +
          (el.getAttribute("data-premium-msg") || "Unlock this with a Pro subscription.") + "</div>" +
        '<a href="pricing.html" style="margin-top:4px;padding:7px 14px;border-radius:7px;background:#58c878;color:#06250f;font-weight:700;font-size:12px;text-decoration:none;">See plans</a>';
      el.appendChild(teaser);
    });
  }

  window.EdgeStatPremium = { configured: configured, getStatus: getStatus, upgrade: upgrade, gate: gate };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { gate(); });
  else gate();
})();
