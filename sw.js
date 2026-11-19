// Старая версия сайта работала офлайн. Этот файл удаляет её кэш и отключает себя,
// чтобы у всех открывалась новая версия сайта.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) await caches.delete(key);
    await self.registration.unregister();
    for (const client of await self.clients.matchAll({ type: "window" })) client.navigate(client.url);
  })());
});
