// EdgeStat -- personal bet tracker (client-side persistence).
//
// Adds a "I BET THIS" / "SKIPPED" toggle next to every play that the
// model surfaces. State lives in localStorage so it persists across
// sessions and pages. The data:
//
//   key: edgestat:bets  -> { [bet_key]: { status: "bet"|"skip"|null,
//                                          stake_units: 1.0,
//                                          ts: "...",
//                                          play, line, market, player_id, source } }
//
// On each page load, after the prop tables render, we walk every prop row
// (matched by data-bet-key="src|player_id|market|line") and append a
// status pill + click handler.
//
// A small summary line at the top of /track-record shows the operator's
// actual hit rate on bets they actually placed.

(function () {
  const KEY = "edgestat:bets";
  const STAKE_DEFAULT = 1.0;
  // Cache localStorage state during a tag pass to avoid hundreds of reads
  // when a page has 150+ data-bet-key elements.
  let _stateCache = null;
  function loadState() {
    if (_stateCache !== null) return _stateCache;
    try { _stateCache = JSON.parse(localStorage.getItem(KEY)) || {}; }
    catch (e) { _stateCache = {}; }
    return _stateCache;
  }
  function saveState(s) {
    _stateCache = s;
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
  }
  function invalidateCache() { _stateCache = null; }

  function keyFor(el) {
    return el.getAttribute("data-bet-key");
  }

  function colorForStatus(s) {
    if (s === "bet")  return { bg: "rgba(88,200,120,0.18)", fg: "#58c878", lbl: "BET" };
    if (s === "skip") return { bg: "rgba(212,160,74,0.15)", fg: "#d4a04a", lbl: "SKIPPED" };
    return { bg: "rgba(255,255,255,0.05)", fg: "var(--muted, #888)", lbl: "TRACK" };
  }

  function renderPill(el) {
    const state = loadState();
    const k = keyFor(el);
    if (!k) return;
    const rec = state[k] || {};
    const c = colorForStatus(rec.status);
    let pill = el.querySelector(".bt-pill");
    if (!pill) {
      pill = document.createElement("button");
      pill.className = "bt-pill";
      pill.type = "button";
      pill.style.cssText = "border:none; padding:2px 8px; border-radius:3px; font-size:9px; font-weight:700; cursor:pointer; margin-left:6px; letter-spacing:0.05em; font-family:inherit;";
      pill.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        const s = loadState();
        const r = s[k] || {};
        // Cycle: null -> bet -> skip -> null
        const cur = r.status || null;
        const next = cur === null ? "bet" : cur === "bet" ? "skip" : null;
        if (next === null) {
          delete s[k];
        } else {
          s[k] = {
            status: next,
            stake_units: r.stake_units || STAKE_DEFAULT,
            ts: new Date().toISOString(),
            label: el.getAttribute("data-bet-label") || "",
            player_id: el.getAttribute("data-bet-pid") || null,
            market: el.getAttribute("data-bet-market") || null,
            line: el.getAttribute("data-bet-line") || null,
            play: el.getAttribute("data-bet-play") || null,
            source: el.getAttribute("data-bet-src") || null,
          };
        }
        saveState(s);
        renderPill(el);
        updateGlobalSummary();
      });
      el.appendChild(pill);
    }
    pill.textContent = c.lbl;
    pill.style.background = c.bg;
    pill.style.color = c.fg;
  }

  function tagAll() {
    document.querySelectorAll("[data-bet-key]").forEach(renderPill);
  }

  // Lightweight global summary -- floats in the corner if at least 1 bet
  function updateGlobalSummary() {
    const s = loadState();
    const bets = Object.values(s).filter(r => r.status === "bet");
    let el = document.getElementById("bt-summary");
    if (!el) {
      el = document.createElement("div");
      el.id = "bt-summary";
      el.style.cssText = "position:fixed; bottom:14px; right:14px; padding:8px 14px; border-radius:6px; background:rgba(0,0,0,0.85); border:1px solid rgba(212,160,74,0.45); color:#d4a04a; font-family:'JetBrains Mono',monospace; font-size:11px; z-index:9999; cursor:pointer;";
      el.title = "Personal bet tracker -- click to view ledger";
      el.addEventListener("click", () => location.href = "my-bets.html");
      document.body.appendChild(el);
    }
    if (!bets.length) {
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    const totalUnits = bets.reduce((s, b) => s + (b.stake_units || 1), 0);
    el.innerHTML = `📒 <strong>${bets.length}</strong> bet${bets.length===1?'':'s'} tonight · ${totalUnits.toFixed(1)}u staked · <span style="text-decoration: underline;">view</span>`;
  }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  ready(function () {
    // Only re-tag after fetch.then() resolves. Pages call window.EdgeStatBets.tagAll()
    // after rendering rows. No setInterval or MutationObserver (those caused
    // page hangs due to localStorage reads per data-bet-key element).
    // Delay initial tag by 500ms so fetch().then() typically completes first.
    setTimeout(function() {
      tagAll();
      updateGlobalSummary();
    }, 500);
    // Re-tag once more at 3s to catch slow fetches.
    setTimeout(function() {
      tagAll();
    }, 3000);
  });
  window.EdgeStatBets = window.EdgeStatBets || {};
  window.EdgeStatBets.tagAll = tagAll;

  // Expose API for /my-bets page
  window.EdgeStatBets = {
    list: loadState,
    clear: function () { saveState({}); updateGlobalSummary(); tagAll(); },
    export: function () {
      const s = loadState();
      const rows = Object.entries(s).map(([k, v]) => ({ key: k, ...v }));
      return JSON.stringify(rows, null, 2);
    },
  };
})();
