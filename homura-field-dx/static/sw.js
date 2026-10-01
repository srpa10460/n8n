// Service worker: app shell + Python core + Pyodide are cached at install (needs ONE online visit).
// /api/* is never cached (sync always goes to the network and fails visibly when offline).
const CACHE = "hoa-field-shell-v1";
self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const list = await (await fetch("/precache.json", { cache: "no-store" })).json();
    const c = await caches.open(CACHE);
    await c.addAll(list.files);          // any failure => install fails => app is NOT reported offline-ready
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE && k.startsWith("hoa-field-shell-")) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin || u.pathname.startsWith("/api/") || e.request.method !== "GET") return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(e.request, { ignoreSearch: true });
    if (hit) return hit;
    try { return await fetch(e.request); }
    catch (err) { if (e.request.mode === "navigate") { const i = await c.match("/"); if (i) return i; } throw err; }
  })());
});
