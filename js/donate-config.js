/* EdgeStat -- donations config (the no-LLC, no-merchant-account monetization path).
 *
 * Donations are NOT selling picks, so they dodge the "tout/payment-processor"
 * and licensing burden entirely. Pick a platform, paste your handle, set
 * enabled:true. Until then support.html shows a polite "coming soon" -- nothing
 * fake ships. Every value here is PUBLIC-safe (no secrets).
 *
 * Platforms (2-minute signup each, no gambling restrictions):
 *   kofi    -> https://ko-fi.com/<handle>
 *   bmc     -> https://www.buymeacoffee.com/<handle>     (Buy Me a Coffee)
 *   github  -> https://github.com/sponsors/<handle>      (GitHub Sponsors)
 *   paypal  -> https://www.paypal.me/<handle>
 */
window.EDGESTAT_DONATE = {
  enabled: false,
  platform: "kofi",        // "kofi" | "bmc" | "github" | "paypal"
  handle: "",              // your username on the chosen platform
  blurb: "EdgeStat is free and ad-light. If the models help your handicapping, a tip keeps the data feeds and late-night model runs going. No paywall, ever.",
};
