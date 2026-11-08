/* 이심전심 서비스 워커 — 인터넷이 끊겨도 스펠러가 열리게.
   페이지: 네트워크가 1.5초 안에 오면 새 것, 아니면(서버가 자는 중) 저장본을 바로 연다.
   사전(dict.txt?v=해시): 내용마다 주소가 다르므로 캐시 먼저, 새 해시를 받으면 옛 사전은 지운다.
   글꼴(Pretendard·Noto Serif KR)·아이콘: 캐시 먼저. 후보 조회(/predict 등)는 건드리지 않는다 — 오프라인이면 단어 후보만 쓴다. */
const CACHE = "esim-v3";

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
    // Render 무료 서버는 자다가 깨는 데 20초~1분 걸린다. 저장본이 있으면 1.5초만 기다리고 바로 연다 —
    // 입력·단어 후보는 기기 안에서 돌기 때문에 서버가 깨는 동안에도 쓸 수 있다. 새 버전은 뒤에서 받아 다음에 연다.
    // Render의 'Application loading' 화면은 우리 페이지가 아니므로 저장도 표시도 하지 않는다.
    const net = fetch(req).then(async res => {
      if (!res.ok || !(await res.clone().text()).includes('id="keyboard"')) throw new Error("not ours");
      const copy = res.clone();
      await caches.open(CACHE).then(c => c.put("/speller", copy));
      return res;
    });
    e.waitUntil(net.catch(() => {}));
    e.respondWith((async () => {
      const hit = await caches.match("/speller");
      if (!hit) return net.catch(() => fetch(req));
      const quick = await Promise.race([net.catch(() => null), new Promise(r => setTimeout(() => r(null), 1500))]);
      return quick || hit;
    })());
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
    || ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"].includes(url.hostname);
  if (asset) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
