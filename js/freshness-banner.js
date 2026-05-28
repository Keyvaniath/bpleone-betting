/*
 * EdgeStat -- data staleness banner.
 *
 * Self-contained, dependency-free. Reads data/data_freshness_audit.json and
 * data/today.json, and shows a banner at the top of the page IF the slate is
 * stale (today.json not dated today) OR freshness_pct is low OR the odds feed
 * is down. Auto-hides as soon as the data is fresh again -- no code change
 * needed once the ODDS_API_KEY is renewed and the pipeline repopulates.
 */
(function () {
  "use strict";

  var BANNER = document.getElementById("staleBanner");
  if (!BANNER) return;

  // Thresholds
  var FRESHNESS_WARN_PCT = 70;   // below this -> warn
  var STALE_AGE_HOURS = 30;      // today.json older than this -> warn

  function ymd(d) {
    return d.getUTCFullYear() + "-" +
      String(d.getUTCMonth() + 1).padStart(2, "0") + "-" +
      String(d.getUTCDate()).padStart(2, "0");
  }

  function parseTs(s) {
    if (!s) return null;
    // Accept "2026-05-26T23:12:13" or with Z
    var t = Date.parse(s.endsWith("Z") ? s : s + "Z");
    return isNaN(t) ? null : t;
  }

  function fetchJson(path) {
    return fetch(path, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  Promise.all([
    fetchJson("data/data_freshness_audit.json"),
    fetchJson("data/today.json"),
  ]).then(function (res) {
    var fresh = res[0] || {};
    var today = res[1] || {};

    var reasons = [];

    // 1) Slate age
    var slateTs = parseTs(today.generated_at || today.date || today.updated);
    var slateDateStr = null;
    if (slateTs) {
      var ageH = (Date.now() - slateTs) / 3.6e6;
      slateDateStr = ymd(new Date(slateTs));
      var todayStr = ymd(new Date());
      if (slateDateStr !== todayStr || ageH > STALE_AGE_HOURS) {
        reasons.push("slate is from " + slateDateStr +
          " (≈" + Math.round(ageH) + "h old)");
      }
    }

    // 2) Freshness pct
    var fp = (typeof fresh.freshness_pct === "number") ? fresh.freshness_pct : null;
    if (fp !== null && fp < FRESHNESS_WARN_PCT) {
      var nStale = fresh.n_stale_or_missing || (fresh.stale_files || []).length || 0;
      reasons.push("data freshness " + fp + "% (" + nStale + " feeds stale)");
    }

    // 3) Odds feed down -- detect via empty bet_slate / props (best-effort, optional)
    // Done lightly: if today.json carries an odds_status flag, surface it.
    if (today.odds_status && /down|fail|401|unauthor/i.test(today.odds_status)) {
      reasons.push("odds feed down");
    }

    if (!reasons.length) {
      BANNER.hidden = true;
      return;
    }

    BANNER.hidden = false;
    BANNER.innerHTML =
      '<span class="stale-banner-dot"></span>' +
      '<span class="stale-banner-text">' +
      '<strong>Heads up —</strong> ' + reasons.join(" · ") +
      '. Model projections are live; book-edge values refresh when the odds feed reconnects.' +
      '</span>' +
      '<button class="stale-banner-x" aria-label="dismiss" ' +
      'onclick="this.parentElement.hidden=true">×</button>';
  });
})();
