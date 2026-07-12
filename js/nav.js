// EdgeStat unified nav — DROP-IN REPLACEMENT for js/nav.js
// FIX: dropdowns were clipped by .mainnav's overflow:auto. Switching .dd-menu
// to position:fixed (with JS positioning from the button's bounding rect)
// escapes any current or future overflow setting on the nav container.
// Behavior is identical otherwise — same items, same active-page highlight,
// same click-outside-to-close, same toggle-on-second-click.
(function () {
  if (window.__edgestatNavInit) return;
  window.__edgestatNavInit = true;

  const SPORTS = [
    { href: "worldcup.html", label: "🏆 World Cup 2026" },
    { href: "mlb.html",   label: "MLB" },
    { href: "golf.html",  label: "Golf" },
    { href: "nba.html",   label: "NBA" },
    { href: "nhl.html",   label: "NHL" },
    { href: "wnba.html",  label: "WNBA" },
    { href: "mls.html",   label: "MLS" },
    { href: "epl.html",   label: "EPL" },
    { href: "ucl.html",   label: "UCL" },
    { href: "nfl.html",   label: "NFL" },
    { href: "ncaaf.html", label: "NCAAF" },
    { href: "ncaab.html", label: "NCAAB" },
    { href: "cws.html",   label: "NCAA Baseball" },
    { href: "kbo.html",   label: "KBO" },
    { href: "lol.html",   label: "LoL" },
    { href: "cs.html",    label: "CS" },
    { href: "f1.html",    label: "F1" },
    { href: "ufc.html",   label: "UFC" },
    { href: "tennis.html", label: "🎾 Tennis" },
  ];
  const PLAYERS = [
    { href: "nba-players.html",  label: "NBA Players" },
    { href: "wnba-players.html", label: "WNBA Players" },
    { href: "nhl-players.html",  label: "NHL Players" },
    { href: "lol-players.html",       label: "LoL Players" },
    { href: "cs-players.html",        label: "CS Players" },
    { href: "kbo-players.html",       label: "KBO Players" },
    { href: "player.html",            label: "MLB Player Search" },
  ];
  // PRIMARY bar items only -- kept short so the top bar never overflows into the
  // ticker / "Today's Play" button. The rest live in four INTENTIONAL, sectioned
  // dropdowns (Picks / Edges / Models / More) instead of one 49-item dump --
  // professional IA. { section } entries render as non-clickable group headers.
  const TOP = [
    { href: "index.html",       label: "Dashboard" },
    { href: "picks.html",       label: "🎯 Today's Picks" },
    { href: "play-of-day.html", label: "★ Play of Day" },
    { href: "tonight.html",     label: "🌙 Tonight" },
  ];
  // PICKS -- the actionable daily output. SLIMMED 2026-07-12 (site audit: 7
  // near-synonymous boards were listed with no guidance): the nav keeps ONE
  // canonical entry per job; everything cut stays reachable by URL and from
  // in-page links (top-edges/confluence/alpha-scanner/props-parlay/parlays/
  // pickem were dropped from the MENU only, not the site).
  const PICKS = [
    { section: "Daily Board" },
    { href: "picks.html",               label: "🎯 Today's Picks (all boards)" },
    { href: "alpha-pick.html",          label: "★ Alpha Pick of the Day" },
    { href: "high-confidence.html",     label: "💎 High-Confidence Board" },
    { href: "best-bets.html",           label: "✓ Best Bets" },
    { href: "alerts.html",              label: "📡 The Tape (live signals)" },
    { section: "Parlays & DFS" },
    { href: "cross-sport-parlays.html", label: "🎰 Cross-Sport Parlays" },
    { href: "prizepicks-value.html",    label: "🃏 PrizePicks Value" },
    { href: "props.html",               label: "Player Props" },
  ];
  // EDGES -- market & line analysis, matchups, live. SLIMMED 2026-07-12: one
  // canonical entry per job; cut items remain reachable by URL / in-page links.
  const EDGES = [
    { section: "Markets & Lines" },
    { href: "book-edges.html",          label: "📊 Book Edges" },
    { href: "deep-edges.html",          label: "🔬 Deep Edges" },
    { href: "line-movement.html",       label: "📈 Line Movement / Steam" },
    { href: "line-shop.html",           label: "💰 Line Shop" },
    { section: "MLB Matchups" },
    { href: "pitcher-matchup.html",     label: "⚾ Pitcher Matchup" },
    { href: "batter-sp-edges.html",     label: "🎯 Batter vs SP Edges" },
    { href: "batter-splits.html",       label: "📊 Batter Splits" },
    { section: "Live" },
    { href: "live-now.html",            label: "Live Now" },
    { href: "golf-live.html",           label: "⛳ Golf Live" },
  ];
  // MODELS -- the quant: proof first, then the lab. SLIMMED 2026-07-12 (site
  // audit: ~16 overlapping proof/performance pages were all listed): the nav
  // keeps the canonical entry per job -- Track Record IS the proof page,
  // Methodology IS the how, calibration-map IS the calibration view. Cut items
  // (proof, models, research, model-cards, simulator, backtest*, residuals,
  // reliability, pod-history, lifecycle, module-performance, audit,
  // learning-integrity, model-control) stay reachable by URL / in-page links.
  const MODELS = [
    { section: "Performance & Proof" },
    { href: "track-record.html",        label: "⟁ Track Record (the proof)" },
    { href: "calibration-map.html",     label: "🎯 Model Calibration" },
    { href: "strategy-sim.html",        label: "🎛️ Strategy Simulator" },
    { href: "clv.html",                 label: "🎯 Closing Line Value" },
    { section: "Lab" },
    { href: "methodology.html",         label: "📐 Methodology" },
    { href: "ml-lab.html",              label: "ML Lab" },
    { href: "model-health.html",        label: "🏥 Model Health" },
    { href: "live-learning.html",       label: "📡 Live Learning (hub)" },
  ];
  // MORE -- account, system, daily read, education. SLIMMED 2026-07-12: legal
  // links (terms/privacy/disclaimer/affiliate/responsible-gambling) live in the
  // GLOBAL FOOTER on every page, so they left the menu; bet-slate/hedge/config/
  // data-health/data-integrity/sport-coverage/pulse/train-your-read/daily-
  // summary/brief/data-sources remain reachable by URL / in-page links.
  const MORE = [
    { section: "Account & Bets" },
    { href: "support.html",             label: "♥ Support / Tip" },
    { href: "pricing.html",             label: "⭐ Pricing / Go Pro" },
    { href: "sportsbooks.html",         label: "🎟 Where to Bet" },
    { href: "bankroll.html",            label: "Bankroll" },
    { href: "my-bets.html",             label: "My Bets" },
    { section: "System & Reads" },
    { href: "status.html",              label: "🟢 System Status" },
    { href: "todays-brief.html",        label: "📋 Today's Master Brief" },
    { section: "Learn" },
    { href: "learn.html",               label: "🎓 EdgeStat Academy" },
    { href: "about.html",               label: "About" },
  ];

  function buildDropdown(label, items, currentPath) {
    const ddId = "dd_" + label.replace(/[^a-z0-9]/gi, "_");
    let seenSection = false;
    const itemsHtml = items.map(i => {
      if (i.section) {
        const bt = seenSection ? "border-top:1px solid rgba(255,255,255,0.06);margin-top:5px;" : "";
        seenSection = true;
        return `<div style="font-size:9px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted,#6b7280);padding:8px 10px 4px;${bt}">${i.section}</div>`;
      }
      const active = currentPath === i.href.toLowerCase();
      const col = active ? "var(--accent,#d4a04a)" : "var(--text-2,#aaa)";
      const wt = active ? "font-weight:600;" : "";
      return `<a href="${i.href}" style="display:block;padding:6px 10px;font-size:12px;color:${col};${wt}text-decoration:none;border-radius:4px;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background=''">${i.label}</a>`;
    }).join("");
    // position:fixed so the .mainnav's overflow:auto can't clip the menu;
    // top/left are set by JS from the button's getBoundingClientRect() each
    // time the menu opens. z-index 10000 keeps it above the topbar (z 100).
    return `<div class="dd-wrap" style="position:relative; display:inline-block;">
      <button type="button" class="dd-btn" data-dd="${ddId}" style="background:none;border:none;color:var(--text-2,#aaa);font-size:12px;font-weight:500;padding:3px 6px;cursor:pointer;font-family:inherit;border-bottom:2px solid transparent;">${label} ▾</button>
      <div class="dd-menu" id="${ddId}" style="display:none;position:fixed;top:0;left:0;background:#0c0e13;border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:6px;min-width:212px;z-index:10000;box-shadow:0 8px 24px rgba(0,0,0,0.4);max-height:74vh;overflow-y:auto;">
        ${itemsHtml}
      </div>
    </div>`;
  }

  function buildNav() {
    const path = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    const topHtml = TOP.map(i => {
      const active = path === i.href.toLowerCase() ? ' class="active"' : "";
      return `<a href="${i.href}"${active}>${i.label}</a>`;
    }).join("");
    const sportsDd = buildDropdown("Sports", SPORTS, path);
    const playersDd = buildDropdown("Players", PLAYERS, path);
    const picksDd = buildDropdown("Picks", PICKS, path);
    const edgesDd = buildDropdown("Edges", EDGES, path);
    const modelsDd = buildDropdown("Models", MODELS, path);
    const moreDd = buildDropdown("More", MORE, path);
    return topHtml + sportsDd + playersDd + picksDd + edgesDd + modelsDd + moreDd;
  }

  // Anchor the fixed-position menu to the button's current screen position.
  // Called every time a menu opens, and on scroll/resize while any is open.
  function positionMenu(btn, menu) {
    const r = btn.getBoundingClientRect();
    menu.style.top = (r.bottom + 4) + 'px';
    menu.style.left = r.left + 'px';
    // Keep menu inside viewport horizontally
    const vw = window.innerWidth || document.documentElement.clientWidth;
    const menuW = menu.offsetWidth || 200;
    if (r.left + menuW > vw - 8) {
      menu.style.left = Math.max(8, vw - menuW - 8) + 'px';
    }
  }

  function installNav() {
    const nav = document.querySelector("nav.mainnav");
    if (!nav) return;
    nav.innerHTML = buildNav();

    document.querySelectorAll(".dd-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.dataset.dd;
        const menu = document.getElementById(id);
        if (!menu) return;
        // Close every other menu first
        document.querySelectorAll(".dd-menu").forEach(m => { if (m !== menu) m.style.display = "none"; });
        const wasOpen = menu.style.display === "block";
        if (wasOpen) {
          menu.style.display = "none";
        } else {
          // Show first so offsetWidth measures correctly, then anchor.
          menu.style.display = "block";
          positionMenu(btn, menu);
        }
      });
    });

    // Reposition any open menu on scroll/resize so it stays glued to its button.
    const reposition = () => {
      document.querySelectorAll(".dd-menu").forEach(m => {
        if (m.style.display !== "block") return;
        const btn = document.querySelector(`[data-dd="${m.id}"]`);
        if (btn) positionMenu(btn, m);
      });
    };
    window.addEventListener("scroll", reposition, { passive: true });
    window.addEventListener("resize", reposition);

    // Close on outside click
    document.addEventListener("click", e => {
      if (!e.target.closest(".dd-wrap") && !e.target.closest(".dd-menu")) {
        document.querySelectorAll(".dd-menu").forEach(m => m.style.display = "none");
      }
    });
  }

  // Site-wide customer-auth loader: pulls in the (free, passwordless) account
  // system on every page so the Sign-In / Account chip appears in the top bar.
  // Skipped on pages that already include auth.js explicitly (login/account),
  // and a no-op until accounts are configured in js/auth-config.js.
  function loadAuth() {
    if (document.querySelector('script[src*="js/auth.js"]')) return;
    var cfg = document.createElement("script"); cfg.src = "js/auth-config.js"; cfg.async = false;
    var lib = document.createElement("script"); lib.src = "js/auth.js"; lib.async = false;
    document.head.appendChild(cfg);
    document.head.appendChild(lib);
  }

  // Site-wide compliance layer (responsible-gambling + legal footer, 21+ age gate).
  // Required on every page of a betting-content site; no-op if already loaded.
  function loadCompliance() {
    if (window.__edgestatCompliance || document.querySelector('script[src*="js/compliance.js"]')) return;
    window.__edgestatCompliance = true;
    var s = document.createElement("script"); s.src = "js/compliance.js"; s.async = false;
    document.head.appendChild(s);
  }

  function boot() { installNav(); loadAuth(); loadCompliance(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
