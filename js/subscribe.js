// EdgeStat -- email capture widget. Renders into a container and POSTs to the
// provider configured in subscribe-config.js. Until that's enabled it shows a
// "coming soon" line, so the product never ships a fake form.
//
//   EdgeStatSubscribe.mount(el)   // el = a container element or its id
//
// No dependencies. State (already-subscribed) cached in localStorage so a
// returning subscriber isn't re-prompted.
(function () {
  const LS = "edgestat:subscribed";
  const cfg = () => window.EDGESTAT_SUBSCRIBE || {};
  const ACCENT = "#58c878";

  function valid(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }
  function done() {
    try { return localStorage.getItem(LS) === "1"; } catch (e) { return false; }
  }
  function markDone() {
    try { localStorage.setItem(LS, "1"); } catch (e) {}
  }

  // Returns a promise that resolves true on success, rejects with a message.
  function submit(email) {
    const c = cfg();
    if (c.provider === "custom" && c.customEndpoint) {
      return fetch(c.customEndpoint, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, source: "the-tape" }),
      }).then(r => { if (!r.ok) throw new Error("That didn't go through — try again in a moment."); return true; });
    }
    if (c.provider === "buttondown" && c.buttondownUser) {
      const body = new URLSearchParams({ email: email, embed: "1" });
      return fetch("https://buttondown.com/api/emails/embed", {
        method: "POST", body,
      }).then(r => { if (!r.ok && r.status !== 0) throw new Error("Subscription failed — try again."); return true; });
    }
    if (c.provider === "formspree" && c.formspreeId) {
      const fd = new FormData();
      fd.append("email", email);
      fd.append("_subject", "New EdgeStat / The Tape subscriber");
      return fetch("https://formspree.io/f/" + c.formspreeId, {
        method: "POST", body: fd, headers: { Accept: "application/json" },
      }).then(r => { if (!r.ok) throw new Error("Subscription failed — try again."); return true; });
    }
    return Promise.reject(new Error("not-configured"));
  }

  function configured() {
    const c = cfg();
    if (!c.enabled) return false;
    if (c.provider === "formspree") return !!c.formspreeId;
    if (c.provider === "buttondown") return !!c.buttondownUser;
    if (c.provider === "custom") return !!c.customEndpoint;
    return false;
  }

  function mount(target) {
    const el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el) return;
    const c = cfg();

    if (!configured()) {
      el.innerHTML = `<span style="color:var(--muted,#8a93a6);font-size:12.5px;">📬 Email alerts are coming soon. For now the feed refreshes here every couple of hours — bookmark it.</span>`;
      return;
    }
    if (done()) {
      el.innerHTML = `<span style="color:${ACCENT};font-size:13px;">✓ You're on the list. The strongest signals will hit your inbox.</span>`;
      return;
    }

    el.innerHTML = `
      ${c.blurb ? `<div style="font-size:12.5px;color:var(--text-2,#9fb0c8);margin-bottom:8px;line-height:1.5;">${c.blurb}</div>` : ""}
      <form id="subForm" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <input id="subEmail" type="email" required placeholder="you@email.com" autocomplete="email"
          style="flex:1;min-width:200px;background:var(--bg-2,#11151c);border:1px solid var(--border,#222a36);color:var(--text,#e8edf4);border-radius:7px;padding:9px 12px;font-size:13px;font-family:inherit;">
        <button id="subBtn" type="submit"
          style="border:1px solid rgba(88,200,120,.4);background:rgba(88,200,120,.14);color:#7ff0b5;padding:9px 18px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;white-space:nowrap;">Notify me</button>
      </form>
      <div id="subMsg" style="font-size:11.5px;margin-top:7px;min-height:14px;"></div>`;

    const form = el.querySelector("#subForm");
    const input = el.querySelector("#subEmail");
    const btn = el.querySelector("#subBtn");
    const msg = el.querySelector("#subMsg");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const email = (input.value || "").trim();
      if (!valid(email)) { msg.style.color = "#ff8a8a"; msg.textContent = "Enter a valid email."; return; }
      btn.disabled = true; btn.textContent = "…"; msg.textContent = "";
      submit(email).then(function () {
        markDone();
        el.innerHTML = `<span style="color:${ACCENT};font-size:13px;">✓ You're in. Watch your inbox for the strongest plays.</span>`;
      }).catch(function (err) {
        btn.disabled = false; btn.textContent = "Notify me";
        msg.style.color = "#ff8a8a";
        msg.textContent = err && err.message === "not-configured"
          ? "Email signup isn't switched on yet." : (err.message || "Something went wrong.");
      });
    });
  }

  window.EdgeStatSubscribe = { mount: mount, configured: configured };
})();
