/* EdgeStat -- site-wide compliance layer (loaded on every page by nav.js).
 *
 * Two responsibilities, both required for a legitimate betting-content site:
 *   1) A persistent responsible-gambling + legal footer (21+, 1-800-GAMBLER,
 *      NCPG, links to Terms / Privacy / Responsible Gambling / Disclaimer).
 *   2) A first-visit 21+ age-verification gate (remembered in localStorage).
 *
 * No backend, no dependencies. Self-boots. Safe to load once per page.
 */
(function () {
  "use strict";
  var AGE_KEY = "edgestat_age_verified_v1";
  var RG_LINKS = [
    ["Responsible Gambling", "responsible-gambling.html"],
    ["Terms", "terms.html"],
    ["Privacy", "privacy.html"],
    ["Disclaimer", "disclaimer.html"],
    ["Affiliate Disclosure", "affiliate-disclosure.html"],
  ];

  // ---------------------------------------------------------------- footer ---
  function installFooter() {
    if (document.getElementById("edgestat-compliance-bar")) return;
    var links = RG_LINKS.map(function (l) {
      return '<a href="' + l[1] + '" style="color:#9aa7bd;text-decoration:none;border-bottom:1px dotted rgba(154,167,189,.5);">' + l[0] + "</a>";
    }).join('<span style="opacity:.4;">·</span>');

    var bar = document.createElement("footer");
    bar.id = "edgestat-compliance-bar";
    bar.setAttribute("role", "contentinfo");
    bar.style.cssText =
      "margin-top:40px;padding:18px 16px 26px;border-top:1px solid rgba(255,255,255,.08);" +
      "background:rgba(0,0,0,.25);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" +
      "font-size:11.5px;line-height:1.7;color:#8a93a6;text-align:center;";
    bar.innerHTML =
      '<div style="max-width:1000px;margin:0 auto;display:flex;flex-direction:column;gap:8px;align-items:center;">' +
        '<div style="display:flex;gap:9px;flex-wrap:wrap;justify-content:center;align-items:center;font-weight:600;color:#c2cadb;">' +
          '<span style="border:1px solid #d98b4a;color:#e8a866;border-radius:4px;padding:1px 7px;font-size:11px;">21+</span>' +
          '<span>Gambling problem? Call <a href="tel:1-800-426-2537" style="color:#e8a866;text-decoration:none;">1-800-GAMBLER</a></span>' +
          '<span style="opacity:.4;">·</span>' +
          '<a href="https://www.ncpgambling.org/" target="_blank" rel="noopener nofollow" style="color:#9aa7bd;text-decoration:none;border-bottom:1px dotted rgba(154,167,189,.5);">NCPG</a>' +
        "</div>" +
        '<div style="display:flex;gap:9px;flex-wrap:wrap;justify-content:center;align-items:center;">' + links + "</div>" +
        '<div style="max-width:760px;color:#6b7280;">EdgeStat publishes <strong>informational sports analytics for entertainment</strong>. ' +
          "It is <strong>not betting advice</strong>, and no outcome or return is guaranteed. Past performance does not predict future results. " +
          "Must be 21+ (or the legal age in your jurisdiction) and physically located where sports wagering is legal. " +
          "EdgeStat does not accept or place wagers. Please bet responsibly." +
        "</div>" +
        '<div style="color:#5b6373;">&copy; ' + "2026" + ' bpleone.com · EdgeStat</div>' +
      "</div>";
    document.body.appendChild(bar);
  }

  // -------------------------------------------------------------- age gate ---
  function verified() {
    try { return localStorage.getItem(AGE_KEY) === "yes"; } catch (e) { return false; }
  }
  function remember() {
    try { localStorage.setItem(AGE_KEY, "yes"); } catch (e) {}
  }

  function installAgeGate() {
    if (verified() || document.getElementById("edgestat-age-gate")) return;

    var ov = document.createElement("div");
    ov.id = "edgestat-age-gate";
    ov.style.cssText =
      "position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;" +
      "padding:20px;background:rgba(6,8,12,.92);backdrop-filter:blur(6px);" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;";
    ov.innerHTML =
      '<div role="dialog" aria-modal="true" aria-label="Age verification" style="max-width:440px;width:100%;background:#0d1017;' +
        'border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:30px 28px;text-align:center;box-shadow:0 24px 60px rgba(0,0,0,.6);">' +
        '<div style="font-size:30px;margin-bottom:6px;">⟁</div>' +
        '<div style="font-size:19px;font-weight:700;color:#e9edf4;margin-bottom:4px;">Welcome to EdgeStat</div>' +
        '<div style="font-size:13px;color:#aab3c5;line-height:1.6;margin-bottom:8px;">' +
          "You must be <strong>21 or older</strong> (or the legal age for sports wagering in your jurisdiction) to enter." +
        "</div>" +
        '<div style="font-size:11.5px;color:#7a8497;line-height:1.6;margin-bottom:20px;">' +
          "EdgeStat is informational analytics for entertainment — not betting advice. By entering you confirm you meet the age requirement and accept our " +
          '<a href="terms.html" style="color:#9aa7bd;">Terms</a> and <a href="privacy.html" style="color:#9aa7bd;">Privacy Policy</a>.' +
        "</div>" +
        '<div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">' +
          '<button id="edgestat-age-yes" style="flex:1;min-width:150px;padding:11px 16px;border:none;border-radius:8px;cursor:pointer;' +
            'background:#58c878;color:#06250f;font-weight:700;font-size:14px;">I am 21 or older — Enter</button>' +
          '<button id="edgestat-age-no" style="flex:1;min-width:120px;padding:11px 16px;border:1px solid rgba(255,255,255,.16);border-radius:8px;cursor:pointer;' +
            'background:transparent;color:#aab3c5;font-weight:600;font-size:14px;">Under 21 — Exit</button>' +
        "</div>" +
        '<div style="font-size:10.5px;color:#5b6373;margin-top:16px;">Gambling problem? Call 1-800-GAMBLER.</div>' +
      "</div>";

    // Prevent scroll behind the gate.
    var prevOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.body.appendChild(ov);

    document.getElementById("edgestat-age-yes").addEventListener("click", function () {
      remember();
      document.documentElement.style.overflow = prevOverflow;
      ov.remove();
    });
    document.getElementById("edgestat-age-no").addEventListener("click", function () {
      ov.innerHTML =
        '<div style="max-width:440px;width:100%;background:#0d1017;border:1px solid rgba(255,255,255,.1);border-radius:14px;' +
          'padding:34px 28px;text-align:center;color:#aab3c5;font-family:inherit;">' +
          '<div style="font-size:30px;margin-bottom:10px;">🔒</div>' +
          '<div style="font-size:18px;font-weight:700;color:#e9edf4;margin-bottom:8px;">Access restricted</div>' +
          '<div style="font-size:13px;line-height:1.6;">You must be 21 or older to access EdgeStat. ' +
            "If you or someone you know has a gambling problem, call <strong>1-800-GAMBLER</strong> or visit " +
            '<a href="https://www.ncpgambling.org/" target="_blank" rel="noopener nofollow" style="color:#9aa7bd;">ncpgambling.org</a>.</div>' +
        "</div>";
    });
  }

  function boot() { installFooter(); installAgeGate(); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
