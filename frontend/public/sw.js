/* ChurchOS service worker: opens the app with no signal. It keeps the app's own files only.
   Anything under /api/ and anything from another website is never stored here. */
const SHELL = 'churchos-shell-v1';
const ASSET = /\.(?:png|jpg|jpeg|svg|ico|webp|woff2?|json)$/i;

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(SHELL).then(cache => cache.addAll(['/', '/index.html', '/manifest.json'])).catch(() => {})
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== SHELL).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    // Always try the network first so a new release shows up; fall back to the saved app when offline.
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(SHELL).then(cache => cache.put('/index.html', copy));
          return response;
        })
        .catch(() => caches.match('/index.html').then(saved => saved || caches.match('/')))
    );
    return;
  }

  if (url.pathname.startsWith('/static/') || ASSET.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then(saved => saved || fetch(request).then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(SHELL).then(cache => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
});
