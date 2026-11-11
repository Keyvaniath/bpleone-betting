// Parse every inline <script> of every root page (no execution) and every js/*.js file.
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[2];
let bad = 0, n = 0;
const check = (code, label) => { n++; try { new vm.Script(code, { filename: label }); } catch (e) { bad++; console.log("SYNTAX", label, "-", e.message); } };
for (const f of fs.readdirSync(root).filter(f => f.endsWith(".html"))) {
  const html = fs.readFileSync(path.join(root, f), "utf8");
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi; let m, i = 0;
  while ((m = re.exec(html))) {
    i++;
    if (/\bsrc\s*=/.test(m[1]) || !m[2].trim()) continue;
    if (/type\s*=\s*["'](application\/(ld\+)?json|text\/template|importmap)/i.test(m[1])) continue;
    if (/type\s*=\s*["']module/i.test(m[1])) continue;
    check(m[2], f + "#script" + i);
  }
}
for (const f of fs.readdirSync(path.join(root, "js")).filter(f => f.endsWith(".js"))) check(fs.readFileSync(path.join(root, "js", f), "utf8"), "js/" + f);
check(fs.readFileSync(path.join(root, "sw.js"), "utf8"), "sw.js");
console.log("parsed", n, "scripts;", bad, "with syntax errors");
process.exit(bad ? 1 : 0);
