/* 이심전심 서비스 워커 — 인터넷이 끊겨도 스펠러가 열리게.
   페이지: 네트워크 먼저(배포하면 바로 새 버전), 실패하면 마지막으로 받은 것.
   사전(dict.txt?v=해시): 내용마다 주소가 다르므로 캐시 먼저, 새 해시를 받으면 옛 사전은 지운다.
   글꼴·아이콘: 캐시 먼저. 후보 조회(/predict 등)는 건드리지 않는다 — 오프라인이면 단어 후보만 쓴다. */
const CACHE = "esim-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;

  if (same && url.pathname === "/speller") {
    e.respondWith(fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put("/speller", copy)); }
      return res;
    }).catch(() => caches.match("/speller").then(r => r || Response.error())));
    return;
  }
  if (same && url.pathname === "/speller/dict.txt" && url.searchParams.get("v")) {
    e.respondWith(caches.open(CACHE).then(async c => {
      const hit = await c.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) {
        for (const k of await c.keys()) if (new URL(k.url).pathname === "/speller/dict.txt") await c.delete(k);
        await c.put(req, res.clone());
      }
      return res;
    }));
    return;
  }
  const asset = (same && /^\/speller\/(icon\.png|manifest\.webmanifest)$/.test(url.pathname))
    || url.hostname === "cdn.jsdelivr.net";
  if (asset) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
