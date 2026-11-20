// 3D 뷰어 (three.js, glb) + 3D 안에서 바로 배치하기
// 평면 좌표 (x, y) = 3D (x, z), Y-up. 제품 yaw = 정면 방향, 상자 회전 = -(yaw - 90°) (glb.py와 같은 규칙)
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";
import { EYE_H, RUN, WALK, isBlocked, moveVector, spawnPoint, step } from "./walk.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { clone as cloneSkinned } from "three/addons/utils/SkeletonUtils.js";
import { toast } from "./core.js";
import { WALK_SPEED, pathLength, poseAt, routeClock, smoothPath } from "./walker.js";
import { dressRoom, furnish, shadowShell, furnitureTemplate, fitFurniture } from "./room3d.js";

const VERDICT_HEX = { fit: 0x1e7a4f, conditional: 0x1e7a4f, no_fit: 0xb3261e, unknown: 0x5b6370 };
const SELECT_HEX = 0xa50034;
const CLICK_PX = 6; // 이 이하로 움직이면 클릭으로 본다
const SURFACE_MAX_M = 2.2; // 공유기를 올릴 수 있는 가장 높은 윗면 (선반 꼭대기까지). 서버 Service.SURFACE_MAX_M과 같게
const NOT_SURFACE = new Set(["decor:wall", "decor:partition", "decor:rug", "decor:plant", "decor:lamp"]); // 서버 NOT_SURFACE와 같게
const skuOf = (o) => { while (o && !o.userData?.sku) o = o.parent; return o?.userData?.sku; };
const GHOST_NEAR_M = 0.8; // 미리 보기 상자가 카메라와 이만큼 가까우면 그리지 않는다
// 바닥 텍스처용 SVG에는 페이지 CSS가 안 먹으므로 오버레이 스타일을 같이 넣는다 (style.css의 .plan 오버레이와 같은 색)
const OVERLAY_CSS = `.sunpatch{fill:#ffd54a;fill-opacity:.55;stroke:#e0a800}.route{fill:none;stroke:#4b45b0;stroke-linecap:round;stroke-linejoin:round;stroke-opacity:.9}
.narrow{fill:none;stroke:#b3261e;stroke-opacity:.9}.tag rect{fill:#1c2024;fill-opacity:.82}.tag text{fill:#fff;font-weight:600}.router-sym rect{fill:#1c2024}.router-sym path{stroke:#1c2024}text{font-family:Pretendard,sans-serif}`;

// 공유기·사람 모델 (Blender: build_router.py, build_person.py). 한 번만 받는다
const assets = new Map();
const loadAsset = (url) => {
  if (!assets.has(url)) assets.set(url, new GLTFLoader().loadAsync(url).catch(() => null));
  return assets.get(url);
};
const ROUTER_URL = "models/devices/router.glb", PERSON_URL = "models/people/walker.glb";
const WALK_EASE_S = 0.6, LOOK_AHEAD_M = 0.35, TURN_S = 0.3; // 출발·정지 가감속, 몸이 보는 앞쪽, 도는 시간
const STRIDE_M = 1.3 * 32 / 30; // build_person.py: walk 한 주기(32프레임, 30 fps)에 1.3 m/s로 가는 거리
const MAX_WALKERS = 4;

// 제품 모델: 한 번 받아 두고 배치마다 복제한다 (화면을 바꿔도 다시 받지 않는다)
const MODEL_DIR = "models/products/";
const templates = new Map();
const pending = new Map();
let modelIndex = null;
let companionIndex = null;
const gltf = new GLTFLoader();
function loadModel(sku) {
  if (templates.has(sku)) return Promise.resolve(true);
  if (pending.has(sku)) return pending.get(sku);
  if (sku.startsWith("decor:")) {
    // 공간 꾸미기 가구: 기준 크기 모델을 배치 크기에 맞춰 부품별로 늘린다 (room3d.fitFurniture)
    const job = furnitureTemplate(sku.slice(6)).then((t) => {
      if (!t) return false;
      templates.set(sku, { decor: true, scene: t.scene, ref: t.ref });
      return true;
    });
    pending.set(sku, job);
    return job;
  }
  modelIndex ??= fetch(MODEL_DIR + "index.json").then((r) => (r.ok ? r.json() : { models: {} })).catch(() => ({ models: {} }));
  // 본체와 떨어져 같이 놓이는 부품 (정수기 파우셋 등). offset_m = 본체 바닥 가운데 기준 [x, 위, 앞]
  companionIndex ??= fetch(MODEL_DIR + "companions.json").then((r) => (r.ok ? r.json() : { models: {} })).catch(() => ({ models: {} }));
  const job = Promise.all([modelIndex, companionIndex]).then(([idx, comps]) => {
    const entry = idx.models?.[sku];
    if (!entry) return false; // 모델이 없으면 치수 상자로 둔다
    const comp = comps.models?.[sku];
    return Promise.all([
      gltf.loadAsync(MODEL_DIR + entry.file),
      comp ? gltf.loadAsync(MODEL_DIR + comp.file).catch(() => null) : null,
    ]).then(([g, c]) => {
      if (c) {
        c.scene.position.fromArray(comp.offset_m);
        c.scene.userData.companion = true;
        g.scene.add(c.scene);
      }
      templates.set(sku, g.scene);
      return true;
    }, () => false);
  });
  pending.set(sku, job);
  return job;
}

export function makeViewer(el, handlers = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; // OutputPass가 마지막에 한 번 적용
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#ffe6c4"); // 톤 매핑을 거치면 따뜻한 회색(#e1d8ca 정도)으로 보인다
  // 실내 반사(유리·메탈 앞판이 살아 보이게) + 부드러운 하늘빛 + 그림자 내는 해
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  scene.environment = envTex;
  const hemi = new THREE.HemisphereLight(0xf4f6ff, 0x9c9184, 0.45);
  scene.add(hemi);
  // 기본 해는 중립 흰빛. 채광을 켜면 setSun()으로 실제 해(날짜·시각·위치·북쪽) 방향·색·세기로 바뀐다
  const STUDIO = { color: 0xfffbf6, intensity: 2.2, hemi: 0.45 };
  const sun = new THREE.DirectionalLight(STUDIO.color, STUDIO.intensity);
  sun.position.set(-4, 8, 6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.bias = -0.0003;
  sun.shadow.normalBias = 0.015;
  scene.add(sun, sun.target);
  const cam = new THREE.PerspectiveCamera(45, 1, 0.05, 200);

  // 후처리: 장면(MSAA) → GTAO(가구 다리·벽 모서리 접촉 그림자) → 톤 매핑·sRGB
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(scene, cam));
  const gtao = new GTAOPass(scene, cam, 1, 1);
  // 반경을 크게 잡으면 샘플이 모자라 바닥·벽에 점 노이즈가 생긴다. 반경은 접촉 그림자 정도(0.35 m)로 좁히고
  // 샘플·디노이즈를 넉넉히 줘서 매끈하게 만든다
  gtao.blendIntensity = 0.85;
  gtao.updateGtaoMaterial({ radius: 0.35, distanceExponent: 1.0, thickness: 1.0, distanceFallOff: 1.0, scale: 1.2, samples: 16 });
  gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 10, rings: 3, samples: 16 });
  // 고르기용 투명 상자, 반투명(컷어웨이 벽·유리·미리 보기), 바닥 오버레이는 AO에서 뺀다
  const baseHide = gtao.overrideVisibility.bind(gtao);
  gtao.overrideVisibility = () => {
    baseHide();
    scene.traverse((o) => {
      if (!o.isMesh || !o.visible) return;
      const m = o.material;
      if (!m || m.visible === false || m.colorWrite === false || (m.transparent && (m.opacity < 0.6 || m.depthWrite === false))) o.visible = false;
    });
  };
  composer.addPass(gtao);
  composer.addPass(new OutputPass());
  const ctl = new OrbitControls(cam, renderer.domElement);
  ctl.enableDamping = true;
  ctl.maxPolarAngle = Math.PI * 0.49; // 바닥 아래로는 못 내려가게
  ctl.minDistance = 1.2;                // 가구 속으로 파고들지 않게
  // 휠을 누른 채 끌면 화면 중심을 옮긴다 (CAD·Blender처럼). 확대는 휠 굴리기, 오른쪽 끌기도 이동
  ctl.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN };
  ctl.screenSpacePanning = false; // 바닥과 나란히 움직여 시점이 바닥 아래로 빠지지 않게
  let grid = null, held = null; // 집어 든 물건 (건축 모드)
  let objectCats = {};           // 스캔 가구 id → 종류 (room.json)
  let model = null, framed = false, keepCam = false, alive = true, walls = [], center = new THREE.Vector3();
  const tmp = new THREE.Vector3(), toCam = new THREE.Vector3();

  // 화면에서 그리는 층: 바닥 오버레이 → 놓은 제품 → 미리 보기
  const overlay = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
  overlay.rotation.x = -Math.PI / 2;
  overlay.position.y = 0.004;
  overlay.visible = false;
  overlay.renderOrder = 1;
  scene.add(overlay);
  const products = new THREE.Group();
  scene.add(products);
  const ghost = new THREE.Group();
  scene.add(ghost);
  const need = new THREE.Group(); // 고른 제품이 차지하는 공간 표시
  scene.add(need);
  // 와이파이: 실제 크기 공유기 (집어 들어 옮기고 돌릴 수 있다)
  const routerG = new THREE.Group();
  routerG.visible = false;
  routerG.userData.router = true;
  scene.add(routerG);
  let routerPose = null;
  // 동선: 경로를 따라 걷는 사람
  const walkersG = new THREE.Group();
  scene.add(walkersG);
  let walkers = [], walkersKey = "", walkersPaused = false;

  // 카메라 쪽 벽은 반투명으로 (돌하우스 컷어웨이)
  const cutaway = () => {
    toCam.copy(cam.position).sub(center).setY(0).normalize();
    for (const w of walls) {
      w.getWorldPosition(tmp);
      const front = tmp.sub(center).setY(0).normalize().dot(toCam) > 0.35;
      const base = w.userData.baseOpacity ?? 1;
      w.material.opacity = front ? 0.12 * base : base;
      w.material.transparent = front || base < 1;
      w.material.depthWrite = !front && base === 1;
    }
  };
  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    const pr = Math.min(devicePixelRatio, 1.5);
    if (renderer.getPixelRatio() !== pr) { renderer.setPixelRatio(pr); composer.setPixelRatio(pr); }
    renderer.setSize(w, h);
    composer.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(el);
  resize();
  // ---------- 1인칭 둘러보기 ----------
  // 눈높이 1.6 m에서 WASD로 걷고, 화면을 누르면 마우스로 둘러본다(Esc로 풀림). 벽·가구·제품은 못 지나간다.
  const plc = new PointerLockControls(cam, renderer.domElement);
  plc.pointerSpeed = 0.8;
  let camGlide = null; // 새로 놓은 제품 쪽으로 시점을 부드럽게 옮길 때
  let walk = null, lastT = performance.now(), stepSunFn = null; // 해 보간 함수는 아래 '해'에서 채운다
  const euler = new THREE.Euler(0, 0, 0, "YXZ");
  const KEYS = { KeyW: "f", ArrowUp: "f", KeyS: "b", ArrowDown: "b", KeyA: "l", ArrowLeft: "l", KeyD: "r", ArrowRight: "r" };
  const onWalkKey = (e) => {
    if (!walk || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    const k = KEYS[e.code];
    if (e.key === "Shift") walk.keys.run = e.type === "keydown";
    if (!k) return;
    walk.keys[k] = e.type === "keydown";
    walkHud.hidden = true; // 걷기 시작하면 안내는 접는다
    e.preventDefault();
    e.stopImmediatePropagation(); // 건축 모드 키(WASD 카메라·R 돌리기)와 겹치지 않게
  };
  document.addEventListener("keydown", onWalkKey, true);
  document.addEventListener("keyup", onWalkKey, true);
  const walkHud = document.createElement("div");
  walkHud.className = "walk-hud";
  walkHud.hidden = true;
  Object.assign(walkHud.style, { position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)",
    background: "rgba(20,22,26,.72)", color: "#fff", padding: "10px 14px", borderRadius: "10px", font: "13px/1.5 sans-serif",
    pointerEvents: "none", textAlign: "center", zIndex: 3 });
  walkHud.innerHTML = "화면을 누르면 마우스로 둘러봐요<br><b>W A S D</b> 걷기 · <b>Shift</b> 빠르게 · <b>Esc</b> 마우스 풀기";
  const cross = document.createElement("div");
  cross.hidden = true;
  Object.assign(cross.style, { position: "absolute", left: "50%", top: "50%", width: "6px", height: "6px", margin: "-3px 0 0 -3px",
    borderRadius: "50%", background: "rgba(255,255,255,.85)", boxShadow: "0 0 0 1px rgba(0,0,0,.35)", pointerEvents: "none", zIndex: 3 });
  if (getComputedStyle(el).position === "static") el.style.position = "relative";
  el.append(walkHud, cross);
  plc.addEventListener("lock", () => { walkHud.hidden = true; cross.hidden = false; });
  plc.addEventListener("unlock", () => { if (walk) { walkHud.hidden = false; cross.hidden = true; } walk && (walk.keys = {}); });
  const walkTick = (dt) => {
    euler.setFromQuaternion(cam.quaternion);
    const d = moveVector(euler.y, walk.keys, walk.keys.run ? RUN : WALK, dt);
    if (d[0] || d[1]) {
      const p = step([cam.position.x, cam.position.z], d, walk.world);
      cam.position.set(p[0], EYE_H, p[1]);
    }
  };
  const ceilingMesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshStandardMaterial({ color: 0xf6f6f3, roughness: 0.95 }));
  ceilingMesh.rotation.x = Math.PI / 2; // 아래를 본다
  ceilingMesh.receiveShadow = true;
  ceilingMesh.visible = false;
  scene.add(ceilingMesh);
  const solidWalls = () => {
    for (const w of walls) {
      const base = w.userData.baseOpacity ?? 1;
      w.material.opacity = base;
      w.material.transparent = base < 1;
      w.material.depthWrite = base === 1;
    }
  };

  (function loop() {
    if (!alive) return;
    // 느린 PC에서도 걷는 빠르기가 같게 (한 번에 길게 가도 walk.step이 잘게 나눠 벽을 안 뚫는다)
    const now = performance.now(), dt = Math.min(0.25, (now - lastT) / 1000);
    lastT = now;
    if (walk) walkTick(dt);
    else {
      if (camGlide) {
        const k = Math.min(1, dt * 4);
        ctl.target.lerp(camGlide.target, k); cam.position.lerp(camGlide.pos, k);
        if (ctl.target.distanceTo(camGlide.target) < 0.01) camGlide = null;
      }
      ctl.update();
      cutaway();
    }
    // 브라우저 확대·축소나 모니터 이동으로 화면 배율만 바뀌면 크기 변화가 안 잡혀 일부만 그려진다 → 매 프레임 배율을 확인
    if (renderer.getPixelRatio() !== Math.min(devicePixelRatio, 1.5)) resize();
    animateHeld();
    stepWalkers(dt);
    stepSunFn?.(dt);
    composer.render();
    requestAnimationFrame(loop);
  })();
  // ---------- 해 ----------
  // realSun: null이면 보기 좋은 기본 해(카메라 왼쪽 위). 있으면 {direction:[x,y,z](해 쪽), color, intensity(0~1), up}
  let realSun = null, shell = null, roomR = 8;
  const roomC = new THREE.Vector3();
  // 해는 목표(goal)로 바로 바뀌지 않고 매 프레임 조금씩 다가간다(약 0.2초 시정수).
  // 시간 슬라이더를 움직이거나 하루를 재생해도 방향·색·세기·하늘빛이 끊김 없이 이어진다.
  const DEFAULT_DIR = new THREE.Vector3(-0.6, 1.6, 0.8).normalize();
  const goal = { dir: DEFAULT_DIR.clone(), color: new THREE.Color(STUDIO.color), sun: STUDIO.intensity, hemi: STUDIO.hemi, env: 1 };
  const cur = { dir: DEFAULT_DIR.clone(), color: new THREE.Color(STUDIO.color), sun: STUDIO.intensity, hemi: STUDIO.hemi, env: 1 };
  // 주변광(환경 반사) 세기. 실제 해일 때는 낮춘다: 가구·제품이 어디서나 똑같이 밝으면 볕이 닿은 면과 그늘이 구분되지 않는다.
  // 재질마다 처음 값(baseEnv)을 기억해 두고 곱한다. 새로 들어온 물체도 다음 프레임에 맞춰진다.
  let envApplied = -1, envCount = -1;
  const applyEnv = (k) => {
    let n = 0;
    scene.traverse((o) => {
      const m = o.isMesh && o.material;
      if (!m || m.envMapIntensity === undefined) return;
      n++;
      if (m.userData.baseEnv === undefined) m.userData.baseEnv = m.envMapIntensity;
      m.envMapIntensity = m.userData.baseEnv * k;
    });
    envApplied = k; envCount = n;
  };
  let envTick = 0;
  let snapSun = true;
  const placeSun = () => {
    sun.position.copy(roomC).addScaledVector(cur.dir, roomR * 2);
    sun.target.position.copy(roomC);
    sun.target.updateMatrixWorld();
  };
  const stepSun = (dt) => {
    const k = snapSun ? 1 : 1 - Math.exp(-dt / 0.2);
    snapSun = false;
    cur.dir.lerp(goal.dir, k).normalize();
    cur.color.lerp(goal.color, k); // 선형 색 공간에서 섞는다
    cur.sun += (goal.sun - cur.sun) * k;
    cur.hemi += (goal.hemi - cur.hemi) * k;
    sun.color.copy(cur.color);
    sun.intensity = cur.sun;
    hemi.intensity = cur.hemi;
    sun.castShadow = cur.sun > 0.01;
    placeSun();
    cur.env += (goal.env - cur.env) * k;
    // 값이 바뀌었거나, 가끔(0.5초마다) 새로 들어온 물체가 있는지 보고 다시 맞춘다
    envTick += dt;
    if (Math.abs(cur.env - envApplied) > 0.01 || envTick > 0.5) { envTick = 0; applyEnv(cur.env); }
  };
  stepSunFn = stepSun;
  const applySun = (instant = false) => {
    if (shell) shell.visible = !!realSun; // 벽·천장 그림자: 실제 해일 때만 (창으로만 볕이 든다)
    if (!realSun) {
      goal.dir.copy(DEFAULT_DIR);
      goal.color.set(STUDIO.color);
      goal.sun = STUDIO.intensity;
      goal.hemi = STUDIO.hemi;
      goal.env = 1;
    } else {
      goal.dir.set(...realSun.direction).normalize();
      goal.color.set(realSun.color);
      // 직사광은 실내 간접광보다 몇 배 밝다: 창으로 든 볕이 바닥에 또렷하게
      goal.sun = realSun.up ? 6.0 * realSun.intensity : 0;
      // 하늘빛: 해가 진 뒤에도 박명(sky)만큼 남았다가 서서히 어두워진다
      const sky = realSun.sky ?? (realSun.up ? 1 : 0);
      goal.hemi = 0.1 + 0.22 * sky + 0.24 * Math.min(1, realSun.intensity * 1.4);
      goal.env = 0.08 + 0.3 * sky;
    }
    if (instant) snapSun = true;
  };

  // 방 전체가 보이게 카메라를 잡는다 (화면 비율이 세로로 길면 더 멀리)
  // keep = true면 카메라는 그대로 두고 그림자 범위·격자만 방에 맞춘다 (저장해 둔 시점으로 돌아왔을 때)
  // 저장해 둔 시점이 쓸 만한지: 바닥에 붙었거나, 너무 가깝거나, 방 밖을 보고 있으면 방 전체 보기로 시작한다
  const sensibleCam = (box) => {
    const near = box.clone().expandByScalar(1);
    return cam.position.y >= 1.4 && cam.position.distanceTo(ctl.target) >= 2 && near.containsPoint(ctl.target);
  };
  const frame = (keep = false) => {
    if (!model) return;
    const box = new THREE.Box3().setFromObject(model);
    const c = box.getCenter(new THREE.Vector3());
    const s = box.getSize(new THREE.Vector3()).length() * Math.max(1, 1.2 / cam.aspect);
    if (!keep || !sensibleCam(box)) {
      cam.position.set(c.x - s * 0.35, c.y + s * 1.05, c.z + s * 0.55);
      ctl.target.copy(c);
    }
    // 그림자 범위를 방에 맞춘다
    const r = box.getSize(new THREE.Vector3()).length() / 2;
    roomC.copy(c);
    roomR = r;
    placeSun();
    Object.assign(sun.shadow.camera, { left: -r, right: r, top: r, bottom: -r, near: 0.1, far: r * 4 });
    sun.shadow.camera.updateProjectionMatrix();
    // 집어 들었을 때만 보이는 바닥 격자 (0.5 m 칸)
    const size = box.getSize(new THREE.Vector3());
    const n = Math.ceil(Math.max(size.x, size.z) / 0.5) + 2;
    if (grid) scene.remove(grid);
    grid = new THREE.GridHelper(n * 0.5, n, 0x1c2024, 0x1c2024);
    grid.material.transparent = true;
    grid.material.opacity = 0.14;
    grid.material.depthWrite = false;
    grid.position.set(Math.round(c.x * 2) / 2, 0.003, Math.round(c.z * 2) / 2);
    grid.visible = !!held;
    scene.add(grid);
  };

  // ---------- 집어 들기 (건축 모드) ----------
  // 고른 제품·스캔 가구를 살짝 띄워 커서를 따라오게 하고, 다시 누르면 내려놓는다.
  const LIFT = 0.12;
  const heldNodes = (item) => {
    if (item.kind === "placement") return products.children.filter((c) => c.userData.placementId === item.id);
    if (item.kind === "router") return routerG.visible && routerG.children.length ? [routerG] : [];
    const out = [];
    model?.traverse((o) => {
      if (o.userData.objectId === item.id) out.push(o);                                    // Blender 가구 모델
      else if (o.isMesh && o.userData.kind === "object" && o.name === item.id && !o.userData.shared) out.push(o); // 고르기용 상자
    });
    return out;
  };
  // 평면 yaw → 3D 회전: 제품은 -(yaw - 90°), 스캔 가구는 -yaw (glb.py와 같은 규칙)
  const rotY = (kind, yaw) => (kind === "placement" ? -(yaw - Math.PI / 2) : -yaw);
  // 공유기를 들고 다니면 아래 가구(책상·선반) 윗면에 올라간다. 놓으면 서버가 같은 규칙으로 높이를 저장한다
  const downRay = new THREE.Raycaster(), DOWN = new THREE.Vector3(0, -1, 0), rayFrom = new THREE.Vector3();
  const surfaceY = (xz) => {
    rayFrom.set(xz[0], SURFACE_MAX_M + 0.1, xz[1]);
    downRay.set(rayFrom, DOWN);
    const hit = downRay.intersectObjects(products.children, true).find((h) => h.object.isMesh && h.point.y <= SURFACE_MAX_M && !NOT_SURFACE.has(skuOf(h.object)));
    return hit ? hit.point.y : 0;
  };
  const placeHeld = () => {
    if (!held) return;
    const top = held.kind === "router" ? surfaceY(held.xz) : null;
    for (const { node, baseY } of held.nodes) {
      node.position.set(held.xz[0], (top ?? baseY) + held.lift, held.xz[1]);
      node.rotation.set(0, rotY(held.kind, held.yaw), 0);
    }
  };
  function animateHeld() {
    need.visible = !held; // 들고 옮기는 동안에는 옛 자리 표시를 숨긴다
    if (!held) return;
    const target = held.dropping ? 0 : LIFT;
    held.lift += (target - held.lift) * 0.3;
    placeHeld();
  }


  const productBox = (p, { selected = false, preview = false } = {}) => {
    const [w, h, d] = p.size_m;
    const g = new THREE.Group();
    const vhex = selected ? SELECT_HEX : VERDICT_HEX[p.verdict] ?? VERDICT_HEX.unknown;
    const tmpl = p.sku && templates.get(p.sku);
    if (tmpl) {
      // Blender로 만든 제품 모델 (models/products/<sku>.glb, 바닥 가운데 원점, 정면 +Z). 꾸미기 가구는 크기에 맞춰 늘린다
      const m = tmpl.decor ? fitFurniture(tmpl.scene, tmpl.ref, new THREE.Vector3(w, h, d)) : tmpl.clone(true);
      m.traverse((o) => {
        if (!o.isMesh) return;
        o.userData.shared = true;
        o.castShadow = !preview;
        o.receiveShadow = true;
        o.userData.placementId = p.placement_id;
        if (tmpl.decor) o.material = o.material.clone(), o.userData.ownMaterial = true;
        const isFinish = o.material.name === "finish";
        if (preview || (isFinish && p.hex)) {
          o.material = o.material.clone();
          o.userData.ownMaterial = true;
          if (isFinish && p.hex) o.material.color.set(p.hex);
          if (preview) Object.assign(o.material, { transparent: true, opacity: 0.5, depthWrite: false });
        }
      });
      g.add(m);
    } else {
      if (p.sku) requestModel(p.sku);
      const body = new THREE.Mesh(
        new THREE.BoxGeometry(w, h, d),
        new THREE.MeshStandardMaterial({ color: new THREE.Color(p.hex || "#f2f2f0"), roughness: 0.55, metalness: 0.05,
          transparent: preview, opacity: preview ? 0.55 : 1 }),
      );
      body.position.y = h / 2;
      body.castShadow = !preview;
      body.userData = { placementId: p.placement_id };
      // 정면 표시: 앞쪽 아래 굵은 띠
      const front = new THREE.Mesh(new THREE.BoxGeometry(w * 0.9, 0.025, 0.012), new THREE.MeshBasicMaterial({ color: 0x1c2024 }));
      front.position.set(0, 0.05, d / 2 + 0.007);
      g.add(body, front);
    }
    // 판정 색 테두리: 상자 모양일 때와 고른 제품·미리 보기일 때만 (모델 위에 늘 그리면 지저분하다)
    if (!tmpl || selected || preview) {
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w + 0.01, h + 0.01, d + 0.01)),
        new THREE.LineBasicMaterial({ color: vhex }));
      edges.position.y = h / 2;
      g.add(edges);
    }
    // 바닥 판: 판정 색 (꾸미기 가구는 고른 때·안 들어갈 때만, 평소엔 깔끔하게)
    const decor = p.sku?.startsWith("decor:");
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(w + 0.08, d + 0.08),
      new THREE.MeshBasicMaterial({ color: vhex, transparent: true, opacity: selected ? 0.55 : 0.35, depthWrite: false }));
    plate.rotation.x = -Math.PI / 2;
    plate.position.y = 0.006;
    plate.userData.verdictPlate = true;
    if (!decor || selected || preview || p.verdict === "no_fit") g.add(plate);
    // 치수선은 그리지 않는다: 놓을 때는 판정 색 테두리만 (치수는 제품 상세에서)
    g.position.set(p.center_xz[0], 0, p.center_xz[1]);
    g.rotation.y = -((p.yaw_rad ?? Math.PI / 2) - Math.PI / 2);
    g.userData = { placementId: p.placement_id, sku: p.sku };
    return g;
  };
  const clear = (grp) => {
    for (const c of [...grp.children]) {
      grp.remove(c);
      c.traverse((o) => {
        if (o.userData.ownTexture) o.material.map?.dispose();
        if (!o.userData.shared) o.geometry?.dispose();
        if (!o.userData.shared || o.userData.ownMaterial) o.material?.dispose?.();
      });
    }
  };
  // 모델이 늦게 도착하면 마지막 상태로 다시 그린다
  let last = { list: [], selectedId: null, ghost: null };
  const requestModel = (sku) => loadModel(sku).then((ok) => {
    if (!ok || !alive || dragging) return;
    api.setPlacements(last.list, last.selectedId);
    api.setGhost(last.ghost);
  });

  // ---------- 포인터 ----------
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const setNdc = (e) => {
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, cam);
  };
  const floorPoint = (e, step = 0.05) => {
    setNdc(e);
    const hit = ray.ray.intersectPlane(floor, new THREE.Vector3());
    if (!hit) return null;
    const snap = (v) => Math.round(v / step) * step;
    return [snap(hit.x), snap(hit.z)];
  };
  // 가구 윗면(책상·선반)을 가리키면 그 윗면 자리. 공유기처럼 위에 올려놓는 물건을 놓을 때만 쓴다
  const surfacePoint = (e) => {
    setNdc(e);
    const hit = ray.intersectObjects(products.children, true).find((h) => h.object.isMesh && h.face && h.point.y <= SURFACE_MAX_M && !NOT_SURFACE.has(skuOf(h.object))
      && tmp.copy(h.face.normal).transformDirection(h.object.matrixWorld).y > 0.7);
    return hit ? [hit.point.x, hit.point.z] : floorPoint(e);
  };
  const pointFor = (e) => (handlers.onSurface?.() ? surfacePoint(e) : floorPoint(e));
  const pick = (e) => {
    setNdc(e);
    const targets = [...products.children];
    if (routerG.visible) targets.push(routerG);
    if (model) model.traverse((o) => { if (o.isMesh && o.userData?.kind === "object" && o.visible) targets.push(o); });
    if (wallPick && model) {
      // 벽 철거 고르기: 벽만 맞힌다
      const walls = [];
      model.traverse((o) => { if (o.isMesh && o.userData?.kind === "wall" && o.visible) walls.push(o); });
      const wh = ray.intersectObjects(walls, false)[0];
      return wh ? { type: "wall", id: wh.object.name } : null;
    }
    const hit = ray.intersectObjects(targets, true).find((h) => h.object.visible);
    if (!hit) return null;
    let o = hit.object;
    while (o && !o.userData?.placementId && o.userData?.kind !== "object" && !o.userData?.router) o = o.parent;
    if (!o) return null;
    if (o.userData.router) return { type: "router", id: "router" };
    if (o.userData.placementId) return { type: "placement", id: o.userData.placementId };
    return { type: "object", id: o.name };
  };
  let down = null, dragging = null;
  let wallPick = false; // 벽 철거: 벽을 눌러 고르는 중
  let look = null; // 둘러보기에서 마우스를 못 잠글 때(터치 등) 끌어서 둘러보기
  const onDown = (e) => {
    if (walk) {
      e.stopPropagation(); // 둘러보기에서는 고르기·집어 들기·배치 없음
      walkHud.hidden = true;
      if (e.pointerType === "mouse" && !plc.isLocked) plc.lock();
      else if (!plc.isLocked) look = { x: e.clientX, y: e.clientY };
      return;
    }
    if (e.button !== undefined && e.button !== 0) return;
    if (held) { down = { x: e.clientX, y: e.clientY, hit: null, p: null, held: true }; return; }
    const hit = pick(e);
    down = { x: e.clientX, y: e.clientY, hit, p: floorPoint(e) };
    if (hit?.type === "placement" && handlers.canDrag?.()) {
      // 제품 위에서 누르면 카메라 회전을 멈추고 끌기
      ctl.enabled = false;
      const g = products.children.find((c) => c.userData.placementId === hit.id);
      if (g) g.userData.dirty = true;
      dragging = { id: hit.id, start: down.p, orig: g ? [g.position.x, g.position.z] : down.p, group: g, moved: false };
      renderer.domElement.setPointerCapture?.(e.pointerId);
    }
  };
  const onMove = (e) => {
    if (walk) {
      if (look) {
        euler.setFromQuaternion(cam.quaternion);
        euler.y -= (e.clientX - look.x) * 0.005;
        euler.x = Math.max(-1.4, Math.min(1.4, euler.x - (e.clientY - look.y) * 0.005));
        cam.quaternion.setFromEuler(euler);
        look = { x: e.clientX, y: e.clientY };
      }
      return;
    }
    if (held && !held.dropping) {
      // 들고 있으면 커서를 따라온다: 10 cm 격자, Alt는 1 cm
      const q = floorPoint(e, e.altKey ? 0.01 : 0.1);
      if (q) { held.xz = [q[0] + held.grab[0], q[1] + held.grab[1]]; handlers.onHoldMove?.(held, held.xz); }
      return;
    }
    const p = floorPoint(e);
    if (!p) return;
    if (dragging && dragging.start) {
      const c = [dragging.orig[0] + p[0] - dragging.start[0], dragging.orig[1] + p[1] - dragging.start[1]];
      if (!dragging.moved && Math.hypot(e.clientX - down.x, e.clientY - down.y) > CLICK_PX) dragging.moved = true;
      if (dragging.moved) {
        dragging.group?.position.set(c[0], 0, c[1]);
        handlers.onDragMove?.(dragging.id, c);
      }
      return;
    }
    handlers.onHover?.(handlers.onSurface?.() ? surfacePoint(e) || p : p);
  };
  const onUp = (e) => {
    if (walk) { look = null; return; }
    const d = down;
    down = null;
    ctl.enabled = true;
    if (dragging) {
      const g = dragging;
      dragging = null;
      if (g.moved) { handlers.onDragEnd?.(g.id, [g.group?.position.x ?? 0, g.group?.position.z ?? 0]); return; }
    }
    if (!d || Math.hypot(e.clientX - d.x, e.clientY - d.y) > CLICK_PX) return; // 카메라를 돌린 것
    if (d.held) { handlers.onHoldClick?.(held); return; }
    handlers.onClick?.({ hit: d.hit, point: pointFor(e), event: e });
  };
  const dom = renderer.domElement;
  dom.style.touchAction = "none";
  el.addEventListener("pointerdown", onDown, { capture: true }); // OrbitControls보다 먼저
  dom.addEventListener("pointermove", onMove);
  dom.addEventListener("pointerup", onUp);
  dom.addEventListener("pointerleave", () => handlers.onLeave?.());
  dom.addEventListener("mousedown", (e) => { if (e.button === 1) e.preventDefault(); }); // 휠 누름: 브라우저 자동 스크롤 대신 화면 이동
  dom.addEventListener("dragover", (e) => { e.preventDefault(); const p = floorPoint(e); if (p) handlers.onHover?.(p); });
  dom.addEventListener("drop", (e) => {
    e.preventDefault();
    const sku = e.dataTransfer.getData("text/sku");
    const p = floorPoint(e);
    if (sku && p) handlers.onDropSku?.(sku, p);
  });

  // ---------- 동선을 걷는 사람 ----------
  const angleTo = (a, b) => Math.atan2(Math.sin(b - a), Math.cos(b - a));
  function stepWalkers(dt) {
    if (walkersPaused) return;
    for (const w of walkers) {
      w.t += dt;
      const { s, moving, v } = w.clock(w.t);
      const p = poseAt(w.path, s);
      w.node.position.set(p.xz[0], 0, p.xz[1]);
      // 몸은 발밑이 아니라 조금 앞(0.35 m)을 보고 0.3초쯤에 걸쳐 돈다 (모퉁이에서 휙 돌지 않게)
      const ahead = poseAt(w.path, s + LOOK_AHEAD_M);
      const want = Math.hypot(ahead.xz[0] - p.xz[0], ahead.xz[1] - p.xz[1]) > 0.05 ? Math.atan2(ahead.xz[0] - p.xz[0], ahead.xz[1] - p.xz[1]) : p.heading;
      w.heading += angleTo(w.heading, want) * Math.min(1, dt / TURN_S);
      if (moving) w.walk.timeScale = Math.max(v, 0.25) * w.stepRate; // 가속·감속할 때 걸음도 같이
      w.node.rotation.y = w.heading;
      if (moving !== w.moving) {
        w.moving = moving;
        const [from, to] = moving ? [w.idle, w.walk] : [w.walk, w.idle];
        to.reset().play();
        from.crossFadeTo(to, 0.25, false);
      }
      w.mixer.update(dt);
    }
  }
  const clearWalkers = () => {
    for (const w of walkers) w.mixer.stopAllAction();
    walkersG.clear();
    walkers = [];
  };

  const loader = new GLTFLoader();
  let finishSet = {};
  const api = {
    load(url) {
      loader.load(url + (url.includes("?") ? "&" : "?") + "v=" + Date.now(), (g) => {
        if (model) scene.remove(model);
        if (held?.kind === "object") { held = null; if (grid) grid.visible = false; } // 들고 있던 가구는 새 방으로 바뀜
        model = g.scene;
        walls = [];
        model.traverse((o) => {
          if (o.isMesh) o.material = o.material.clone();
          const kind = o.userData?.kind ?? o.parent?.userData?.kind;
          if (o.isMesh) {
            o.receiveShadow = true;
            o.castShadow = kind === "object";
            o.material.envMapIntensity = 0.25; // 방은 반사를 약하게: 해 그림자가 보이게
          }
          if (o.isMesh && (kind === "wall" || kind === "door" || kind === "window")) walls.push(o);
          if (kind === "product") o.visible = false; // 제품은 화면에서 직접 그린다
        });
        shell = shadowShell(model); // dressRoom이 창 크기를 바꾸기 전에 구멍 자리를 잡는다
        model.add(shell);
        walls.push(...dressRoom(model, finishSet));
        const mine = model;
        furnish(model, () => alive && model === mine, (id) => objectCats[id]);
        scene.add(model);
        new THREE.Box3().setFromObject(model).getCenter(center);
        if (!framed) { frame(keepCam); framed = true; }
        applySun();
      }, undefined, () => toast("3D 파일을 불러오지 못했습니다", true));
    },
    /** 놓은 제품을 다시 그린다. 끌고 있는 중이면 건너뛴다. */
    setPlacements(list, selectedId) {
      last = { ...last, list, selectedId };
      if (dragging || (held?.kind === "placement" && !held.dropping)) return;
      // 바뀐 것만 다시 만든다. 놓을 때마다 전부 새로 만들면 가구가 많을수록 버벅인다
      const keep = new Map();
      for (const c of products.children) if (c.userData.key && !c.userData.dirty) keep.set(c.userData.key, c);
      const next = [];
      for (const p of list) {
        if (!p.size_m) continue;
        const selected = p.placement_id === selectedId;
        const key = JSON.stringify([p.placement_id, p.sku, p.center_xz, p.yaw_rad, p.size_m, p.verdict, p.hex, selected, templates.has(p.sku)]);
        const old = keep.get(key);
        if (old) { keep.delete(key); next.push(old); continue; }
        const g = productBox(p, { selected });
        g.userData.key = key;
        next.push(g);
      }
      const stay = new Set(next);
      const gone = products.children.filter((c) => !stay.has(c));
      if (gone.length) { const tmpG = new THREE.Group(); gone.forEach((c) => tmpG.add(c)); clear(tmpG); }
      next.forEach((g) => { if (g.parent !== products) products.add(g); });
    },
    /** 고른 제품이 차지하는 공간(본체 + 문 여는 공간 + 이격)을 바닥에 점선으로. null이면 지운다. pts: 평면 좌표 [[x, y], …] */
    setNeed(pts) {
      clear(need);
      if (!pts?.length) return;
      const v = pts.map(([x, y]) => new THREE.Vector3(x, 0.012, y));
      const ln = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(v),
        new THREE.LineDashedMaterial({ color: SELECT_HEX, dashSize: 0.12, gapSize: 0.08, depthTest: false, transparent: true }));
      ln.computeLineDistances();
      ln.renderOrder = 18;
      const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, -y)));
      const fill = new THREE.Mesh(new THREE.ShapeGeometry(shape),
        new THREE.MeshBasicMaterial({ color: SELECT_HEX, transparent: true, opacity: 0.08, depthWrite: false }));
      fill.rotation.x = -Math.PI / 2;
      fill.position.y = 0.004;
      need.add(fill, ln);
    },
    /** 미리 보기 상자 (pose-check 결과). null이면 지운다. */
    setGhost(res) {
      last = { ...last, ghost: res };
      if (!res?.size_m) { clear(ghost); return; }
      // 카메라 바로 앞(화면 아래 끝)에 오면 반투명 상자가 화면을 하얗게 덮는다 → 그때는 그리지 않는다
      const [gx, gz] = res.pose.center_xz;
      const reach = Math.hypot(res.size_m[0], res.size_m[2]) / 2 + GHOST_NEAR_M;
      ghost.visible = walk || Math.hypot(cam.position.x - gx, cam.position.z - gz) >= reach;
      // 마우스를 따라갈 때는 같은 모양이면 자리·방향만 옮긴다 (매번 새로 만들면 버벅인다)
      const key = JSON.stringify([res.sku, res.size_m, res.verdict, res.hex, templates.has(res.sku)]);
      const cur = ghost.children[0];
      if (cur && cur.userData.ghostKey === key) {
        cur.position.set(gx, 0, gz);
        cur.rotation.y = -((res.pose.yaw_rad ?? Math.PI / 2) - Math.PI / 2);
        return;
      }
      clear(ghost);
      ghost.add(productBox({ center_xz: res.pose.center_xz, yaw_rad: res.pose.yaw_rad, size_m: res.size_m, verdict: res.verdict, hex: res.hex, sku: res.sku }, { preview: true }));
      ghost.children[0].userData.ghostKey = key;
    },
    /** 끄는 동안 판정 색만 바꾼다 */
    setDragVerdict(id, verdict) {
      const g = products.children.find((c) => c.userData.placementId === id);
      if (!g) return;
      g.userData.dirty = true; // 색을 바꿨으니 다음 그리기에서 새로 만든다
      const hex = VERDICT_HEX[verdict] ?? VERDICT_HEX.unknown;
      g.children.forEach((c) => { if ((c.isLineSegments && !c.userData.dim) || c.userData.verdictPlate) c.material.color.setHex(hex); });
    },
    /** 공유기 자리 {center_xz, yaw_rad}. null이면 숨긴다. 들고 있는 동안에는 자리를 덮지 않는다 */
    setRouter(rt) {
      routerPose = rt ? { xz: [...rt.center_xz], yaw: rt.yaw_rad ?? 0, y: rt.height_m ?? 0 } : null;
      if (!rt) { if (held?.kind === "router") api.cancelHold(); routerG.visible = false; return; }
      loadAsset(ROUTER_URL).then((g) => {
        if (!g || !alive) return;
        if (!routerG.children.length) {
          const m = g.scene.clone(true);
          m.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
          routerG.add(m);
        }
        if (!routerPose || held?.kind === "router") return;
        routerG.position.set(routerPose.xz[0], routerPose.y, routerPose.xz[1]);
        routerG.rotation.set(0, -routerPose.yaw, 0);
        routerG.visible = true;
      });
    },
    /** 공유기 놓기: 마우스를 따라다니는 공유기. null이면 원래 자리로 (없으면 숨김) */
    routerFollow(xz) {
      loadAsset(ROUTER_URL).then((g) => {
        if (!g || !alive) return;
        if (!routerG.children.length) {
          const m = g.scene.clone(true);
          m.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
          routerG.add(m);
        }
        if (xz) {
          routerG.position.set(xz[0], surfaceY(xz), xz[1]);
          routerG.visible = true;
        } else if (routerPose) {
          routerG.position.set(routerPose.xz[0], routerPose.y, routerPose.xz[1]);
        } else routerG.visible = false;
      });
    },
    /** 동선 경로들([[x,y],...] 목록)을 사람이 하나씩 걷는다. 빈 목록이면 지운다 */
    setWalkers(paths) {
      const list = (paths || []).filter((p) => p?.length >= 2 && pathLength(p) > 0.3).slice(0, MAX_WALKERS);
      const key = JSON.stringify(list);
      if (key === walkersKey) return;
      walkersKey = key;
      clearWalkers();
      if (!list.length) return;
      loadAsset(PERSON_URL).then((g) => {
        if (!g || !alive || walkersKey !== key) return;
        const walkClip = g.animations.find((a) => a.name === "walk"), idleClip = g.animations.find((a) => a.name === "idle");
        list.forEach((path, i) => {
          const node = cloneSkinned(g.scene);
          node.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
          const mixer = new THREE.AnimationMixer(node);
          const walk = mixer.clipAction(walkClip), idle = mixer.clipAction(idleClip);
          const stepRate = walkClip.duration / STRIDE_M; // 1 m 갈 때 도는 동작 길이: 발이 미끄러지지 않게 빠르기에 맞춘다
          walk.timeScale = WALK_SPEED * stepRate;
          idle.play();
          walkersG.add(node);
          const smooth = smoothPath(path), len = pathLength(smooth); // 격자 계단을 펴고 모퉁이는 둥글게
          walkers.push({ node, mixer, walk, idle, path: smooth, moving: false, heading: poseAt(smooth, 0.3).heading, stepRate,
            clock: routeClock(len, { speed: WALK_SPEED, pause: 1.5, ease: WALK_EASE_S }), t: -i * 1.2 });
        });
      });
    },
    /** 걷는 사람 멈추기/다시 걷기 (화면 캡처용) */
    pauseWalkers(on = true) { walkersPaused = !!on; },
    /** 걷는 사람 (E2E 확인용) */
    walkersInfo() { return walkers.map((w) => ({ pos: [+w.node.position.x.toFixed(3), +w.node.position.z.toFixed(3)], moving: w.moving })); },
    routerInfo() { return { visible: routerG.visible && routerG.children.length > 0, pos: [+routerG.position.x.toFixed(3), +routerG.position.z.toFixed(3)], yaw: +(-routerG.rotation.y).toFixed(3) }; },
    /** 평면 오버레이(SVG, 단위 m)를 바닥 텍스처로 깐다. svg가 비면 끈다. */
    setOverlay(inner, box) {
      if (!inner || !box) { overlay.visible = false; return; }
      const [x0, y0, w, h] = box;
      const px = 1024, k = px / Math.max(w, h);
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.round(w * k)}" height="${Math.round(h * k)}" viewBox="${x0} ${y0} ${w} ${h}"><style>${OVERLAY_CSS}</style>${inner}</svg>`;
      const img = new Image();
      img.onload = () => {
        const cv = document.createElement("canvas");
        cv.width = img.width; cv.height = img.height;
        cv.getContext("2d").drawImage(img, 0, 0);
        overlay.material.map?.dispose();
        overlay.material.map = new THREE.CanvasTexture(cv);
        overlay.material.map.colorSpace = THREE.SRGBColorSpace;
        overlay.material.needsUpdate = true;
        overlay.scale.set(w, h, 1);
        overlay.position.set(x0 + w / 2, 0.004, y0 + h / 2);
        overlay.visible = true;
      };
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    },
    /** 바닥 점 [x, z]의 화면 좌표 (E2E 확인용) */
    toScreen([x, z], y = 0) {
      const v = new THREE.Vector3(x, y, z).project(cam), r = dom.getBoundingClientRect();
      return [r.left + ((v.x + 1) / 2) * r.width, r.top + ((1 - v.y) / 2) * r.height];
    },
    /** 집어 들기. item = {kind: "placement"|"object", id, xz, yaw}. grab = 누른 점과 물건 중심의 차이 */
    hold(item, grabPoint) {
      api.cancelHold();
      const nodes = heldNodes(item);
      if (!nodes.length) return false;
      nodes.forEach((n) => { if (n.userData.placementId) n.userData.dirty = true; }); // 들어 옮긴 것은 다시 그릴 때 새로 만든다
      held = { ...item, nodes: nodes.map((n) => ({ node: n, baseY: n.position.y, orig: n.position.clone(), rot: n.rotation.y })),
        lift: 0, dropping: false, grab: grabPoint ? [item.xz[0] - grabPoint[0], item.xz[1] - grabPoint[1]] : [0, 0] };
      if (grid) grid.visible = true;
      return true;
    },
    held: () => held && { kind: held.kind, id: held.id, xz: [...held.xz], yaw: held.yaw },
    moveHeld(dx, dz) { if (held) { held.xz = [held.xz[0] + dx, held.xz[1] + dz]; handlers.onHoldMove?.(held, held.xz); } },
    rotateHeld(dyaw) { if (held) { held.yaw += dyaw; handlers.onHoldMove?.(held, held.xz); } },
    /** 내려놓기: 마지막 자리를 돌려준다 (저장은 부르는 쪽이) */
    dropHold() {
      if (!held) return null;
      const out = { kind: held.kind, id: held.id, xz: [...held.xz], yaw: held.yaw };
      held.dropping = true;
      const h = held;
      setTimeout(() => {
        if (held !== h) return;
        held = null;
        if (grid) grid.visible = false;
        if (h.kind === "placement") api.setPlacements(last.list, last.selectedId); // 내려놓는 동안 미뤄 둔 다시 그리기
      }, 180);
      return out;
    },
    /** 취소: 원래 자리로 */
    cancelHold() {
      if (!held) return;
      for (const { node, orig, rot } of held.nodes) { node.position.copy(orig); node.rotation.set(0, rot, 0); }
      held = null;
      if (grid) grid.visible = false;
    },
    /** 들고 있는 물건 바닥 판 색 (판정) */
    holdVerdict(verdict) {
      if (held?.kind === "placement") api.setDragVerdict(held.id, verdict);
    },
    /** 키보드 카메라: 화면 기준 앞뒤·좌우로 이동, 대상 둘레로 돌기 */
    panCamera(right, fwd) {
      const f = new THREE.Vector3().subVectors(ctl.target, cam.position).setY(0).normalize();
      const r = new THREE.Vector3().crossVectors(f, new THREE.Vector3(0, 1, 0));
      const d = r.multiplyScalar(right).add(f.multiplyScalar(fwd));
      cam.position.add(d);
      ctl.target.add(d);
    },
    orbitCamera(deg) {
      const v = new THREE.Vector3().subVectors(cam.position, ctl.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), (deg * Math.PI) / 180);
      cam.position.copy(ctl.target).add(v);
    },
    /** 카메라가 보는 방향 기준 바닥 단위 벡터 (방향키로 옮길 때) */
    screenAxes() {
      const f = new THREE.Vector3().subVectors(ctl.target, cam.position).setY(0).normalize();
      return { fwd: [f.x, f.z], right: [-f.z, f.x] };
    },
    /** 스캔 가구 종류 (3D 파일에 종류가 없을 때 씀). load 전에 부른다 */
    /** 3D에 입힐 실제 벽지·바닥재 { wall?, floor? }. 다음 load부터 반영 */
    setFinishes(f) { finishSet = f || {}; },
    setObjects(objects) { objectCats = Object.fromEntries((objects || []).map((o) => [o.object_id, o.category])); },
    /** 화면에 그린 것 세기 (E2E 확인용) */
    stats() {
      let furniture = 0;
      model?.traverse((o) => { if (o.isMesh && o.userData.shared && o.userData.kind === "object") furniture++; });
      return { furniture, products: products.children.length };
    },
    /** 평면 좌표 [x, z] 쪽으로 시점을 부드럽게 옮긴다 (보는 각도·거리는 그대로) */
    /** 벽 철거 고르기 켜기/끄기. 켜면 클릭이 벽({type:"wall", id})을 맞히고, 벽 위에서 커서가 바뀐다 */
    setWallPick(on) {
      wallPick = !!on;
      dom.style.cursor = on ? "crosshair" : "";
      model?.traverse((o) => {
        if (!o.isMesh || o.userData?.kind !== "wall") return;
        if (on && !o.userData.pickMat) { o.userData.pickMat = o.material; o.material = o.material.clone(); o.material.emissive?.set("#A50034"); o.material.emissiveIntensity = 0.18; }
        if (!on && o.userData.pickMat) { o.material.dispose(); o.material = o.userData.pickMat; delete o.userData.pickMat; }
      });
    },
    lookAt([x, z]) {
      if (walk || !Number.isFinite(x) || !Number.isFinite(z)) return;
      const target = new THREE.Vector3(x, 0.8, z);
      camGlide = { target, pos: target.clone().add(cam.position.clone().sub(ctl.target)) };
    },
    reframe(keep = false) { if (!keep) keepCam = false; setTimeout(() => { resize(); if (!walk) frame(keep && keepCam); }, 280); },
    /** 지금 카메라 자리 (다시 왔을 때 같은 눈높이로 보이게 저장용) */
    camera() { const c = walk ? walk.saved : { pos: cam.position, target: ctl.target };
      return { pos: c.pos.toArray().map((v) => +v.toFixed(3)), target: c.target.toArray().map((v) => +v.toFixed(3)) }; },
    /** 저장해 둔 카메라 자리로. 방을 처음 불러와도 방 전체 보기로 덮지 않는다 */
    setCamera(c) {
      const ok = (a) => Array.isArray(a) && a.length === 3 && a.every(Number.isFinite);
      if (!c || !ok(c.pos) || !ok(c.target)) return false;
      cam.position.fromArray(c.pos); ctl.target.fromArray(c.target); ctl.update();
      keepCam = true;
      return true;
    },
    /** 1인칭 둘러보기 켜기/끄기. world = walk.buildWorld(room, placements, hidden), null이면 끄기 */
    setWalk(world) {
      if (world && !walk) {
        if (held) api.cancelHold();
        walk = { world, keys: {}, saved: { pos: cam.position.clone(), target: ctl.target.clone(), fov: cam.fov } };
        ctl.enabled = false;
        if (grid) grid.visible = false;
        solidWalls();
        const c = shell?.userData.ceiling;
        if (c) { ceilingMesh.scale.set(c.w, c.d, 1); ceilingMesh.position.set(c.x, c.y, c.z); ceilingMesh.visible = true; }
        const s = spawnPoint(world);
        // 가장 멀리 트인 쪽을 보고 선다
        let bestYaw = 0, best = -1;
        for (let i = 0; i < 16; i++) {
          const yaw = (i / 16) * Math.PI * 2;
          const p = step(s, [-Math.sin(yaw) * 20, -Math.cos(yaw) * 20], world);
          const dist = Math.hypot(p[0] - s[0], p[1] - s[1]);
          if (dist > best) { best = dist; bestYaw = yaw; }
        }
        cam.fov = 70;
        cam.updateProjectionMatrix();
        cam.position.set(s[0], EYE_H, s[1]);
        cam.quaternion.setFromEuler(new THREE.Euler(-0.08, bestYaw, 0, "YXZ"));
        walkHud.hidden = false;
      } else if (world && walk) {
        walk.world = world; // 제품을 옮기거나 가구를 치웠을 때
        if (isBlocked([cam.position.x, cam.position.z], world)) {
          const s = spawnPoint(world);
          cam.position.set(s[0], EYE_H, s[1]);
        }
      } else if (!world && walk) {
        const sv = walk.saved;
        walk = null;
        look = null;
        if (plc.isLocked) plc.unlock();
        walkHud.hidden = cross.hidden = true;
        ceilingMesh.visible = false;
        cam.fov = sv.fov;
        cam.updateProjectionMatrix();
        cam.position.copy(sv.pos);
        ctl.target.copy(sv.target);
        cam.lookAt(sv.target);
        ctl.enabled = true;
      }
      return !!walk;
    },
    walking() { return !!walk; },
    /** 지금 선 자리 (E2E 확인용) */
    walkInfo() {
      if (!walk) return null;
      euler.setFromQuaternion(cam.quaternion);
      return { pos: cam.position.toArray().map((v) => +v.toFixed(3)), yaw: +euler.y.toFixed(3), locked: plc.isLocked,
        blocked: isBlocked([cam.position.x, cam.position.z], walk.world) };
    },
    /** 실제 해로 비춘다 (채광 API의 sun). null이면 기본 해. */
    /** 해 바꾸기. 기본은 부드럽게 이어서, instant면 바로 */
    setSun(s, { instant = false } = {}) { realSun = s && s.direction ? s : null; applySun(instant); },
    /** 지금 해 (E2E 확인용) */
    sunInfo() {
      return { real: !!realSun, color: "#" + sun.color.getHexString(), intensity: sun.intensity, hemi: hemi.intensity, env: +cur.env.toFixed(3), shell: !!shell?.visible,
        position: sun.position.toArray().map((v) => +v.toFixed(3)), target: sun.target.position.toArray().map((v) => +v.toFixed(3)) };
    },
    /** 접촉 그림자(GTAO) 켜고 끄기. 느린 PC용. mode: true | false | "debug"(AO 버퍼만 보기) */
    setAO(mode) {
      gtao.enabled = mode !== false;
      gtao.output = mode === "debug" ? GTAOPass.OUTPUT.Denoise : GTAOPass.OUTPUT.Default;
      return gtao.enabled;
    },
    dispose() { alive = false; clearWalkers(); ro.disconnect(); plc.dispose(); document.removeEventListener("keydown", onWalkKey, true); document.removeEventListener("keyup", onWalkKey, true); el.removeEventListener("pointerdown", onDown, { capture: true }); envTex.dispose(); pmrem.dispose(); gtao.dispose(); composer.dispose(); renderer.dispose(); el.innerHTML = ""; },
  };
  el.viewer = api;
  return api;
}
