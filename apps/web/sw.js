// 서비스 워커: 화면 파일과 three.js는 캐시에서 먼저, API는 항상 서버에서 받는다.
const VERSION = "lgb-shell-v5";
const SHELL = [
  "./", "./index.html", "./style.css", "./app.js", "./manifest.webmanifest",
  "./js/core.js", "./js/viewer.js", "./js/room3d.js", "./js/plan.js", "./js/pages.js", "./js/remodel.js", "./js/install.js",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon.svg",
  "./vendor/three/three.module.min.js",
  "./vendor/three/addons/loaders/GLTFLoader.js",
  "./vendor/three/addons/controls/OrbitControls.js",
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
  e.waitUntil(caches.open(VERSION).then((c) => Promise.allSettled(SHELL.map((u) => c.add(u)))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.origin === location.origin && url.pathname.startsWith("/api/")) return; // 스캔·판정 데이터는 캐시하지 않음
  // 화면 파일: 네트워크 먼저 받아 캐시를 갱신하고, 끊기면 캐시로
  e.respondWith(
    fetch(e.request)
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
