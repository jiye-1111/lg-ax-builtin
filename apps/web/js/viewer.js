// 3D 뷰어 (three.js, glb) + 3D 안에서 바로 배치하기
// 평면 좌표 (x, y) = 3D (x, z), Y-up. 제품 yaw = 정면 방향, 상자 회전 = -(yaw - 90°) (glb.py와 같은 규칙)
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "../vendor/meshopt/meshopt_decoder.module.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { lookRadPerPx } from "./walk.js";
import { wantVelocity, ease, isMoving } from "./camkeys.js";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";
import { EYE_H, RUN, WALK, isBlocked, moveVector, spawnPoint, step } from "./walk.js";
import { lookYaw } from "./stops.js";
import { pointerAngle, turnTo, snapTurn, degLabel } from "./rotring.js";
import { reachOf, HANDLE_OUT_M } from "./stretch.js";
import { DOOR_BACK_M } from "./slot.js";
import { onPlane, grabOffset } from "./surfmove.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { coversCase, finishPart, materialLabel, surfaceKind, surfaceLook } from "./surface.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { clone as cloneSkinned } from "three/addons/utils/SkeletonUtils.js";
import { toast } from "./core.js";
import { WALK_SPEED, pathLength, poseAt, routeClock, smoothPath } from "./walker.js";
import { dressRoom, furnish, shadowShell, cutWalls, furnitureTemplate, fitFurniture, tintFurniture, glassLook, WIDE_DOOR_M, WIDE_WINDOW_M } from "./room3d.js";

const VERDICT_HEX = { fit: 0x1e7a4f, conditional: 0x1e7a4f, no_fit: 0xb3261e, unknown: 0x5b6370 };
// 고른 것도 판정 색 그대로 (빨강 = 안 들어감으로 읽히므로 선택·필요 공간에 LG 레드를 쓰지 않는다)
const SELECT_HEX = 0x5b6370;
const CLICK_PX = 6; // 이 이하로 움직이면 클릭으로 본다
const SURFACE_MAX_M = 2.2; // 공유기를 올릴 수 있는 가장 높은 윗면 (선반 꼭대기까지). 서버 Service.SURFACE_MAX_M과 같게
const NOT_SURFACE = new Set(["decor:wall", "decor:partition", "decor:rug", "decor:plant", "decor:lamp"]); // 서버 NOT_SURFACE와 같게
// 작은 가전(전자레인지·정수기 등)을 올려 둘 수 있는 가구와 높이. 서버 Service.HOSTS, pose.SURFACE_MAX_M과 같게
const PRODUCT_HOSTS = new Set(["decor:table", "decor:coffee", "decor:desk", "decor:dresser", "decor:basecab", "decor:island", "decor:islandtable", "decor:tvstand"]);
const PRODUCT_SURFACE_MAX_M = 1.2;
const SCANNED_TOPS = new Set(["table", "storage"]);
const skuOf = (o) => { while (o && !o.userData?.sku) o = o.parent; return o?.userData?.sku; };
const GHOST_NEAR_M = 0.8; // 미리 보기 상자가 카메라와 이만큼 가까우면 그리지 않는다
// 바닥 텍스처용 SVG에는 페이지 CSS가 안 먹으므로 오버레이 스타일을 같이 넣는다 (style.css의 .plan 오버레이와 같은 색)
const OVERLAY_CSS = `.sunpatch{fill:#ffd54a;fill-opacity:.55;stroke:#e0a800}.route{fill:none;stroke:#4b45b0;stroke-linecap:round;stroke-linejoin:round;stroke-opacity:.9}
.narrow{fill:none;stroke:#b3261e;stroke-opacity:.9}.tag rect{fill:#1c2024;fill-opacity:.82}.tag text{fill:#fff;font-weight:600}.router-sym rect{fill:#1c2024}.router-sym path{stroke:#1c2024}.start-dot{fill:#4b45b0;fill-opacity:.28;stroke:#4b45b0;stroke-width:.03px}text{font-family:Pretendard,sans-serif}`;

// 공유기·사람 모델 (Blender: build_router.py, build_person.py). 한 번만 받는다
const assets = new Map();
const loadAsset = (url) => {
  if (!assets.has(url)) assets.set(url, new GLTFLoader().loadAsync(url).catch(() => null));
  return assets.get(url);
};
const ROUTER_URL = "models/devices/router.glb", PERSON_URL = "models/people/walker.glb";
const MAX_TURN_RAD_S = 3.2; // 사람이 제자리에서 도는 빠르기 (반 바퀴에 1초쯤)
const WALK_EASE_S = 0.6, LOOK_AHEAD_M = 0.35, TURN_S = 0.3; // 출발·정지 가감속, 몸이 보는 앞쪽, 도는 시간
const STRIDE_M = 1.3 * 32 / 30; // build_person.py: walk 한 주기(32프레임, 30 fps)에 1.3 m/s로 가는 거리
const MAX_WALKERS = 4;
const GLAZED = new Set(["decor:window", "decor:glassdoor"]); // 벽에 다는 창: 그 자리 벽을 뚫고 유리는 비치게
// 넓게 늘린 창은 네 짝짜리 모델로 그린다 (두 짝을 늘리면 한 짝이 너무 넓어진다)
const modelKey = (p) => (p.sku === "decor:glassdoor" && p.size_m?.[0] >= WIDE_DOOR_M ? "decor:glassdoor4"
  : p.sku === "decor:window" && p.size_m?.[0] >= WIDE_WINDOW_M ? "decor:window4" : p.sku);
const DOOR_SKU = "decor:door", DOOR_JAMB_M = 0.036, DOOR_FACE_M = 0.018, DOOR_OPEN_RAD = (78 * Math.PI) / 180; // 문짝 왼쪽 끝과 앞면 자리: build_furniture.py door와 같게

// 제품 모델: 한 번 받아 두고 배치마다 복제한다 (화면을 바꿔도 다시 받지 않는다)
const MODEL_DIR = "models/products/";
const templates = new Map();
const pending = new Map();
let modelIndex = null;
let companionIndex = null;
const gltf = new GLTFLoader();
gltf.setMeshoptDecoder(MeshoptDecoder); // 제품 모델은 meshopt로 눌러 담겨 있다
// 색만 다른 모델은 파일 하나를 같이 쓴다: 파일은 한 번만 받고, 모델명에 맞는 색(KHR_materials_variants, 이름 = 묶음 SKU)을 복사본에 입힌다
const files = new Map();
function loadVariant(file, variant) {
  if (!files.has(file)) files.set(file, gltf.loadAsync(MODEL_DIR + file));
  return files.get(file).then(async (g) => {
    const scene = g.scene.clone(true);
    const i = variant ? (g.parser.json.extensions?.KHR_materials_variants?.variants ?? []).findIndex((v) => v.name === variant) : -1;
    if (i < 0) return scene;
    const jobs = [];
    scene.traverse((o) => {
      const hit = o.isMesh && o.userData.gltfExtensions?.KHR_materials_variants?.mappings?.find((m) => m.variants.includes(i));
      if (hit) jobs.push(g.parser.getDependency("material", hit.material).then((m) => { o.material = m; }));
    });
    await Promise.all(jobs);
    return scene;
  });
}
// 제품 겉면: 카탈로그의 재질(메탈·스테인리스·글라스)대로 문짝과 몸통이 빛나고 주변이 비치게 한다 (surface.js)
const surfaces = new Map();
const glossy = new Set(); // 재질을 입힌 문짝·몸통 재질 (방 안 모습이 비치는 면)
function dressModel(sku, root) {
  const kind = surfaces.get(sku), look = surfaceLook(kind);
  if (!look || root.userData.surface === kind) return;
  const done = new Map();
  root.traverse((o) => {
    if (!o.isMesh) return;
    const part = finishPart(o.material.name);
    if (!part || (part === "case" && !coversCase(kind))) return;
    if (!done.has(o.material)) {
      // 색만 다른 모델끼리 재질을 같이 쓰니 늘 복사본에 입힌다. 맑은 겉칠은 MeshPhysicalMaterial에만 있다. 모델이 표준 재질로 왔으면 색·무늬를 옮겨 바꾼다
      const m = o.material.isMeshPhysicalMaterial ? o.material.clone() : new THREE.MeshPhysicalMaterial({ name: o.material.name, color: o.material.color, map: o.material.map, normalMap: o.material.normalMap });
      Object.assign(m, look);
      m.needsUpdate = true;
      glossy.add(m);
      done.set(o.material, m);
    }
    o.material = done.get(o.material);
  });
  root.userData.surface = kind;
}
/** 카탈로그를 받으면 한 번 부른다. 이미 받아 둔 모델에도 바로 입힌다 */
export function setProductSurfaces(products) {
  for (const p of products || []) {
    const kind = surfaceKind(materialLabel(p), p.cmf_options?.[0]?.color);
    if (kind) surfaces.set(p.sku, kind);
  }
  templates.forEach((t, sku) => { if (t.isObject3D) dressModel(sku, t); });
}
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
      loadVariant(entry.file, entry.variant),
      comp ? loadVariant(comp.file, comp.variant).catch(() => null) : null,
    ]).then(([scene, part]) => {
      if (part) {
        part.position.fromArray(comp.offset_m);
        part.userData.companion = true;
        scene.add(part);
      }
      dressModel(sku, scene);
      templates.set(sku, scene);
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
  const ROOM_ENV_SKY = new THREE.Color("#f3efe8"); // 벽이 열린 쪽으로 비치는 바깥: 밝은 천장빛
  const STAGE_BG = new THREE.Color("#ffe6c4"), STAGE_BG_SHOWN = new THREE.Color("#e1d8ca");
  scene.background = STAGE_BG.clone(); // 톤 매핑을 거치면 따뜻한 회색(#e1d8ca)으로 보인다
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
  sun.shadow.normalBias = 0.04; // 둥근 쿠션 면에 줄무늬(그림자 얼룩)가 생기지 않게
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
  // AO는 그림자 껍데기(벽·천장)를 숨기고 한 번 더 그린다. 그때 그림자 지도까지 다시 만들면 벽·천장 그림자가 빠진 지도가 남아서,
  // 느린 PC가 화면을 돌리는 동안(그림자를 다시 안 만드는 가벼운 그리기) 볕 든 자리가 사라지고 방 전체가 환해진다. AO에서는 그림자를 건드리지 않는다
  const gtaoRender = gtao.render.bind(gtao);
  gtao.render = (...args) => {
    const sm = renderer.shadowMap, auto = sm.autoUpdate, need = sm.needsUpdate;
    sm.autoUpdate = false; sm.needsUpdate = false;
    try { gtaoRender(...args); } finally { sm.autoUpdate = auto; sm.needsUpdate = need; }
  };
  composer.addPass(gtao);
  composer.addPass(new OutputPass());
  const ctl = new OrbitControls(cam, renderer.domElement);
  ctl.enableDamping = true;
  ctl.dampingFactor = 0.14; // 손을 떼면 금방 선다 (기본 0.05는 미끄러지듯 오래 흘러서 붕 뜬 느낌)
  ctl.maxPolarAngle = Math.PI * 0.49; // 바닥 아래로는 못 내려가게
  ctl.minDistance = 1.2;                // 가구 속으로 파고들지 않게
  // 휠을 누른 채 끌면 화면 중심을 옮긴다 (CAD·Blender처럼). 확대는 휠 굴리기, 오른쪽 끌기도 이동
  ctl.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN };
  ctl.screenSpacePanning = false; // 바닥과 나란히 움직여 시점이 바닥 아래로 빠지지 않게
  ctl.addEventListener("start", () => { camGlide = null; }); // 직접 돌리거나 확대하면 데려가던 시점 옮기기는 멈춘다 (안 그러면 되돌아간다)
  ctl.zoomToCursor = true; // 휠로 확대하면 커서가 가리키는 곳으로 다가간다 (Planner 5D·지도처럼)
  let grid = null, held = null; // 집어 든 물건 (건축 모드)
  let objectCats = {};           // 스캔 가구 id → 종류 (room.json)
  let objectColors = {};         // 스캔 가구 id → 고른 색
  let objectPartColors = {};     // 스캔 가구 id → {부위: 색}
  let model = null, framed = false, keepCam = false, alive = true, walls = [], center = new THREE.Vector3();
  const tmp = new THREE.Vector3(), toCam = new THREE.Vector3();

  // 화면에서 그리는 층: 바닥 오버레이 → 놓은 제품 → 미리 보기
  const overlay = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
  overlay.rotation.x = -Math.PI / 2;
  overlay.position.y = 0.004;
  overlay.visible = false;
  let overlayTurn = 0;
  overlay.renderOrder = 1;
  scene.add(overlay);
  const products = new THREE.Group();
  /** 화면에 보이는 LG 제품의 화면 자리 [{sku, box:[x0,y0,x1,y1]}] (0~1, 위가 0). 카메라 뒤나 화면 밖은 뺀다 */
  const productBoxes = () => {
    const out = [], v = new THREE.Vector3(), bb = new THREE.Box3();
    for (const g of products.children) {
      const sku = g.userData.sku;
      if (!g.visible || !sku || sku.startsWith("decor:")) continue;
      bb.makeEmpty();
      g.traverse((o) => { if (o.isMesh && o.visible && !o.userData.verdictPlate) bb.expandByObject(o); });
      if (bb.isEmpty()) continue;
      let x0 = 1, y0 = 1, x1 = 0, y1 = 0, behind = false;
      for (let i = 0; i < 8; i++) {
        v.set(i & 1 ? bb.max.x : bb.min.x, i & 2 ? bb.max.y : bb.min.y, i & 4 ? bb.max.z : bb.min.z).project(cam);
        if (v.z > 1) { behind = true; break; }
        const x = (v.x + 1) / 2, y = (1 - v.y) / 2;
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      }
      const c = (n) => Math.round(Math.max(0, Math.min(1, n)) * 1e4) / 1e4;
      [x0, y0, x1, y1] = [c(x0), c(y0), c(x1), c(y1)];
      if (behind || x1 - x0 < 0.01 || y1 - y0 < 0.01) continue;
      out.push({ sku, box: [x0, y0, x1, y1] });
    }
    return out.slice(0, 24);
  };
  scene.add(products);
  const ghost = new THREE.Group();
  scene.add(ghost);
  const need = new THREE.Group(); // 고른 제품이 차지하는 공간 표시
  scene.add(need);
  // 회전 고리: 고른 물건 둘레 바닥에 고리와 손잡이. 손잡이(또는 고리)를 끌면 커서 쪽으로 돈다 (Planner 5D·Houzz처럼)
  const RING_HEX = 0x6b6f76, RING_ON_HEX = 0x2f3236; // 빨강은 "안 들어감"으로 읽혀서 쓰지 않는다
  const ringMat = new THREE.MeshBasicMaterial({ color: RING_HEX, transparent: true, opacity: 0.55, depthTest: false, depthWrite: false });
  const knobMat = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, depthWrite: false });
  const knobRimMat = new THREE.MeshBasicMaterial({ color: RING_HEX, depthTest: false, depthWrite: false });
  const rotRing = new THREE.Group();
  rotRing.visible = false;
  rotRing.renderOrder = 5;
  scene.add(rotRing);
  let ringInfo = null, ringDrag = null, wasBusy = false;
  const ringChip = document.createElement("div");
  ringChip.className = "rot-chip";
  ringChip.hidden = true;
  const buildRing = (r) => {
    clear(rotRing);
    const band = new THREE.Mesh(new THREE.RingGeometry(r - 0.016, r + 0.016, 96), ringMat);
    const hit = new THREE.Mesh(new THREE.RingGeometry(r - 0.09, r + 0.09, 64), new THREE.MeshBasicMaterial({ visible: false }));
    hit.userData.ringPart = true;
    const arm = new THREE.Group(); // 손잡이: 앞쪽(0°)에 둔다
    const rim = new THREE.Mesh(new THREE.CircleGeometry(0.085, 32), knobRimMat);
    const knob = new THREE.Mesh(new THREE.CircleGeometry(0.06, 32), knobMat);
    const grip = new THREE.Mesh(new THREE.CircleGeometry(0.16, 24), new THREE.MeshBasicMaterial({ visible: false }));
    grip.userData.ringPart = true; grip.userData.knob = true;
    rim.position.y = 0.001; knob.position.y = 0.002;
    [rim, knob, grip].forEach((m, i) => { m.position.z = r; m.rotation.x = -Math.PI / 2; m.renderOrder = 6 + i; arm.add(m); }); // 테두리 위에 흰 손잡이
    [band, hit].forEach((m) => { m.rotation.x = -Math.PI / 2; m.renderOrder = 5; });
    arm.name = "arm";
    rotRing.add(band, hit, arm);
  };
  // 장 끝 손잡이: 고른 장의 양 끝 바닥에 좌우 화살표. 끌면 그 끝만 움직여 길이가 늘거나 준다 (IKEA 플래너처럼)
  // 아일랜드처럼 벽에서 떨어진 것(deep)은 앞뒤에도 손잡이가 있어 깊이도 늘린다. 손잡이 번호: 폭 ±1, 깊이 ±2 (+가 정면 쪽)
  const stretchG = new THREE.Group();
  stretchG.visible = false;
  stretchG.renderOrder = 5;
  scene.add(stretchG);
  let stretchInfo = null, stretchDrag = null;
  const buildStretch = () => {
    let order = 6; // 깊이를 안 보고 그리므로 테두리 → 흰 바탕 → 화살표 차례를 정해 준다
    const flat = (m, y) => { m.rotation.x = -Math.PI / 2; m.position.y = y; m.renderOrder = order++; return m; };
    const arrow = new THREE.Shape([new THREE.Vector2(0.05, 0), new THREE.Vector2(0.014, 0.03), new THREE.Vector2(0.014, -0.03)]);
    for (const side of [-1, 1, -2, 2]) {
      const h = new THREE.Group();
      order = 6;
      h.name = `end${side}`;
      if (Math.abs(side) === 2) h.rotation.y = Math.PI / 2; // 화살표가 앞뒤를 보게
      const grip = new THREE.Mesh(new THREE.CircleGeometry(0.17, 24), new THREE.MeshBasicMaterial({ visible: false }));
      grip.userData.stretch = side;
      const right = new THREE.Mesh(new THREE.ShapeGeometry(arrow), knobRimMat), left = new THREE.Mesh(new THREE.ShapeGeometry(arrow), knobRimMat);
      left.scale.x = -1;
      h.add(flat(new THREE.Mesh(new THREE.CircleGeometry(0.095, 32), knobRimMat), 0.001), flat(new THREE.Mesh(new THREE.CircleGeometry(0.078, 32), knobMat), 0.002),
        flat(right, 0.003), flat(left, 0.003), flat(grip, 0.004));
      stretchG.add(h);
    }
  };
  const placeStretch = () => {
    const i = stretchInfo;
    if (!i) return;
    stretchG.position.set(i.xz[0], (i.y || 0) + 0.014, i.xz[1]);
    stretchG.rotation.y = -(i.yaw - Math.PI / 2);
    for (const side of [-1, 1]) stretchG.getObjectByName(`end${side}`).position.x = side * (i.w / 2 + HANDLE_OUT_M);
    for (const side of [-1, 1]) {
      const h = stretchG.getObjectByName(`end${side * 2}`);
      h.visible = !!i.deep;
      h.position.z = side * (i.d / 2 + HANDLE_OUT_M);
    }
  };
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
  // 동선 출발 자리 고르기: 마우스를 따라오는 사람 (발밑에 고리)
  const starter = new THREE.Group();
  starter.visible = false;
  scene.add(starter);
  let starterMixer = null, starterAsked = false;
  {
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.36, 48), new THREE.MeshBasicMaterial({ color: 0x4b45b0, transparent: true, opacity: 0.75, depthWrite: false }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.008;
    starter.add(ring);
  }

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
  // 눈높이 1.6 m에서 WASD로 걷고, 화면을 끌어서 둘러본다(끄는 동안만 천천히 돈다). 벽·가구·제품은 못 지나간다.
  const plc = new PointerLockControls(cam, renderer.domElement);
  plc.pointerSpeed = 0.8;
  let camKeys = {}, camVel = [0, 0, 0]; // 키보드로 화면 움직이기 (누르고 있는 동안)
  let camGlide = null; // 새로 놓은 제품 쪽으로 시점을 부드럽게 옮길 때
  let walk = null, lastT = performance.now(), stepSunFn = null; // 해 보간 함수는 아래 '해'에서 채운다
  const euler = new THREE.Euler(0, 0, 0, "YXZ");
  // W A S D로 걷고, 방향키로 고개를 돌린다
  const KEYS = { KeyW: "f", KeyS: "b", KeyA: "l", KeyD: "r", ArrowLeft: "tl", ArrowRight: "tr", ArrowUp: "tu", ArrowDown: "td" };
  const TURN_RAD_S = 1.5, NOD_RAD_S = 0.8;
  let lookVel = [0, 0, 0];
  const onWalkKey = (e) => {
    if (!walk || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    const k = KEYS[e.code];
    if (e.key === "Shift") walk.keys.run = e.type === "keydown";
    if (!k) return;
    walk.keys[k] = e.type === "keydown";
    if (e.type === "keydown") stopGlide(); // 직접 걸으면 데려다주던 걸음은 멈춘다
    walkHud.hidden = true; // 걷기 시작하면 안내는 접는다
    e.preventDefault();
    e.stopImmediatePropagation(); // 건축 모드 키(WASD 카메라·R 돌리기)와 겹치지 않게
  };
  document.addEventListener("keydown", onWalkKey, true);
  document.addEventListener("keyup", onWalkKey, true);
  const walkHud = document.createElement("div");
  walkHud.className = "walk-hud";
  walkHud.hidden = true;
  Object.assign(walkHud.style, { position: "absolute", left: "50%", top: "16px", transform: "translateX(-50%)",
    background: "rgba(20,22,26,.72)", color: "#fff", padding: "10px 14px", borderRadius: "10px", font: "13px/1.5 sans-serif",
    pointerEvents: "none", textAlign: "center", zIndex: 3 });
  // 손으로 쓰는 화면에는 키보드 안내를 보이지 않는다
  const touchOnly = globalThis.matchMedia?.("(hover: none) and (pointer: coarse)").matches;
  walkHud.innerHTML = touchOnly ? "화면을 끌어서 둘러봐요"
    : "<b>W A S D</b> 걷기 · <b>방향키</b> 둘러보기 · <b>Shift</b> 빠르게<br>화면을 끌어서 둘러봐도 돼요";
  const cross = document.createElement("div");
  cross.hidden = true;
  Object.assign(cross.style, { position: "absolute", left: "50%", top: "50%", width: "6px", height: "6px", margin: "-3px 0 0 -3px",
    borderRadius: "50%", background: "rgba(255,255,255,.85)", boxShadow: "0 0 0 1px rgba(0,0,0,.35)", pointerEvents: "none", zIndex: 3 });
  if (getComputedStyle(el).position === "static") el.style.position = "relative";
  el.append(walkHud, cross, ringChip);
  plc.addEventListener("lock", () => { walkHud.hidden = true; cross.hidden = false; });
  plc.addEventListener("unlock", () => { if (walk) { walkHud.hidden = false; cross.hidden = true; } walk && (walk.keys = {}); });
  // 들를 곳까지 데려다주기: 길을 따라 걸으면서 가는 쪽을 보고, 다 와서는 그곳에서 볼 방향으로 돈다
  const GLIDE_SPEED = 1.5, GLIDE_TURN = 3.5, GLIDE_AHEAD_M = 0.6, GLIDE_FACE_M = 0.7, GLIDE_PITCH = -0.06;
  // 들를 곳에 잠깐 서 있는 사이(걸음이 없을 때)에 눌러도 이어 보기는 멈춰야 한다
  const stopGlide = () => { if (!walk) return; walk.glide = null; handlers.onWalkStop?.(); };
  const glideTick = (dt) => {
    const g = walk.glide;
    euler.setFromQuaternion(cam.quaternion);
    let want = g.yaw;
    if (g.s < g.len) {
      const left = g.len - g.s;
      const v = GLIDE_SPEED * Math.max(0.2, Math.min(1, (g.s + 0.1) / 0.5, (left + 0.05) / 0.6)); // 천천히 떠나고 천천히 선다
      g.s = Math.min(g.len, g.s + v * dt);
      const p = poseAt(g.path, g.s).xz;
      cam.position.set(p[0], EYE_H, p[1]);
      if (left > GLIDE_FACE_M) {
        const a = poseAt(g.path, Math.min(g.len, g.s + GLIDE_AHEAD_M)).xz;
        if (Math.hypot(a[0] - p[0], a[1] - p[1]) > 0.05) want = lookYaw(p, a);
      }
    }
    const k = Math.min(1, dt * GLIDE_TURN), off = Math.atan2(Math.sin(want - euler.y), Math.cos(want - euler.y));
    euler.y += off * k;
    euler.x += (g.pitch - euler.x) * k;
    euler.z = 0;
    cam.quaternion.setFromEuler(euler);
    if (g.s >= g.len && Math.abs(off) < 0.03 && Math.abs(g.pitch - euler.x) < 0.03) { walk.glide = null; g.done?.(); }
  };
  const walkTick = (dt) => {
    if (walk.glide) { glideTick(dt); return; }
    euler.setFromQuaternion(cam.quaternion);
    const k = walk.keys;
    lookVel = ease(lookVel, [((k.tl ? 1 : 0) - (k.tr ? 1 : 0)) * TURN_RAD_S, ((k.tu ? 1 : 0) - (k.td ? 1 : 0)) * NOD_RAD_S, 0], dt);
    if (Math.abs(lookVel[0]) > 0.002 || Math.abs(lookVel[1]) > 0.002) {
      euler.y += lookVel[0] * dt;
      euler.x = Math.max(-1.4, Math.min(1.4, euler.x + lookVel[1] * dt));
      euler.z = 0;
      cam.quaternion.setFromEuler(euler);
    }
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

  let down = null, dragging = null;
  let grabbing = null, rotKey = false; // 누른 채 끌어 잡기, E를 누른 채 돌리기
  const GRAB_PX = 6, SPIN_RAD_PER_PX = 0.012, SNAP_RAD = Math.PI / 4, WHEEL_RAD = Math.PI / 12;
  // 내장 그래픽처럼 느린 PC에서는 곱게 그린 한 장이 오래 걸려 둘러볼 때 뚝뚝 끊긴다.
  // 움직이는 동안에는 후처리(접촉 그림자)를 쉬고 가볍게 그리다가, 멈추면 다시 곱게 그린다. 빠른 PC는 늘 곱게 그린다.
  const SLOW_FRAME_MS = 28, SETTLE_MS = 220;
  const seenPos = new THREE.Vector3(), seenQuat = new THREE.Quaternion();
  let fullMs = 0, lastBusy = 0, prevFull = false, liteFrames = 0, forceLite = false;
  let sunBusy = false; // 해가 새 자리로 옮겨 가는 중 (시각을 바꿨을 때)
  // 문짝에 방 안이 비치게: 방 가운데에서 둘러본 모습을 작게 한 번 찍어 반짝이는 면에만 입힌다.
  // 배치가 바뀌고 손을 뗀 뒤에만 다시 찍는다 (매 장면마다 찍지 않으니 느린 PC에서도 가볍다).
  const ROOM_ENV_PX = 128, ROOM_ENV_REST_MS = 700, ROOM_ENV_EVERY_MS = 2500;
  const myGloss = new Map(); // 모델 재질 → 이 화면 전용 복사본 (비친 그림은 화면마다 따로 가진다)
  const glossOf = (mat) => { if (!myGloss.has(mat)) { const m = mat.clone(); m.envMap = roomEnv?.texture || null; myGloss.set(mat, m); } return myGloss.get(mat); };
  let roomEnv = null, roomEnvDirty = true, roomEnvAt = -1e9, roomCube = null;
  const bakeRoomEnv = (now) => {
    roomEnvDirty = false; roomEnvAt = now;
    if (!model || !myGloss.size) return;
    const box = new THREE.Box3().setFromObject(model);
    if (box.isEmpty()) return;
    roomCube ??= new THREE.CubeCamera(0.05, 40, new THREE.WebGLCubeRenderTarget(ROOM_ENV_PX, { type: THREE.HalfFloatType }));
    roomCube.position.set((box.min.x + box.max.x) / 2, Math.min(1.3, box.max.y * 0.6), (box.min.z + box.max.z) / 2);
    const bg = scene.background, auto = renderer.shadowMap.autoUpdate;
    scene.background = ROOM_ENV_SKY; renderer.shadowMap.autoUpdate = false;
    roomCube.update(renderer, scene);
    scene.background = bg; renderer.shadowMap.autoUpdate = auto;
    const next = pmrem.fromCubemap(roomCube.renderTarget.texture);
    roomEnv?.dispose();
    roomEnv = next;
    myGloss.forEach((m) => { if (!m.envMap) m.needsUpdate = true; m.envMap = roomEnv.texture; });
  };
  const renderFrame = (now, dtMs) => {
    if (roomEnvDirty && now - lastBusy > ROOM_ENV_REST_MS && now - roomEnvAt > ROOM_ENV_EVERY_MS) bakeRoomEnv(now);
    if (prevFull) fullMs = fullMs ? fullMs * 0.8 + dtMs * 0.2 : dtMs; // 곱게 그린 다음 장까지 걸린 시간
    const moves = !!held || !!dragging || (walkers.length > 0 && !walkersPaused);
    if (moves || !cam.position.equals(seenPos) || !cam.quaternion.equals(seenQuat)) lastBusy = now;
    seenPos.copy(cam.position); seenQuat.copy(cam.quaternion);
    const lite = forceLite || (now - lastBusy < SETTLE_MS && fullMs > SLOW_FRAME_MS);
    prevFull = !lite;
    if (!lite) { renderer.shadowMap.autoUpdate = true; composer.render(); return; }
    liteFrames += 1;
    renderer.shadowMap.autoUpdate = moves || sunBusy; // 시점만 움직일 때는 그림자를 다시 만들 필요가 없다 (해가 움직이는 중이면 만든다)
    renderer.setRenderTarget(null);
    // 바로 그리면 배경색은 톤 매핑을 안 거쳐서 살구색(#ffe6c4)으로 번쩍인다. 곱게 그릴 때 보이는 색으로 잠깐 바꿔 그린다
    const bg = scene.background;
    if (bg?.isColor && bg.equals(STAGE_BG)) scene.background = STAGE_BG_SHOWN;
    renderer.render(scene, cam);
    scene.background = bg;
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
      camVel = ease(camVel, wantVelocity(camKeys), dt);
      if (isMoving(camVel)) { api.panCamera(camVel[0] * dt, camVel[1] * dt); api.orbitCamera(camVel[2] * dt); }
      ctl.update();
      cutaway();
    }
    // 브라우저 확대·축소나 모니터 이동으로 화면 배율만 바뀌면 크기 변화가 안 잡혀 일부만 그려진다 → 매 프레임 배율을 확인
    if (renderer.getPixelRatio() !== Math.min(devicePixelRatio, 1.5)) resize();
    animateHeld();
    stepWalkers(dt);
    if (starter.visible) starterMixer?.update(dt);
    stepSunFn?.(dt);
    renderFrame(now, dt * 1000);
    requestAnimationFrame(loop);
  })();
  // ---------- 해 ----------
  // realSun: null이면 보기 좋은 기본 해(카메라 왼쪽 위). 있으면 {direction:[x,y,z](해 쪽), color, intensity(0~1), up}
  let realSun = null, shell = null, roomR = 8;
  // 새로 단 창·유리문 자리: 벽을 뚫고, 볕도 그리로 든다
  const glazedSpots = (list) => (list || []).filter((p) => (GLAZED.has(p.sku) || p.sku === DOOR_SKU) && p.size_m)
    .map((p) => ({ x: p.center_xz[0], y: (p.base_m || 0) + p.size_m[1] / 2, z: p.center_xz[1], w: p.size_m[0], h: p.size_m[1], door: p.sku === DOOR_SKU }));
  let spotKey = "";
  const openWalls = (list, force = false) => {
    if (!model) return;
    const spots = glazedSpots(list), key = JSON.stringify(spots);
    if (!force && key === spotKey) return;
    spotKey = key;
    cutWalls(model, spots);
    if (shell) { model.remove(shell); shell.traverse((o) => o.geometry?.dispose()); }
    shell = shadowShell(model, spots.filter((s) => !s.door));
    shell.visible = !!realSun;
    model.add(shell);
    renderer.shadowMap.needsUpdate = true;
  };
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
    const cast = cur.sun > 0.01;
    if (cast !== sun.castShadow) renderer.shadowMap.needsUpdate = true;
    sun.castShadow = cast;
    sunBusy = cur.dir.distanceToSquared(goal.dir) > 1e-9 || Math.abs(goal.sun - cur.sun) > 1e-3;
    placeSun();
    cur.env += (goal.env - cur.env) * k;
    // 값이 바뀌었거나, 가끔(0.5초마다) 새로 들어온 물체가 있는지 보고 다시 맞춘다
    envTick += dt;
    if (Math.abs(cur.env - envApplied) > 0.01 || envTick > 0.5) { envTick = 0; applyEnv(cur.env); }
  };
  stepSunFn = stepSun;
  const applySun = (instant = false) => {
    if (shell) shell.visible = !!realSun; // 벽·천장 그림자: 실제 해일 때만 (창으로만 볕이 든다)
    renderer.shadowMap.needsUpdate = true; // 가볍게 그리는 중이어도 그림자는 한 번 다시 만든다
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
    grid.visible = false;
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
  // 올려 두는 가전이 그 자리에서 올라설 윗면 높이 (없으면 바닥 0). 서버와 같은 규칙: 물건 가운데가 윗면 안에 있으면 올라간다
  const tmpP = new THREE.Vector3();
  const productTops = (skipId) => {
    const out = [];
    for (const p of last.list) {
      if (!p.size_m || p.placement_id === skipId || !PRODUCT_HOSTS.has(p.sku) || p.size_m[1] > PRODUCT_SURFACE_MAX_M) continue;
      const yaw = (p.yaw_rad ?? Math.PI / 2) - Math.PI / 2;
      out.push({ has: ([x, z]) => {
        const dx = x - p.center_xz[0], dz = z - p.center_xz[1];
        return Math.abs(dx * Math.cos(yaw) + dz * Math.sin(yaw)) <= p.size_m[0] / 2 && Math.abs(-dx * Math.sin(yaw) + dz * Math.cos(yaw)) <= p.size_m[2] / 2;
      }, top: p.size_m[1] });
    }
    model?.traverse((o) => { // 스캔한 탁자·수납장 (고르기용 단위 상자: 크기 = scale)
      if (!o.isMesh || o.userData.kind !== "object" || o.userData.shared || !o.visible) return;
      if (!SCANNED_TOPS.has(o.userData.category || objectCats[o.name])) return;
      const top = o.position.y + o.scale.y / 2;
      if (top <= PRODUCT_SURFACE_MAX_M) out.push({ has: ([x, z]) => { o.worldToLocal(tmpP.set(x, o.position.y, z)); return Math.abs(tmpP.x) <= 0.5 && Math.abs(tmpP.z) <= 0.5; }, top });
    });
    return out;
  };
  const productTopY = (xz, skipId) => productTops(skipId).reduce((m, t) => (t.top > m && t.has(xz) ? t.top : m), 0);
  const topY = (surface, xz, skipId) => (surface === "router" ? surfaceY(xz) : surface === "product" ? productTopY(xz, skipId) : null);
  const placeHeld = () => {
    if (!held) return;
    const top = topY(held.surface, held.xz, held.id);
    for (const { node, baseY } of held.nodes) {
      // 벽에 건 것은 들어 올리지 않고 벽을 따라 그 높이 그대로 움직인다
      node.position.set(held.xz[0], held.surface === "wall" ? held.y : (top ?? baseY) + held.lift, held.xz[1]);
      node.rotation.set(0, rotY(held.kind, held.yaw), 0);
    }
  };
  function animateHeld() {
    need.visible = !held; // 들고 옮기는 동안에는 옛 자리 표시를 숨긴다
    rotRing.visible = !!ringInfo && !held && !walk && !dragging && !grabbing && !stretchDrag; // 옮기는 동안에는 고리를 숨긴다
    stretchG.visible = !!stretchInfo && !held && !walk && !dragging && !grabbing && !ringDrag;
    // 옮기거나 돌리는 동안에는 위에 뜨는 메뉴가 물건을 가리지 않게 (.canvas.moving-item)
    const busy = !!(held && !held.dropping) || !!ringDrag || !!stretchDrag || !!dragging?.moved;
    if (busy !== wasBusy) { wasBusy = busy; el.closest(".canvas")?.classList.toggle("moving-item", busy); }
    if (!held) return;
    const target = held.dropping ? 0 : LIFT;
    held.lift += (target - held.lift) * 0.3;
    placeHeld();
  }


  // 문: 열 수 있으면 문짝을 열어 두고, 못 열면 닫힌 채 바닥에 붉은 열림 자리를 깐다. 고르거나 놓는 중에는 열림 자리를 판정 색으로
  const doorExtras = (model, p, { selected, preview }) => {
    const [w, , d] = p.size_m, blocked = p.verdict === "no_fit";
    const hingeX = -w / 2 + DOOR_JAMB_M, leafW = w - 2 * DOOR_JAMB_M, out = [];
    const pivot = new THREE.Group();
    const hingeZ = d / 2 - DOOR_FACE_M; // 경첩 축: 문짝 앞면 왼쪽 모서리
    pivot.position.set(hingeX, 0, hingeZ);
    const leaf = [];
    model.traverse((o) => { if (o.isMesh && o.name.startsWith("leaf")) leaf.push(o); });
    leaf.forEach((o) => { o.position.x -= hingeX; o.position.z -= hingeZ; pivot.add(o); });
    pivot.rotation.y = blocked ? 0 : -DOOR_OPEN_RAD; // 경첩은 왼쪽, 앞(+z)으로 열린다
    out.push(pivot);
    if (blocked || selected || preview) {
      const fan = new THREE.Mesh(new THREE.CircleGeometry(leafW, 40, -Math.PI / 2, Math.PI / 2),
        new THREE.MeshBasicMaterial({ color: VERDICT_HEX[p.verdict] ?? VERDICT_HEX.unknown, transparent: true, opacity: 0.3, depthWrite: false, side: THREE.DoubleSide }));
      fan.rotation.x = -Math.PI / 2; // 바닥에 눕힌다: 원의 -y 쪽이 앞(+z)
      fan.position.set(hingeX, 0.007, d / 2);
      fan.userData.verdictPlate = true;
      out.push(fan);
    }
    return out;
  };
  // 이어지는 상판·가림판 재질: 옆 장 모델의 상판(stone)·몸통(white) 재질을 그대로 쓴다
  const coverMat = (look, hex, part = look === "tallcab" ? "white" : "stone") => {
    let m = null;
    const t = templates.get(`decor:${look}`);
    if (t) t.scene.traverse((o) => { if (!m && o.isMesh && o.material.name === part) m = o.material; });
    else requestModel(`decor:${look}`);
    m = m ? m.clone() : new THREE.MeshStandardMaterial({ color: part === "stone" ? 0xe8e4dc : 0xf2f2f0, roughness: 0.6 });
    if (hex) m.color.set(hex);
    return m;
  };
  // 장 칸에 끼운 빌트인 위를 덮는 판과, 제품 뒤가 비는 깊은 장(아일랜드)의 뒤 막음판. 제품 바닥 가운데 기준
  const coverParts = (w, h, d, c, id) => {
    const wide = w + c.left_m + c.right_m, tall = c.top_m - h, x = (c.right_m - c.left_m) / 2, out = [];
    const lid = new THREE.Mesh(new THREE.BoxGeometry(wide, tall, c.depth_m), coverMat(c.look, c.look === "tallcab" ? c.hex : c.top_hex));
    lid.position.set(x, h + tall / 2, c.off_m);
    out.push(lid);
    const back = c.off_m - c.depth_m / 2 + (c.back_m || 0), gap = -d / 2 - back; // 장 몸통 등에서 제품 등까지
    if (gap > 0.03) {
      const fill = new THREE.Mesh(new THREE.BoxGeometry(wide, h, gap), coverMat(c.look, c.hex, "white"));
      fill.position.set(x, h / 2, back + gap / 2);
      out.push(fill);
    }
    out.forEach((m) => { m.castShadow = m.receiveShadow = true; m.userData = { placementId: id, ownMaterial: true, cover: true }; });
    return out;
  };
  const productBox = (p, { selected = false, preview = false } = {}) => {
    const [w, h, d] = p.size_m;
    const g = new THREE.Group();
    const vhex = VERDICT_HEX[p.verdict] ?? VERDICT_HEX.unknown;
    const tmpl = p.sku && templates.get(modelKey(p));
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
        else if (glossy.has(o.material)) o.material = glossOf(o.material);
        if (o.material.name === "glass") { // 창 유리
          glassLook(o.material);
          o.castShadow = false;
          o.receiveShadow = false;
        }
        const isFinish = o.material.name === "finish";
        if (preview || (isFinish && p.hex)) {
          o.material = o.material.clone();
          o.userData.ownMaterial = true;
          if (isFinish && p.hex) o.material.color.set(p.hex);
          if (preview) Object.assign(o.material, { transparent: true, opacity: 0.5, depthWrite: false });
        }
      });
      if (tmpl.decor && !preview) tintFurniture(m, p.sku.slice(p.sku.indexOf(":") + 1), p.hex, p.part_colors, p.top_hex); // 고른 가구 색 (부위별)
      g.add(m);
      if (p.sku === DOOR_SKU) g.add(...doorExtras(m, p, { selected, preview }));
    } else {
      if (p.sku) requestModel(modelKey(p));
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
        new THREE.LineBasicMaterial({ color: !tmpl || preview || p.verdict === "no_fit" ? vhex : SELECT_HEX }));
      edges.position.y = h / 2;
      g.add(edges);
    }
    // 장 칸에 끼운 빌트인: 옆 장 상판이 그 위로 이어진다 (키큰장 줄이면 위 가림판)
    if (p.slot && !preview) g.add(...coverParts(w, h, d, p.slot, p.placement_id));
    // 바닥 판: 판정 색. 놓고 난 뒤에는 안 들어갈 때만 보이고, 들어가는 것은 옮기는 동안에만 보인다 (setDragVerdict)
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(w + 0.08, d + 0.08),
      new THREE.MeshBasicMaterial({ color: vhex, transparent: true, opacity: selected ? 0.55 : 0.35, depthWrite: false }));
    plate.rotation.x = -Math.PI / 2;
    plate.position.y = 0.006;
    plate.userData.verdictPlate = true;
    plate.visible = preview || p.verdict === "no_fit";
    if (selected || plate.visible) g.add(plate);
    // 치수선은 그리지 않는다: 놓을 때는 판정 색 테두리만 (치수는 제품 상세에서)
    g.position.set(p.center_xz[0], p.base_m || 0, p.center_xz[1]); // 가구 위에 올려 둔 것은 그 윗면 높이에
    g.rotation.y = -((p.yaw_rad ?? Math.PI / 2) - Math.PI / 2);
    g.userData = { placementId: p.placement_id, sku: p.sku, surface: p.hung ? "wall" : p.tabletop ? "product" : null };
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
  // 가구 윗면(책상·선반·식탁)을 가리키면 그 윗면 자리. 공유기·작은 가전처럼 위에 올려놓는 물건을 놓거나 옮길 때 쓴다
  // surface: "router"(선반 꼭대기까지) | "product"(식탁·아일랜드·하부장 높이까지), skipId: 지금 들고 있는 것(자기 자신은 받침이 아니다)
  const surfaceHit = (e, surface, skipId) => {
    setNdc(e);
    const max = surface === "product" ? PRODUCT_SURFACE_MAX_M : SURFACE_MAX_M;
    const ok = (sku) => (surface === "product" ? PRODUCT_HOSTS.has(sku) : !NOT_SURFACE.has(sku));
    const targets = products.children.filter((c) => c.userData.placementId !== skipId && ok(c.userData.sku));
    if (surface === "product" && model) model.traverse((o) => {
      if (o.isMesh && o.userData.kind === "object" && !o.userData.shared && o.visible && SCANNED_TOPS.has(o.userData.category || objectCats[o.name])) targets.push(o);
    });
    const hit = ray.intersectObjects(targets, true).find((h) => h.object.isMesh && h.face && h.point.y <= max + 0.01
      && tmp.copy(h.face.normal).transformDirection(h.object.matrixWorld).y > 0.7);
    return hit ? hit.point : null;
  };
  const surfacePoint = (e, surface = "router", skipId = null) => {
    const pt = surfaceHit(e, surface, skipId);
    if (!pt) return floorPoint(e);
    const snap = (v) => Math.round(v / 0.05) * 0.05;
    return surface === "product" ? [snap(pt.x), snap(pt.z)] : [pt.x, pt.z];
  };
  // 높이 h인 수평면에서 커서가 가리키는 점. 위에 올린 물건은 잡은 높이의 평면을 따라가야 바닥 먼 곳으로 튀지 않는다
  const planePoint = (e, h) => { setNdc(e); return onPlane(ray.ray.origin.toArray(), ray.ray.direction.toArray(), h); };
  // 벽걸이 제품은 마우스가 가리키는 벽 자리를 따라간다 (계산은 handlers.hangPoint → js/wallmount.js)
  const wallPoint = (e) => { const p = floorPoint(e, 0.01); return handlers.hangPoint?.(ray.ray.origin.toArray(), ray.ray.direction.toArray(), p) || p; };
  // 장 칸에 끼우는 빌트인은 가리킨 장이 선 자리를 따라간다 (비스듬히 보면 장 윗면 너머 바닥은 벽 뒤다)
  const cabPoint = (e) => {
    setNdc(e);
    const hit = ray.intersectObjects([...products.children.filter((c) => c.userData.sku in DOOR_BACK_M), carveG], true).find((h) => h.object.isMesh);
    return hit ? [hit.point.x, hit.point.z] : null;
  };
  const pointFor = (e) => { const sf = handlers.onSurface?.(); return sf === "wall" ? wallPoint(e) : sf === "slot" ? cabPoint(e) || floorPoint(e) : sf ? surfacePoint(e, sf === true ? "router" : sf) : floorPoint(e); };
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
    // 면만 맞힌다: 고른 물건의 테두리 선은 1 m 밖에서도 맞은 것으로 쳐서, 옆 물건을 눌러도 고른 물건이 다시 잡혔다
    const hit = ray.intersectObjects(targets, true).find((h) => h.object.visible && h.object.isMesh);
    if (!hit) return null;
    let o = hit.object;
    while (o && !o.userData?.placementId && o.userData?.kind !== "object" && !o.userData?.router) o = o.parent;
    if (!o) return null;
    if (o.userData.router) return { type: "router", id: "router" };
    const mat = hit.object.material?.name || null; // 누른 면의 재질: 색 고르기에서 그 부위를 바로 고른다
    if (o.userData.placementId) return { type: "placement", id: o.userData.placementId, mat };
    return { type: "object", id: o.name, mat };
  };
  // 치우기에서 마우스가 올라간 스캔 가구·창. top = ✕를 띄울 자리(위쪽 가운데)
  const hoverHit = (e) => {
    setNdc(e);
    const targets = [];
    model?.traverse((o) => { if (o.isMesh && o.visible && !o.userData.shared && (o.userData?.kind === "object" || o.userData?.kind === "window")) targets.push(o); });
    const o = ray.intersectObjects(targets, false)[0]?.object;
    return o ? { type: o.userData.kind, id: o.name, top: [o.position.x, o.position.y + o.scale.y / 2, o.position.z] } : null;
  };
  // ---- 회전 고리 끌기 ----
  const ringPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const ringPoint = (e) => {
    setNdc(e);
    ringPlane.constant = -(ringInfo?.y || 0);
    const v = ray.ray.intersectPlane(ringPlane, new THREE.Vector3());
    return v && [v.x, v.z];
  };
  const ringAt = (e) => {
    if (!rotRing.visible || !ringInfo || walk) return false;
    setNdc(e);
    const h = ray.intersectObjects(rotRing.children, true).find((x) => x.object.userData.ringPart);
    if (!h) return false;
    // 고리와 손잡이는 늘 맨 위에 그려진다: 보이는 대로 먼저 잡힌다 (옆 의자·책상 위에 걸쳐 있어도).
    // 손잡이는 언제나 잡힌다. 고리 줄만 고른 물건 몸통 너머면 몸통을 잡는다 (냉장고를 눌렀는데 돌아가면 안 된다)
    if (ray.intersectObjects(rotRing.children, true).some((x) => x.object.userData.knob)) return true;
    const mine = ray.intersectObjects(heldNodes(ringInfo), true).find((x) => x.object.visible && x.point.y > (ringInfo.y || 0) + 0.03);
    return !mine || h.distance <= mine.distance + 0.01;
  };
  const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
  const startRing = (e) => {
    const p = ringPoint(e);
    if (!p) return;
    const item = { kind: ringInfo.kind, id: ringInfo.id, xz: [...ringInfo.xz], yaw: ringInfo.yaw };
    const rot = rotY(item.kind, item.yaw);
    ringDrag = { item, nodes: heldNodes(item), rot, grab: pointerAngle(item.xz, p), a: rot, yaw: item.yaw, moved: false };
    ctl.enabled = false;
    renderer.domElement.setPointerCapture?.(e.pointerId);
    renderer.domElement.style.cursor = "grabbing";
    ringMat.color.setHex(RING_ON_HEX); knobRimMat.color.setHex(RING_ON_HEX); ringMat.opacity = 0.9;
  };
  const moveRing = (e) => {
    const p = ringPoint(e);
    if (!p) return;
    const g = ringDrag, now = pointerAngle(g.item.xz, p);
    // 커서가 뒤쪽(±180°)을 넘어가도 이어지게 잡은 각도를 따라 옮긴다
    const a = snapTurn(turnTo({ rot: g.rot, grab: g.grab }, g.grab + wrap(now - g.grab)), { fine: e.shiftKey, free: e.altKey });
    if (Math.abs(wrap(now - g.grab)) > Math.PI * 0.9) { g.rot = g.a; g.grab = now; } // 반 바퀴 넘게 돌리면 기준을 다시 잡는다
    g.a = a;
    g.moved = g.moved || Math.abs(wrap(a - rotY(g.item.kind, g.item.yaw))) > 1e-4;
    g.yaw = wrap(g.item.kind === "placement" ? Math.PI / 2 - a : -a);
    for (const n of g.nodes) n.rotation.y = a;
    rotRing.getObjectByName("arm").rotation.y = a;
    const r = el.getBoundingClientRect();
    ringChip.textContent = degLabel(a);
    ringChip.style.left = `${e.clientX - r.left + 16}px`;
    ringChip.style.top = `${e.clientY - r.top - 34}px`;
    ringChip.hidden = false;
    handlers.onRingMove?.({ ...g.item, yaw: g.yaw });
  };
  const endRing = () => {
    const g = ringDrag;
    ringDrag = null;
    ctl.enabled = true;
    ringChip.hidden = true;
    renderer.domElement.style.cursor = "";
    ringMat.color.setHex(RING_HEX); knobRimMat.color.setHex(RING_HEX); ringMat.opacity = 0.55;
    if (g.moved) { ringInfo = { ...ringInfo, yaw: g.yaw }; handlers.onRingEnd?.({ ...g.item, yaw: g.yaw }); }
  };
  // ---- 끼워 넣기 미리 보기: 끄는 동안 장이 칸을 내준 모습 (저장은 놓을 때 서버가) ----
  const carveG = new THREE.Group();
  scene.add(carveG);
  // 벽 길이 재기: 고른 벽 발치에 줄자처럼 긋는 선 (벽에 가려도 보인다)
  const tapeG = new THREE.Group();
  tapeG.visible = false;
  scene.add(tapeG);
  const tapeMat = new THREE.MeshBasicMaterial({ color: "#1f1f1f", depthTest: false, transparent: true });
  let carveKey = null, carveHid = [];
  const setCarve = (c) => {
    const key = c ? JSON.stringify(c) : null;
    if (key === carveKey) return;
    carveKey = key;
    carveHid.forEach((o) => { o.visible = true; });
    carveHid = [];
    clear(carveG);
    if (!c) return;
    for (const g of products.children) if (c.hide.includes(g.userData.placementId)) { g.visible = false; carveHid.push(g); }
    for (const id of c.hideObjects || []) for (const o of heldNodes({ kind: "object", id })) if (o.visible) { o.visible = false; carveHid.push(o); }
    for (const q of c.pieces) carveG.add(productBox(q));
    if (c.lid) {
      const g = new THREE.Group();
      g.add(...coverParts(c.lid.size_m[0], c.lid.size_m[1], c.lid.size_m[2], c.lid.slot, null));
      g.position.set(c.lid.xz[0], 0, c.lid.xz[1]);
      g.rotation.y = rotY("placement", c.lid.yaw);
      carveG.add(g);
    }
  };
  // ---- 장 끝 손잡이 끌기 ----
  const stretchAt = (e) => {
    if (!stretchG.visible || !stretchInfo || walk) return 0;
    setNdc(e);
    return ray.intersectObjects(stretchG.children.filter((h) => h.visible), true).find((x) => x.object.userData.stretch)?.object.userData.stretch || 0;
  };
  const stretchPoint = (e) => {
    setNdc(e);
    ringPlane.constant = -(stretchInfo?.y || 0);
    const v = ray.ray.intersectPlane(ringPlane, new THREE.Vector3());
    return v && [v.x, v.z];
  };
  const startStretch = (e, side) => {
    const p = stretchPoint(e);
    if (!p) return;
    // 깊이는 90° 돌려 놓은 장의 길이로 본다 (같은 계산을 쓴다)
    const axis = Math.abs(side) === 2 ? "d" : "w", i = stretchInfo;
    const base = axis === "d" ? { ...i, xz: [...i.xz], yaw: i.yaw + Math.PI / 2, w: i.d, d: i.w } : { ...i, xz: [...i.xz] };
    side = Math.sign(side);
    stretchDrag = { base, side, axis, off: reachOf(base, side, p) - base.w, now: null, moved: false };
    ctl.enabled = false;
    renderer.domElement.setPointerCapture?.(e.pointerId);
    renderer.domElement.style.cursor = axis === "d" ? "ns-resize" : "ew-resize";
    knobRimMat.color.setHex(RING_ON_HEX);
  };
  const moveStretch = (e) => {
    const p = stretchPoint(e), g = stretchDrag;
    if (!p) return;
    const r = handlers.stretch?.(g.base, g.side, reachOf(g.base, g.side, p) - g.off, e.altKey, g.axis);
    if (!r) return;
    g.now = r;
    g.moved = g.moved || Math.abs(r.w - g.base.w) > 1e-4;
    stretchInfo = { ...stretchInfo, xz: r.xz, [g.axis]: r.w };
    placeStretch();
    const box = el.getBoundingClientRect();
    ringChip.textContent = `${Math.round(r.w * 1000).toLocaleString("ko-KR")} mm`;
    ringChip.style.left = `${e.clientX - box.left + 16}px`;
    ringChip.style.top = `${e.clientY - box.top - 34}px`;
    ringChip.hidden = false;
    handlers.onStretchMove?.(g.base.id, r, g.axis);
  };
  const endStretch = () => {
    const g = stretchDrag;
    stretchDrag = null;
    ctl.enabled = true;
    ringChip.hidden = true;
    renderer.domElement.style.cursor = "";
    knobRimMat.color.setHex(RING_HEX);
    if (g.moved && g.now) handlers.onStretchEnd?.(g.base, g.now, g.axis);
  };
  let wallPick = false; // 벽 철거: 벽을 눌러 고르는 중
  let look = null; // 둘러보기에서 마우스를 못 잠글 때(터치 등) 끌어서 둘러보기
  const onDown = (e) => {
    if (walk) {
      e.stopPropagation(); // 둘러보기에서는 고르기·집어 들기·배치 없음
      stopGlide();
      walkHud.hidden = true;
      // 마우스를 잠그지 않는다: 누른 채 끄는 동안만, 마우스가 가는 쪽으로 천천히 돈다
      look = { x: e.clientX, y: e.clientY };
      renderer.domElement.setPointerCapture?.(e.pointerId);
      renderer.domElement.style.cursor = "grabbing";
      return;
    }
    if (e.button !== undefined && e.button !== 0) return;
    if (held) { down = { x: e.clientX, y: e.clientY, hit: null, p: null, held: true }; return; }
    const end = stretchAt(e);
    if (end) { e.preventDefault(); startStretch(e, end); return; }
    if (ringAt(e)) { e.preventDefault(); startRing(e); return; }
    const hit = pick(e);
    down = { x: e.clientX, y: e.clientY, hit, p: floorPoint(e) };
    if ((hit?.type === "placement" || hit?.type === "object") && handlers.canGrab?.(hit)) {
      // 고른 물건 위에서 누르고 끌면 잡혀서 따라온다 (잡아도 되는지는 canGrab이 정한다). 놓으면 그 자리에 내려놓는다
      e.preventDefault(); // 끄는 동안 화면 글자가 파랗게 잡히지 않게
      ctl.enabled = false;
      grabbing = { hit, p: down.p };
      renderer.domElement.setPointerCapture?.(e.pointerId);
    } else if (hit?.type === "placement" && handlers.canDrag?.(hit.id)) {
      // 제품 위에서 누르면 카메라 회전을 멈추고 끌기
      ctl.enabled = false;
      const g = products.children.find((c) => c.userData.placementId === hit.id);
      if (g) g.userData.dirty = true;
      dragging = { id: hit.id, start: down.p, orig: g ? [g.position.x, g.position.z] : down.p, group: g, moved: false, surface: g?.userData.surface };
      renderer.domElement.setPointerCapture?.(e.pointerId);
    }
  };
  const onMove = (e) => {
    if (walk) {
      if (look) {
        euler.setFromQuaternion(cam.quaternion);
        const perPx = lookRadPerPx(cam.fov, renderer.domElement.clientHeight); // 끈 만큼만 돈다
        euler.y -= (e.clientX - look.x) * perPx; // 마우스가 가는 쪽을 본다
        euler.x = Math.max(-1.4, Math.min(1.4, euler.x - (e.clientY - look.y) * perPx));
        cam.quaternion.setFromEuler(euler);
        look = { x: e.clientX, y: e.clientY };
      }
      return;
    }
    if (stretchDrag) { moveStretch(e); return; }
    if (ringDrag) { moveRing(e); return; }
    if (grabbing && !held && Math.hypot(e.clientX - down.x, e.clientY - down.y) > GRAB_PX) {
      const g = grabbing;
      grabbing = null;
      handlers.onGrab?.(g.hit, g.p);
      if (held) {
        held.byDrag = true;
        if (held.surface) held.grab = grabOffset(held.xz, planePoint({ clientX: down.x, clientY: down.y }, held.plane)); // 누른 자리 그대로 잡는다
      } else ctl.enabled = true;
    }
    if (held && !held.dropping && rotKey && held.surface !== "wall") { // E를 누른 채 마우스를 좌우로: 잡은 물건이 돈다 (Shift는 45°씩)
      held.spin = (held.spin ?? held.yaw) + e.movementX * SPIN_RAD_PER_PX;
      held.yaw = e.shiftKey ? Math.round(held.spin / SNAP_RAD) * SNAP_RAD : held.spin;
      held.turned = true;
      held.freeYaw = undefined;
      handlers.onHoldMove?.(held, held.xz);
      return;
    }
    if (held) held.spin = undefined;
    if (held && !held.dropping && held.surface === "wall") {
      // 벽걸이: 가리키는 벽 자리로. 위아래로 움직이면 높이가 바뀐다
      const p = floorPoint(e, 0.01);
      const m = handlers.hang?.(held, ray.ray.origin.toArray(), ray.ray.direction.toArray(), p);
      if (m) { held.xz = m.xz; held.yaw = m.yaw; held.y = m.base; handlers.onHoldMove?.(held, held.xz); }
      return;
    }
    if (held && !held.dropping) {
      // 들고 있으면 커서를 그대로 따라온다 (1 cm). 칸 단위로 뚝뚝 끊기면 손에 안 붙는다. 맞추는 건 벽·가전 붙기가 한다
      // 올려 두는 물건은 커서가 가리키는 가구 윗면을 따라간다 (식탁 위를 가리키면 식탁 위로)
      // 바닥에서 들고 책상 윗면을 가리키면 그 윗면으로 올라탄다 (전에는 바닥 평면만 따라가서 책상 뒤 바닥으로 갔다)
      const up = held.surface && held.surface !== "wall" ? surfaceHit(e, held.surface, held.id) : null;
      if (up && Math.abs(up.y - held.plane) > 0.01) { held.plane = up.y; held.grab = [0, 0]; }
      const q = held.surface ? planePoint(e, held.plane) : floorPoint(e, 0.01);
      if (q) {
        held.xz = [q[0] + held.grab[0], q[1] + held.grab[1]];
        // 벽·가전 옆에 가까이 가면 착 붙는다 (Alt를 누르고 있으면 붙지 않는다)
        // 벽에 붙으면서 돌아간 방향은 벽에서 떼면 원래대로 돌아온다 (지나가다 붙었다고 방향이 바뀐 채 남지 않게)
        const sn = !held.surface && !e.altKey && handlers.snap?.(held, held.xz, held.freeYaw ?? held.yaw);
        setCarve(sn?.carve || null);
        if (sn) { held.freeYaw ??= held.yaw; held.xz = sn.xz; held.yaw = sn.yaw; }
        else if (held.freeYaw !== undefined) { held.yaw = held.freeYaw; held.freeYaw = undefined; }
        handlers.onHoldMove?.(held, held.xz);
      }
      return;
    }
    const p = floorPoint(e, dragging ? 0.01 : 0.05);
    if (!p) return;
    if (dragging && dragging.start) {
      const c = dragging.surface ? surfacePoint(e, dragging.surface, dragging.id) || p
        : [dragging.orig[0] + p[0] - dragging.start[0], dragging.orig[1] + p[1] - dragging.start[1]];
      if (!dragging.moved && Math.hypot(e.clientX - down.x, e.clientY - down.y) > CLICK_PX) dragging.moved = true;
      if (dragging.moved) {
        const sn = !dragging.surface && !e.altKey && handlers.snap?.({ kind: "placement", id: dragging.id }, c, undefined);
        const at = sn ? sn.xz : c;
        setCarve(sn?.carve || null);
        dragging.yaw = sn ? sn.yaw : undefined;
        if (sn && dragging.group) dragging.group.rotation.y = rotY("placement", sn.yaw);
        dragging.group?.position.set(at[0], topY(dragging.surface, at, dragging.id) ?? 0, at[1]);
        handlers.onDragMove?.(dragging.id, at, dragging.yaw);
      }
      return;
    }
    if (!down) renderer.domElement.style.cursor = Math.abs(stretchAt(e)) === 2 ? "ns-resize" : stretchAt(e) ? "ew-resize" : ringAt(e) ? "grab" : "";
    handlers.onHover?.(pointFor(e) || p);
    if (handlers.wantHoverHit?.()) handlers.onHoverHit?.(hoverHit(e));
  };
  const onUp = (e) => {
    if (walk) { look = null; renderer.domElement.style.cursor = "grab"; return; }
    if (stretchDrag) { down = null; endStretch(); return; }
    if (ringDrag) { down = null; endRing(); return; }
    const d = down;
    down = null;
    ctl.enabled = true;
    grabbing = null;
    if (held?.byDrag) { handlers.onHoldClick?.(held); return; } // 끌던 물건은 놓는 자리에 내려놓는다
    if (dragging) {
      const g = dragging;
      dragging = null;
      if (g.moved) { handlers.onDragEnd?.(g.id, [g.group?.position.x ?? 0, g.group?.position.z ?? 0], g.surface === "product" ? g.group?.position.y : undefined, g.yaw); return; }
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
  // 잡고 있는 동안 휠을 굴리면 15°씩 돈다 (화면 확대는 잠시 쉰다)
  el.addEventListener("wheel", (e) => {
    if (!held || held.dropping) return;
    e.preventDefault(); e.stopPropagation();
    api.rotateHeld((e.deltaY > 0 ? 1 : -1) * WHEEL_RAD);
  }, { capture: true, passive: false });
  dom.addEventListener("mousedown", (e) => { if (e.button === 1) e.preventDefault(); }); // 휠 누름: 브라우저 자동 스크롤 대신 화면 이동
  dom.addEventListener("dragover", (e) => { e.preventDefault(); const p = floorPoint(e); if (p) handlers.onHover?.(p); });
  dom.addEventListener("drop", (e) => {
    e.preventDefault();
    const sku = e.dataTransfer.getData("text/sku");
    const p = (handlers.slots?.(sku) && cabPoint(e)) || floorPoint(e);
    if (sku && p) handlers.onDropSku?.(sku, p);
  });

  // ---------- 동선을 걷는 사람 ----------
  const angleTo = (a, b) => Math.atan2(Math.sin(b - a), Math.cos(b - a));
  function stepWalkers(dt) {
    if (walkersPaused) return;
    for (const w of walkers) {
      w.t += dt;
      const { s, moving, v, dir = 1 } = w.clock(w.t);
      const p = poseAt(w.path, s);
      w.node.position.set(p.xz[0], 0, p.xz[1]);
      // 몸은 발밑이 아니라 조금 앞(0.35 m)을 보고 0.3초쯤에 걸쳐 돈다 (모퉁이에서 휙 돌지 않게)
      // 끝에서 쉬는 동안에는 돌아갈 쪽으로 천천히 돌아선다
      const ahead = poseAt(w.path, Math.max(0, Math.min(w.len, s + dir * LOOK_AHEAD_M)));
      const far = Math.hypot(ahead.xz[0] - p.xz[0], ahead.xz[1] - p.xz[1]) > 0.05;
      const want = far ? Math.atan2(ahead.xz[0] - p.xz[0], ahead.xz[1] - p.xz[1]) : w.heading;
      const turn = angleTo(w.heading, want) * Math.min(1, dt / TURN_S), cap = MAX_TURN_RAD_S * dt;
      w.heading += Math.max(-cap, Math.min(cap, turn));
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
        shell = null;
        openWalls(last.list, true); // 창 자리 벽을 뚫고 그림자용 벽을 만든다 (dressRoom이 창 두께를 바꾸기 전에)
        const mine = model;
        walls.push(...dressRoom(model, finishSet, () => alive && model === mine, (made) => {
          walls = walls.filter((w) => !w.userData.gone);
          walls.push(...made);
          roomEnvDirty = true;
        }));
        furnish(model, () => alive && model === mine, (id) => objectCats[id], (id) => objectColors[id], (id) => objectPartColors[id]);
        scene.add(model);
        new THREE.Box3().setFromObject(model).getCenter(center);
        if (!framed) { frame(keepCam); framed = true; }
        applySun();
      }, undefined, () => toast("3D 파일을 불러오지 못했습니다", true));
    },
    /** 놓은 제품을 다시 그린다. 끌고 있는 중이면 건너뛴다. */
    setPlacements(list, selectedId) {
      last = { ...last, list, selectedId };
      roomEnvDirty = true;
      openWalls(list);
      if (dragging || (held?.kind === "placement" && !held.dropping)) return;
      if (!last.ghost) setCarve(null); // 놓았거나 그만뒀으면 미리 보던 칸은 지운다
      // 바뀐 것만 다시 만든다. 놓을 때마다 전부 새로 만들면 가구가 많을수록 버벅인다
      const keep = new Map();
      for (const c of products.children) if (c.userData.key && !c.userData.dirty) keep.set(c.userData.key, c);
      const next = [];
      for (const p of list) {
        if (!p.size_m) continue;
        const selected = p.placement_id === selectedId;
        const key = JSON.stringify([p.placement_id, p.sku, p.center_xz, p.yaw_rad, p.size_m, p.verdict, p.hex, p.part_colors, p.top_hex, selected, templates.has(modelKey(p)), p.base_m || 0,
          p.slot ? [p.slot, templates.has(`decor:${p.slot.look}`)] : 0]);
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
    setNeed(pts, baseY = 0) {
      clear(need);
      need.position.y = baseY; // 가구 위에 올려 둔 것은 그 윗면에 그린다
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
      if (!res?.size_m) { clear(ghost); setCarve(null); return; }
      setCarve(res.carve || null);
      // 카메라 바로 앞(화면 아래 끝)에 오면 반투명 상자가 화면을 하얗게 덮는다 → 그때는 그리지 않는다
      const [gx, gz] = res.pose.center_xz;
      const reach = Math.hypot(res.size_m[0], res.size_m[2]) / 2 + GHOST_NEAR_M;
      ghost.visible = walk || Math.hypot(cam.position.x - gx, cam.position.z - gz) >= reach;
      // 마우스를 따라갈 때는 같은 모양이면 자리·방향만 옮긴다 (매번 새로 만들면 버벅인다)
      const key = JSON.stringify([res.sku, res.size_m, res.verdict, res.hex, templates.has(modelKey(res))]);
      const cur = ghost.children[0];
      // 올려 두는 가전은 서버 답을 기다리지 않고 지금 가리키는 윗면 높이로 바로 올린다
      const gy = res.surface ? topY(res.surface, [gx, gz], null) : res.base_m || 0;
      if (cur && cur.userData.ghostKey === key) {
        cur.position.set(gx, gy, gz);
        cur.rotation.y = -((res.pose.yaw_rad ?? Math.PI / 2) - Math.PI / 2);
        return;
      }
      clear(ghost);
      ghost.add(productBox({ center_xz: res.pose.center_xz, yaw_rad: res.pose.yaw_rad, size_m: res.size_m, verdict: res.verdict, hex: res.hex, sku: res.sku, base_m: gy }, { preview: true }));
      ghost.children[0].userData.ghostKey = key;
    },
    /** 끄는 동안 판정 색만 바꾼다 */
    setDragVerdict(id, verdict) {
      const g = products.children.find((c) => c.userData.placementId === id);
      if (!g) return;
      g.userData.dirty = true; // 색을 바꿨으니 다음 그리기에서 새로 만든다
      const hex = VERDICT_HEX[verdict] ?? VERDICT_HEX.unknown;
      g.children.forEach((c) => {
        if ((c.isLineSegments && !c.userData.dim) || c.userData.verdictPlate) c.material.color.setHex(hex);
        if (c.userData.verdictPlate) c.visible = true; // 옮기는 동안에는 들어가는지 바닥 색으로 보여 준다
      });
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
          walkers.push({ node, mixer, walk, idle, path: smooth, len, moving: false, heading: poseAt(smooth, 0.3).heading, stepRate,
            clock: routeClock(len, { speed: WALK_SPEED, pause: 1.6, ease: WALK_EASE_S, roundTrip: true }), t: -i * 1.2 });
        });
      });
    },
    /** 동선 출발 자리 고르기: 마우스를 따라오는 사람. null이면 숨긴다 */
    personFollow(xz) {
      if (!xz) { starter.visible = false; return; }
      starter.position.set(xz[0], 0, xz[1]);
      starter.visible = true;
      if (starterAsked) return;
      starterAsked = true;
      loadAsset(PERSON_URL).then((g) => {
        if (!g || !alive) return;
        const node = cloneSkinned(g.scene);
        node.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
        const idle = g.animations.find((a) => a.name === "idle");
        if (idle) { starterMixer = new THREE.AnimationMixer(node); starterMixer.clipAction(idle).play(); }
        starter.add(node);
      });
    },
    starterInfo() { return { visible: starter.visible, loaded: starter.children.length > 1, pos: [+starter.position.x.toFixed(3), +starter.position.z.toFixed(3)] }; },
    /** 걷는 사람 멈추기/다시 걷기 (화면 캡처용) */
    pauseWalkers(on = true) { walkersPaused = !!on; },
    /** 걷는 사람 (E2E 확인용) */
    walkersInfo() { return walkers.map((w) => ({ pos: [+w.node.position.x.toFixed(3), +w.node.position.z.toFixed(3)], moving: w.moving })); },
    routerInfo() { return { visible: routerG.visible && routerG.children.length > 0, pos: [+routerG.position.x.toFixed(3), +routerG.position.z.toFixed(3)], yaw: +(-routerG.rotation.y).toFixed(3) }; },
    /** 평면 오버레이(SVG, 단위 m)를 바닥 텍스처로 깐다. svg가 비면 끈다. */
    setOverlay(inner, box) {
      const turn = ++overlayTurn; // 그림은 늦게 뜬다: 그 사이 지우거나 새로 그렸으면 늦게 온 것은 버린다 (끈 동선이 다시 뜨던 문제)
      if (!inner || !box) { overlay.visible = false; return; }
      const [x0, y0, w, h] = box;
      const px = 1024, k = px / Math.max(w, h);
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.round(w * k)}" height="${Math.round(h * k)}" viewBox="${x0} ${y0} ${w} ${h}"><style>${OVERLAY_CSS}</style>${inner}</svg>`;
      const img = new Image();
      img.onload = () => {
        if (turn !== overlayTurn) return;
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
    /** 지금 보이는 판정 색 바닥 판 수 (점검용) */
    /** 끄는 동안 미리 보이는 칸 조각 수 (점검용) */
    carved: () => ({ pieces: carveG.children.length, hidden: carveHid.length }),
    shownPlates() { let n = 0; products.traverse((o) => { if (o.userData.verdictPlate && o.visible) n += 1; }); return n; },
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
        lift: 0, dropping: false, y: nodes[0].position.y,
        // 윗면에 올린 물건은 잡은 높이의 평면을 따라간다 (끌어서 잡으면 누른 자리 차이는 onMove에서 잰다)
        plane: item.surface ? nodes[0].position.y : 0,
        grab: item.surface ? [0, 0] : grabOffset(item.xz, grabPoint) };
      return true; // 50 cm 격자는 안 띄운다: 1 cm로 따라오는데 칸이 보이면 칸에 맞춰야 할 것 같고 방 밖까지 깔려 어지럽다
    },
    /** 회전 고리를 고른 물건 둘레에 깐다. info = {kind, id, xz, yaw, r, y} 또는 null */
    setRotateRing(info) {
      if (ringDrag) return; // 돌리는 중에는 그대로
      const same = ringInfo && info && ringInfo.r === info.r;
      ringInfo = info || null;
      rotRing.visible = !!info && !walk;
      if (!info) return;
      if (!same) buildRing(info.r);
      rotRing.position.set(info.xz[0], (info.y || 0) + 0.012, info.xz[1]);
      rotRing.getObjectByName("arm").rotation.y = rotY(info.kind, info.yaw);
    },
    ringDragging: () => !!ringDrag,
    /** 장 끝 손잡이 {id, xz, yaw, w, d, y, deep}. null이면 숨긴다. deep이면 앞뒤 손잡이도 낸다 */
    setStretch(info) {
      if (stretchDrag) return; // 늘리는 중에는 그대로
      stretchInfo = info || null;
      stretchG.visible = !!info && !walk;
      if (!info) return;
      if (!stretchG.children.length) buildStretch();
      placeStretch();
    },
    stretching: () => !!stretchDrag,
    held: () => held && { kind: held.kind, id: held.id, xz: [...held.xz], yaw: held.yaw, surface: held.surface, y: held.nodes[0]?.node.position.y ?? 0 },
    /** E를 누르고 있는지 (잡은 물건을 마우스로 돌리는 중) */
    spinKey(on) { rotKey = !!on && !!held; },
    moveHeld(dx, dz) { if (held && held.surface !== "wall") { held.xz = [held.xz[0] + dx, held.xz[1] + dz]; handlers.onHoldMove?.(held, held.xz); } },
    rotateHeld(dyaw) { if (held && held.surface !== "wall") { held.yaw += dyaw; held.turned = true; held.freeYaw = undefined; handlers.onHoldMove?.(held, held.xz); } }, // 직접 돌렸으면 벽이 다시 돌려놓지 않는다
    /** 내려놓기: 마지막 자리를 돌려준다 (저장은 부르는 쪽이) */
    dropHold() {
      if (!held) return null;
      const out = { kind: held.kind, id: held.id, xz: [...held.xz], yaw: held.yaw, turned: !!held.turned, baseY: held.surface === "wall" ? held.y : held.surface === "product" ? productTopY(held.xz, held.id) : undefined };
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
      setCarve(null);
      if (grid) grid.visible = false;
    },
    /** 들고 있는 물건 바닥 판 색 (판정) */
    holdVerdict(verdict) {
      if (held?.kind === "placement") api.setDragVerdict(held.id, verdict);
    },
    /** 키보드 카메라: 화면 기준 앞뒤·좌우로 이동, 대상 둘레로 돌기 */
    /** 화면 움직이는 키를 눌렀다·뗐다 (w a s d q e). 누르고 있는 동안 부드럽게 움직인다 */
    camKey(k, on) { camKeys = { ...camKeys, [k]: !!on }; if (on) camGlide = null; },
    camKeysOff() { camKeys = {}; },
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
    /** 지금 시점 (서버의 Blender가 같은 자리에서 그릴 때 쓴다). fov는 세로 화각(도) */
    cameraPose() {
      const r3 = (v) => v.toArray().map((n) => Math.round(n * 1000) / 1000);
      const dir = cam.getWorldDirection(new THREE.Vector3());
      return { pos: r3(cam.position), target: r3(cam.position.clone().add(dir)), fov: cam.fov };
    },
    /** 실사로 보기: 지금 시점을 1536x1024로 찍고, 같은 시점에서 LG 제품만 흰색인 마스크도 찍는다.
     *  판정 판·테두리·미리 보기·사람 같은 표시는 빼고 찍는다.
     *  화면에 보이는 LG 제품마다 자리(0~1 상자)도 같이 준다: 서버가 그 제품의 LGE.COM 사진을 이미지 AI에 참고로 보낸다 */
    snapshot(W = 1536, H = 1024) {
      const size = renderer.getSize(new THREE.Vector2()), pr = renderer.getPixelRatio(), aspect = cam.aspect;
      const hidden = [];
      const hide = (o) => { if (o?.visible) { o.visible = false; hidden.push(o); } };
      [overlay, ghost, need, walkersG, starter, grid].forEach(hide);
      products.traverse((o) => { if (o.userData.verdictPlate || o.isLineSegments) hide(o); });
      renderer.setPixelRatio(1); composer.setPixelRatio(1);
      renderer.setSize(W, H, false); composer.setSize(W, H);
      cam.aspect = W / H; cam.updateProjectionMatrix();
      let image, mask, boxes = [];
      try {
        composer.render();
        image = renderer.domElement.toDataURL("image/png");
        boxes = productBoxes();
        const black = new THREE.MeshBasicMaterial({ color: 0x000000 }), white = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const lgOf = (o) => { for (let q = o; q && q !== scene; q = q.parent) if (q.parent === products) return !!q.userData.sku && !q.userData.sku.startsWith("decor:"); return false; };
        const swapped = [];
        scene.traverse((o) => {
          if (!o.visible) return;
          if (o.isMesh) {
            const mats = [].concat(o.material);
            // 비쳐 보이는 벽(카메라 쪽 컷어웨이)·유리는 마스크에서 가리지 않는다 (뒤의 제품이 보이니까)
            if (!lgOf(o) && mats.every((m) => m.transparent && (m.opacity ?? 1) < 0.9)) { hide(o); return; }
            swapped.push([o, o.material]); o.material = lgOf(o) ? white : black;
          } else if (o.isLine || o.isPoints || o.isSprite) hide(o);
        });
        const bg = scene.background, tm = renderer.toneMapping;
        scene.background = new THREE.Color(0x000000); renderer.toneMapping = THREE.NoToneMapping;
        renderer.render(scene, cam);
        mask = renderer.domElement.toDataURL("image/png");
        swapped.forEach(([o, m]) => (o.material = m));
        scene.background = bg; renderer.toneMapping = tm;
        black.dispose(); white.dispose();
      } finally {
        hidden.forEach((o) => (o.visible = true));
        renderer.setPixelRatio(pr); composer.setPixelRatio(pr);
        cam.aspect = aspect; cam.updateProjectionMatrix();
        renderer.setSize(size.x, size.y); composer.setSize(size.x, size.y);
      }
      return { image, mask, products: boxes };
    },
    /** 첫 화면 카드에 쓰는 작은 미리보기 (지금 시점, JPEG). 표시용 선·사람은 빼고 찍는다 */
    thumb(W = 480, H = 320) {
      const size = renderer.getSize(new THREE.Vector2()), pr = renderer.getPixelRatio(), aspect = cam.aspect;
      const hidden = [];
      [overlay, ghost, need, walkersG, starter, grid].forEach((o) => { if (o?.visible) { o.visible = false; hidden.push(o); } });
      renderer.setPixelRatio(1); composer.setPixelRatio(1);
      renderer.setSize(W, H, false); composer.setSize(W, H);
      cam.aspect = W / H; cam.updateProjectionMatrix();
      try {
        composer.render();
        return renderer.domElement.toDataURL("image/jpeg", 0.8);
      } finally {
        hidden.forEach((o) => (o.visible = true));
        renderer.setPixelRatio(pr); composer.setPixelRatio(pr);
        cam.aspect = aspect; cam.updateProjectionMatrix();
        renderer.setSize(size.x, size.y); composer.setSize(size.x, size.y);
      }
    },
    /** 스캔 가구 종류 (3D 파일에 종류가 없을 때 씀). load 전에 부른다 */
    /** 3D에 입힐 실제 벽지·바닥재 { wall?, floor? }. 다음 load부터 반영 */
    setFinishes(f) { finishSet = f || {}; },
    setObjects(objects, colors, partColors) { objectCats = Object.fromEntries((objects || []).map((o) => [o.object_id, o.category])); objectColors = colors || {}; objectPartColors = partColors || {}; },
    /** 화면에 그린 것 세기 (E2E 확인용) */
    stats() {
      let furniture = 0;
      model?.traverse((o) => { if (o.isMesh && o.userData.shared && o.userData.kind === "object") furniture++; });
      return { furniture, products: products.children.length };
    },
    /** 평면 좌표 [x, z] 쪽으로 시점을 부드럽게 옮긴다 (보는 각도·거리는 그대로) */
    /** 벽 고르기 켜기/끄기 (철거는 붉게 물들이고, 길이 재기는 tint = false로 그대로 둔다). 켜면 클릭이 벽({type:"wall", id})을 맞히고, 벽 위에서 커서가 바뀐다 */
    setWallPick(on, tint = true) {
      wallPick = !!on;
      dom.style.cursor = on ? "crosshair" : "";
      model?.traverse((o) => {
        if (!o.isMesh || o.userData?.kind !== "wall") return;
        if (on && tint && !o.userData.pickMat) { o.userData.pickMat = o.material; o.material = o.material.clone(); o.material.emissive?.set("#A50034"); o.material.emissiveIntensity = 0.18; }
        if (!on && o.userData.pickMat) { o.material.dispose(); o.material = o.userData.pickMat; delete o.userData.pickMat; }
      });
    },
    /** 벽 발치에 줄자 선을 긋는다. seg = {start: [x, z], end: [x, z]}, 없으면 지운다 */
    setTape(seg) {
      tapeG.clear();
      tapeG.visible = !!seg;
      if (!seg) return;
      const [ax, az] = seg.start, [bx, bz] = seg.end, len = Math.hypot(bx - ax, bz - az);
      const bar = (l, w) => { const m = new THREE.Mesh(new THREE.BoxGeometry(l, 0.012, w), tapeMat); m.renderOrder = 50; return m; };
      const line = bar(len, 0.035);
      tapeG.add(line);
      for (const x of [-len / 2, len / 2]) { const tick = bar(0.035, 0.3); tick.position.x = x; tapeG.add(tick); } // 양 끝 눈금
      tapeG.position.set((ax + bx) / 2, 0.02, (az + bz) / 2);
      tapeG.rotation.y = -Math.atan2(bz - az, bx - ax);
    },
    tapeShown: () => tapeG.visible,
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
    /** 걸어 보기에서 길(평면 점들)을 따라 걸어가 yaw 쪽을 보고 선다. 다 오면 done. 길이 없으면 그 자리에서 돌기만 */
    walkTo(path, yaw, done, pitch = GLIDE_PITCH) {
      if (!walk) return false;
      if (plc.isLocked) plc.unlock();
      const pts = path?.length ? path : [[cam.position.x, cam.position.z]];
      walk.glide = { path: pts, len: pathLength(pts), s: 0, yaw, pitch, done };
      walk.keys = {};
      walkHud.hidden = true;
      return true;
    },
    /** 걸어 보기에서 그 자리에 바로 선다 (처음 들어갈 때) */
    walkPlace(pos, yaw, pitch = GLIDE_PITCH) {
      if (!walk) return false;
      walk.glide = null;
      cam.position.set(pos[0], EYE_H, pos[1]);
      cam.quaternion.setFromEuler(new THREE.Euler(pitch, yaw, 0, "YXZ"));
      return true;
    },
    walkStop() { stopGlide(); },
    /** 지금 선 자리 (E2E 확인용) */
    /** 그리기 상태 (점검용): 곱게 그린 한 장에 걸리는 시간(ms), 가볍게 그린 장 수 */
    renderInfo() { return { fullMs: Math.round(fullMs), liteFrames }; },
    /** 느린 PC에서 움직일 때 쓰는 가벼운 그리기를 계속 켜 둔다 (점검용) */
    setLite(on) { forceLite = !!on; },
    walkInfo() {
      if (!walk) return null;
      euler.setFromQuaternion(cam.quaternion);
      return { pos: cam.position.toArray().map((v) => +v.toFixed(3)), yaw: +euler.y.toFixed(3), locked: plc.isLocked, gliding: !!walk.glide,
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
    dispose() { alive = false; clearWalkers(); ro.disconnect(); plc.dispose(); document.removeEventListener("keydown", onWalkKey, true); document.removeEventListener("keyup", onWalkKey, true); el.removeEventListener("pointerdown", onDown, { capture: true }); envTex.dispose(); roomEnv?.dispose(); roomCube?.renderTarget.dispose(); myGloss.forEach((m) => m.dispose()); pmrem.dispose(); gtao.dispose(); composer.dispose(); renderer.dispose(); el.innerHTML = ""; },
  };
  el.viewer = api;
  return api;
}
