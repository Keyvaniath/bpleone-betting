// EdgeStat -- nav badge for /config recommendations.
// Fetches param_recommendations.json and decorates the Config nav link
// with a count badge so the operator notices when the model wants a tweak.
// Pure vanilla, no deps. Safe to include on every page.
(function(){
  if (window.__edgestatNavBadge) return;
  window.__edgestatNavBadge = true;
  function decorate(n) {
    if (!n) return;
    var links = document.querySelectorAll('.mainnav a[href="config.html"]');
    links.forEach(function(a){
      if (a.querySelector('.nav-badge')) return;
      var b = document.createElement('span');
      b.className = 'nav-badge';
      b.textContent = n;
      b.title = n + ' model recommendation' + (n===1?'':'s') + ' on /config';
      b.style.cssText = 'display:inline-block;margin-left:6px;padding:1px 6px;border-radius:9px;background:#d4a04a;color:#1a1a1a;font-size:9px;font-weight:700;vertical-align:middle;font-family:JetBrains Mono,monospace;';
      a.appendChild(b);
    });
  }
  function run(){
    try {
      fetch('data/param_recommendations.json', {cache:'no-cache'})
        .then(function(r){ return r.json(); })
        .then(function(p){
          var n = (p && p.recommendations && p.recommendations.length) || 0;
          if (n) decorate(n);
        })
        .catch(function(){});
    } catch(e) {}
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
