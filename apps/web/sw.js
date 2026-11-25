// 서비스 워커: 화면 파일과 three.js는 캐시에서 먼저, API는 항상 서버에서 받는다.
const VERSION = "lgb-shell-v88"; // 직접 돌린 것은 벽에 붙을 때 다시 돌려놓지 않는다
const SHELL = [
  "./", "./index.html", "./config.js", "./style.css", "./studio.css", "./app.js", "./manifest.webmanifest",
  "./js/core.js", "./js/viewer.js", "./js/room3d.js", "./js/plan.js", "./js/pages.js", "./js/remodel.js", "./js/install.js", "./js/finishes.js", "./js/account.js", "./js/options.js", "./js/filters.js", "./js/guide.js", "./js/tour.js", "./js/combos.js", "./js/snap.js", "./js/gapnote.js",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon.svg",
  "./vendor/fonts/PretendardVariable.woff2", "./img/hero-kitchen.webp", "./img/hero-kitchen-m.webp",
  "./vendor/three/three.module.min.js",
  "./vendor/three/addons/loaders/GLTFLoader.js",
  "./vendor/three/addons/controls/OrbitControls.js",
  "./vendor/three/addons/controls/PointerLockControls.js", "./js/walk.js", "./js/walker.js", "./js/stops.js", "./js/furncolors.js", "./js/camkeys.js", "./js/wallsnap.js", "./js/symbols.js", "./js/rotring.js", "./js/surfmove.js", "./js/wallmount.js", "./js/slot.js", "./js/stretch.js",
  "./vendor/three/addons/utils/SkeletonUtils.js", "./models/devices/router.glb", "./models/people/walker.glb",
  "./vendor/three/addons/environments/RoomEnvironment.js",
  "./models/products/index.json", "./models/furniture/index.json",
  "./vendor/three/addons/utils/BufferGeometryUtils.js",
  // 후처리 (GTAO 접촉 그림자 + 톤 매핑)
  "./vendor/three/addons/postprocessing/EffectComposer.js",
  "./vendor/three/addons/postprocessing/Pass.js",
  "./vendor/three/addons/postprocessing/RenderPass.js",
  "./vendor/three/addons/postprocessing/ShaderPass.js",
  "./vendor/three/addons/postprocessing/MaskPass.js",
  "./vendor/three/addons/postprocessing/OutputPass.js",
  "./vendor/three/addons/postprocessing/GTAOPass.js",
  "./vendor/three/addons/shaders/CopyShader.js",
  "./vendor/three/addons/shaders/OutputShader.js",
  "./vendor/three/addons/shaders/GTAOShader.js",
  "./vendor/three/addons/shaders/PoissonDenoiseShader.js",
  "./vendor/three/addons/math/SimplexNoise.js",
];

self.addEventListener("install", (e) => {
  // 브라우저 HTTP 캐시에 남은 옛 파일을 넣지 않게 서버에서 새로 받는다
  // 제품 사진·모델은 1,000개가 넘어서 미리 받지 않고, 한 번 본 것만 아래 fetch에서 캐시해 둔다
  e.waitUntil(caches.open(VERSION)
    .then((c) => Promise.allSettled(SHELL.map((u) => c.add(new Request(u, { cache: "reload" })))))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) return; // 스캔·판정 데이터는 캐시하지 않음 (API가 다른 주소에 있어도)
  // 화면 파일: 네트워크 먼저 받아 캐시를 갱신하고, 끊기면 캐시로
  // 같은 서버 파일은 매번 서버에 바뀌었는지 묻는다(no-cache): 앱을 고친 뒤 옛 CSS·JS가 남지 않게
  // 제품 사진(img/products/<sku>.webp)·모델(models/products/<sku>.glb): 캐시에 있으면 바로 (오프라인 시연)
  if (url.origin === location.origin && /\/(img|models)\/products\/[^/]+\.(webp|glb)$/.test(url.pathname)) {
    e.respondWith(caches.open(VERSION).then((c) => c.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok) c.put(e.request, res.clone());
      return res;
    }))));
    return;
  }
  const same = url.origin === location.origin && e.request.mode !== "navigate";
  e.respondWith(
    fetch(same ? new Request(e.request, { cache: "no-cache" }) : e.request)
      .then((res) => {
        if (res.ok && (url.origin === location.origin || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com"))) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || caches.match("./index.html"))),
  );
});
