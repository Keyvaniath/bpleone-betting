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

  disclosure:
    "Some links below are affiliate links. If you register or deposit through them, " +
    "EdgeStat may earn a commission at no extra cost to you. This never affects our " +
    "models or track record. 21+ only, where legal. Gambling problem? Call 1-800-GAMBLER.",

  // Operator cards. `url` "#" = not yet configured (rendered disabled).
  books: [
    { name: "DraftKings Sportsbook", code: "DK", url: "#", offer: "[configure affiliate link]",
      note: "Available in most regulated US states." },
    { name: "FanDuel Sportsbook",    code: "FD", url: "#", offer: "[configure affiliate link]",
      note: "Available in most regulated US states." },
    { name: "BetMGM",                code: "MGM", url: "#", offer: "[configure affiliate link]",
      note: "Available in most regulated US states." },
    { name: "Caesars Sportsbook",    code: "CZR", url: "#", offer: "[configure affiliate link]",
      note: "Available in most regulated US states." },
    { name: "Fanatics Sportsbook",   code: "FAN", url: "#", offer: "[configure affiliate link]",
      note: "Available in select states." },
  ],
};
