// ponytail: shell cache-first, data network-first with a cached fallback, so the
// home-screen icon opens to the last known state instead of a dinosaur.
const SHELL = "poopy-v2";
const FILES = ["./", "index.html", "manifest.json", "favicon.png", "favicon-64.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== SHELL).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const fresh = fetch(e.request)
    .then(r => { caches.open(SHELL).then(c => c.put(e.request, r.clone())); return r; });
  e.respondWith(
    e.request.url.includes("data.json")
      ? fresh.catch(() => caches.match(e.request))
      : caches.match(e.request).then(hit => hit || fresh));
});
