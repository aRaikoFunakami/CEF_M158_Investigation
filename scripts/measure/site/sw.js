self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => { if (new URL(e.request.url).pathname === '/sw-probe') e.respondWith(new Response('from-sw')); });
