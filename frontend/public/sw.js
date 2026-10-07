/* AgriGPT service worker: offline data + immutable-asset caching.
   Strategy (v9):
   - Never cache POST/AI requests (always network).
   - Never cache page HTML: a stale shell references dead hashed chunks from
     an older build and hard-crashes the app on load (two prior incidents).
     Pages are always fetched live; the browser handles offline errors.
   - Static assets: cache-first, only when the filename carries a content hash.
   - API GETs: network-first with cache fallback (offline data viewing). */
const CACHE = "agrigpt-v9"; // v9: stop caching page HTML entirely; purge v8
const SHELL = ["/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => undefined))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // chat/market POSTs always hit the network

  const url = new URL(req.url);
  // Never cache or serve the landing page from cache — marketing content must
  // always be fresh; a stale snapshot here caused hydration mismatches.
  if (url.pathname === "/") return;
  const isApi = url.pathname.startsWith("/api/") || url.port === "8000";
  const isNextStatic = url.pathname.startsWith("/_next/static");

  // Only cache-first assets whose filename carries a content hash (production).
  // `next dev` serves chunks from stable, un-hashed paths
  // (e.g. /_next/static/chunks/app/auth/login/page.js); caching those cache-first
  // pins the old compiled module forever, so the browser runs stale JS after a
  // rebuild while the dev server keeps returning 200. Those must never be cached.
  const isImmutable = /-[0-9a-f]{8,}\.(?:js|css|woff2?)$/i.test(url.pathname);

  if (url.pathname === "/manifest.json" || (isNextStatic && isImmutable)) {
    // Cache-first for immutable assets
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return res;
          })
      )
    );
    return;
  }

  if (isNextStatic) {
    // Un-hashed build output: always go to the network, never store it.
    event.respondWith(fetch(req));
    return;
  }

  // Network-first with cache fallback for API GETs only. Page navigations are
  // never intercepted: no cached HTML can ever be served, so a stale shell
  // cannot boot old chunks against a new build.
  if (isApi) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || Response.error()))
    );
    return;
  }

  // Everything else (page navigations, unknown GETs): plain network.
});

/* Push notifications (wired to backend web-push when VAPID keys are set) */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "AgriGPT", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "AgriGPT alert", {
      body: data.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: data.url || "/dashboard" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url || "/dashboard"));
});
