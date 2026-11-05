/* EdgeStat -- affiliate configuration (the monetization layer).
 *
 * Default monetization model = AFFILIATE (sportsbook revenue share). This is the
 * single place to wire real affiliate links once the LLC + operator affiliate
 * accounts are in place. Until then `enabled:false` keeps the page in a compliant
 * "partners coming soon" state — no live links, no false claims.
 *
 * To go live: set enabled:true and replace each book's `url` with your real,
 * state-targeted affiliate tracking link. Keep rel="sponsored nofollow noopener"
 * (sportsbooks.html enforces this) and keep the FTC disclosure visible.
 */
window.EDGESTAT_AFFILIATE = {
  enabled: false,

  // (2026-11-05) honest while enabled is false: there are NO affiliate links or
  // sportsbook partnerships today. Restore the commission wording only with real links.
  disclosure:
    "EdgeStat currently has no affiliate or sportsbook partnerships: nothing on this page " +
    "pays us. If that ever changes, the links will be marked and this disclosure updated first. " +
    "21+ only, where legal. Gambling problem? Call 1-800-GAMBLER.",

  // Operator cards. `url` "#" = not yet configured (rendered disabled).
  books: [
    { name: "DraftKings Sportsbook", code: "DK", url: "#", offer: "no partner link",
      note: "Available in most regulated US states." },
    { name: "FanDuel Sportsbook",    code: "FD", url: "#", offer: "no partner link",
      note: "Available in most regulated US states." },
    { name: "BetMGM",                code: "MGM", url: "#", offer: "no partner link",
      note: "Available in most regulated US states." },
    { name: "Caesars Sportsbook",    code: "CZR", url: "#", offer: "no partner link",
      note: "Available in most regulated US states." },
    { name: "Fanatics Sportsbook",   code: "FAN", url: "#", offer: "no partner link",
      note: "Available in select states." },
  ],
};
