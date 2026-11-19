// Работа сайта без интернета.
// Страница и данные: сначала сеть, без сети — сохранённая копия.
// Иконки, шрифты и фото: сначала сохранённая копия.
const CACHE = "dawnline-v1";
const SHELL = ["./", "index.html", "data.json", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(cacheKey || request, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(cacheKey || request);
    if (hit) return hit;
    throw e;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok || res.type === "opaque") cache.put(request, res.clone());
  return res;
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname === "api.github.com") return; // публикация — только напрямую

  if (url.origin === location.origin) {
    if (req.mode === "navigate") { event.respondWith(networkFirst(req, "index.html")); return; }
    if (url.pathname.endsWith("/data.json")) { event.respondWith(networkFirst(req, "data.json")); return; }
    event.respondWith(cacheFirst(req));
    return;
  }

  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(cacheFirst(req));
  }
});
