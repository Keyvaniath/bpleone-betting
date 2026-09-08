/* EdgeStat service worker -- makes the site installable (PWA) and keeps the
   app shell usable offline. DATA IS NEVER CACHED: every data/*.json request
   goes to the network, because a stale pick or line shown as current is
   exactly the failure this site exists to avoid. Only static shell assets
   (HTML/CSS/JS/icons) are cached, network-first, so a fresh deploy wins. */
const VERSION = 'edgestat-shell-v1';
const SHELL = ['/', '/index.html', '/css/style.css', '/js/nav.js', '/manifest.json',
               '/assets/icons/icon-192.png', '/assets/icons/icon-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/data/')) return;           // live data: network only, never cached
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request).then(m => m || caches.match('/index.html')))
  );
});
