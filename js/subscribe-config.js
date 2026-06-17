// EdgeStat -- email capture config. NO-OP until you fill this in (the form
// renders a polite "coming soon" until then, so nothing fake ever ships).
//
// To go live: pick ONE provider, set enabled:true, and paste the public ID.
// Every value here is PUBLIC-safe (these IDs are *meant* to live in client
// HTML). NEVER put a secret API key in this file -- it ships to the browser.
//
//   formspree  -- easiest. Create a form at https://formspree.io (free tier
//                 = 50 submissions/mo), copy the form ID (the XXXXXXXX in
//                 https://formspree.io/f/XXXXXXXX) into formspreeId.
//   buttondown -- a real newsletter. Your username at buttondown.com/<user>.
//   custom     -- own it: a URL (e.g. a Cloudflare Worker) that accepts a
//                 JSON POST { email } and stores it. Set customEndpoint.
//
// After editing, just push -- no other code changes needed.
window.EDGESTAT_SUBSCRIBE = {
  enabled: true,
  provider: "formspree",      // "formspree" | "buttondown" | "custom"
  // Wired to Brandon's existing Formspree form by his explicit choice
  // (selected "Use existing DCF form" — Formspree blocks scripted creation of a
  // dedicated one). Tape signups arrive labeled (_subject "New EdgeStat / The
  // Tape subscriber" + a `source` field) so they're filterable from DCF leads.
  // Swap to a dedicated form anytime: just replace the id below and push.
  formspreeId: "xdayqzkj",    // shared with the DCF form by choice; swappable
  buttondownUser: "",         // e.g. "edgestat"
  customEndpoint: "",         // e.g. "https://edgestat-subscribe.<you>.workers.dev"
  // Copy shown above the input. Tweak freely.
  blurb: "Get the strongest signals in your inbox — steam, sharp moves, and fresh edges. No spam, unsubscribe anytime.",
};
