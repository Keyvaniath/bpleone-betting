/* (2026-11-16) Display names for players. Several model tables key players by a lowercased name
   ("anthony edwards") because that is what the ledger matches on; pages show it properly cased.
   Display only: never feed the result back into a lookup. */
(function () {
  const EXACT = {
    lebron: "LeBron", demar: "DeMar", derozan: "DeRozan", lamelo: "LaMelo", lavine: "LaVine", deaaron: "De'Aaron",
    demarcus: "DeMarcus", deandre: "DeAndre", deanthony: "DeAnthony", javale: "JaVale", lamarcus: "LaMarcus",
    rj: "RJ", cj: "CJ", pj: "PJ", tj: "TJ", aj: "AJ", og: "OG", jj: "JJ", dj: "DJ", jt: "JT",
    ii: "II", iii: "III", iv: "IV", jr: "Jr.", "jr.": "Jr.", sr: "Sr.", "sr.": "Sr.",
    mcdavid: "McDavid", mccaffrey: "McCaffrey", mcconnell: "McConnell", mcdaniels: "McDaniels", mccollum: "McCollum",
    mackinnon: "MacKinnon", vanvleet: "VanVleet", dicaprio: "DiCaprio", divincenzo: "DiVincenzo",
  };
  const cap = (w) => w ? w.charAt(0).toUpperCase() + w.slice(1) : w;
  const word = (w) => {
    const k = w.toLowerCase();
    if (EXACT[k]) return EXACT[k];
    // hyphen and apostrophe parts each capitalised: gilgeous-alexander, o'neale
    return k.split("-").map((h) => h.split("'").map(cap).join("'")).join("-");
  };
  function nice(name) {
    const s = String(name == null ? "" : name).trim();
    if (!s || /[A-Z]/.test(s)) return s;                 // already cased by its source: leave it alone
    return s.split(/\s+/).map(word).join(" ");
  }
  window.EdgeName = { nice };
})();
