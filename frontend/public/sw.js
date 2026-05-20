// PharmaOS Service Worker — cache offline minimal pour la caisse
//
// Stratégie :
// - Assets statiques (HTML, JS, CSS, icônes) : cache-first
// - API (/api/*) : network-first avec fallback offline message
// - Mode hors ligne : la SPA reste utilisable pour consulter les données mises en cache
//   par TanStack Query, et les nouvelles ventes sont mises en file (à implémenter dans l'app)

const CACHE_VERSION = "pharmaos-v1";
const ASSETS_CACHE = `${CACHE_VERSION}-assets`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(ASSETS_CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Purger les anciennes versions
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => !n.startsWith(CACHE_VERSION))
          .map((n) => caches.delete(n))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Bypass : non-GET, requêtes externes, websocket
  if (event.request.method !== "GET" || url.origin !== location.origin) {
    return;
  }

  // API : network-first
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(
          JSON.stringify({
            detail: "Hors ligne — cette opération nécessite une connexion.",
            offline: true,
          }),
          {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );
    return;
  }

  // Assets statiques + SPA shell : cache-first avec mise à jour en arrière-plan
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((response) => {
          // Mettre en cache les assets statiques (immutables Vite hash)
          if (response.ok && /\.(js|css|woff2?|png|svg|ico)$/.test(url.pathname)) {
            const clone = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached || caches.match("/"));
      return cached || fetchPromise;
    })
  );
});
