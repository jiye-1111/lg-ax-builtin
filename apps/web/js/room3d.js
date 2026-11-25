// 스캔한 방 다듬기: 마루 바닥, 걸레받이, 창 유리·창틀, 문틀 + 스캔 가구를 Blender 모델로 바꾸기
// 방 glb(glb.py)는 노드마다 단위 상자를 scale로 늘린 모양이다. 노드 scale = (폭, 높이, 깊이).
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { finishTexture, tileMeters, BUMP, ROUGH } from "./finishes.js";
import { partsOf, partColours, lookOf } from "./furncolors.js";

const FURN_DIR = "models/furniture/";
const PLANK_M = 2.4;          // 바닥 무늬 한 장이 덮는 길이 (m)
const BASEBOARD_H = 0.08;
const FRAME_W = 0.05;

// ---------- 스캔 가구 모델 ----------
const loader = new GLTFLoader();
let furnIndex = null;
const furnTemplates = new Map();
/** 가구 모델 한 벌 (models/furniture/<cat>.glb + 기준 크기). 없으면 null */
export function furnitureTemplate(cat) {
  furnIndex ??= fetch(FURN_DIR + "index.json").then((r) => (r.ok ? r.json() : { models: {} })).catch(() => ({ models: {} }));
  if (!furnTemplates.has(cat)) {
    furnTemplates.set(cat, furnIndex.then((idx) => {
      const e = idx.models?.[cat];
      if (!e) return null;
      return loader.loadAsync(FURN_DIR + e.file).then((g) => {
        g.scene.traverse((o) => { if (o.isMesh) dressMaterial(o.material, o.material.userData.tex); });
        return { scene: g.scene, ref: e.ref_m };
      }, () => null);
    }));
  }
  return furnTemplates.get(cat);
}

/** 부품별 rig(s/p/e)로 기준 크기 모델을 스캔 크기 size(Vector3)에 맞춘다. 바닥 가운데 원점. */
export function fitFurniture(tmpl, ref, size) {
  const g = tmpl.clone(true);
  const R = [ref.w, ref.h, ref.d], T = [size.x, size.y, size.z], AX = ["x", "y", "z"];
  g.traverse((o) => {
    if (!o.isMesh) return;
    const rig = o.userData.rig || "sss";
    const c = o.position.clone();
    AX.forEach((ax, i) => {
      const k = T[i] / R[i];
      if (rig[i] === "s") { o.position[ax] = c[ax] * k; o.scale[ax] = k; }
      else if (rig[i] === "p") o.position[ax] = c[ax] * k;
      else if (i === 1) o.position.y = c.y < R[1] / 2 ? c.y : T[1] - (R[1] - c.y); // 높이: 바닥 또는 위 모서리 기준
      else o.position[ax] = (Math.sign(c[ax]) || 1) * (T[i] / 2 - (R[i] / 2 - Math.abs(c[ax])));
    });
    o.castShadow = true;
    o.receiveShadow = true;
    o.userData.shared = true;
  });
  return g;
}

// ---------- 가구 무늬: 나뭇결과 천 짜임 (작은 그림 두 장을 모든 가구가 같이 쓴다) ----------
let woodTex = null, clothTex = null;
function canvasTexture(size, draw, colour) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  draw(cv.getContext("2d"), size);
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (colour) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
/** 밝은 회색 나뭇결: 재질 색에 곱해져서 어떤 나무 색에도 쓴다. 결은 가로(U)로 흐른다 */
function woodTexture() {
  return (woodTex ??= canvasTexture(512, (g, n) => {
    g.fillStyle = "#f4f4f4";
    g.fillRect(0, 0, n, n);
    let seed = 11;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 150; i++) { // 가는 결
      const y = rnd() * n, a = 0.03 + rnd() * 0.09, wob = 1 + rnd() * 5, ph = rnd() * 6.28;
      g.strokeStyle = `rgba(70,50,30,${a})`;
      g.lineWidth = 0.6 + rnd() * 1.6;
      g.beginPath();
      for (let x = 0; x <= n; x += 16) g.lineTo(x, y + Math.sin((x / n) * 6.283 + ph) * wob);
      g.stroke();
    }
    for (let i = 0; i < 9; i++) { // 넓은 띠: 판재마다 조금씩 다른 밝기
      const y = rnd() * n, h = 18 + rnd() * 50;
      g.fillStyle = rnd() > 0.5 ? "rgba(255,255,255,0.10)" : "rgba(60,40,20,0.05)";
      g.fillRect(0, y, n, h);
      if (y + h > n) g.fillRect(0, y - n, n, h); // 위아래가 이어지게
    }
  }, true));
}
/** 천 짜임: 씨줄·날줄이 엇갈린 옅은 무늬. 재질 색에 곱해진다 (울퉁불퉁 효과보다 가볍고 멀리서도 자글거리지 않는다) */
function clothTexture() {
  return (clothTex ??= canvasTexture(128, (g, n) => {
    g.fillStyle = "#f6f6f6";
    g.fillRect(0, 0, n, n);
    const c = 8;
    for (let y = 0; y < n; y += c) for (let x = 0; x < n; x += c) {
      const over = ((x + y) / c) % 2 === 0;
      const gr = over ? g.createLinearGradient(x, 0, x + c, 0) : g.createLinearGradient(0, y, 0, y + c);
      gr.addColorStop(0, "rgba(40,36,30,0.16)"); gr.addColorStop(0.5, over ? "rgba(255,255,255,0.10)" : "rgba(40,36,30,0.03)"); gr.addColorStop(1, "rgba(40,36,30,0.16)");
      g.fillStyle = gr;
      g.fillRect(x, y, c, c);
    }
  }, true));
}
/** 재질에 무늬를 입힌다. tex: "wood" 나뭇결 · "fabric" 천 짜임 · 그 밖은 민무늬. metal: 금속 느낌 */
export function dressMaterial(m, tex, metal = null) {
  m.userData.base ??= { roughness: m.roughness, metalness: m.metalness };
  const map = tex === "wood" ? woodTexture() : tex === "fabric" ? clothTexture() : null;
  if (m.map !== map) { m.map = map; m.needsUpdate = true; }
  if (metal !== null) {
    m.metalness = metal ? 0.9 : Math.min(m.userData.base.metalness, 0.3);
    m.roughness = metal ? 0.3 : m.userData.base.metalness > 0.5 ? 0.5 : m.userData.base.roughness;
  }
}

/** 고른 색을 가구의 부위별로 입힌다 (천·문짝·상판·다리 등). 재질은 가구마다 따로 쓴다.
 *  hex = 대표 부위 색, partColors = {부위: hex}. 나무 색을 고르면 나뭇결도 같이 입는다 */
export function tintFurniture(group, look, hex, partColors = null, topHex = null) {
  const chosen = partColours(look, hex, partColors, topHex);
  const todo = partsOf(look).filter((q) => chosen[q.key]);
  if (!todo.length) return;
  group.traverse((o) => {
    if (!o.isMesh) return;
    const q = todo.find((t) => t.mats.includes(o.material.name));
    if (!q) return;
    if (!o.userData.ownMaterial) { o.material = o.material.clone(); o.userData.ownMaterial = true; }
    const c = q.colours.find((x) => x.hex === chosen[q.key]);
    o.material.color.set(chosen[q.key]);
    // 팔레트에 없는 예전 색은 무늬를 그대로 둔다
    if (c) dressMaterial(o.material, c.tex || (o.material.userData.tex === "fabric" ? "fabric" : null), !!c.metal);
  });
}

/** 스캔 가구 상자를 모델로 바꾼다. 상자는 안 보이게 두고 고르기(raycast)에만 쓴다. */
export function furnish(model, isCurrent, categoryOf = () => null, colorOf = () => null, partColorsOf = () => null) {
  const boxes = [];
  model.traverse((o) => { if (o.isMesh && o.userData?.kind === "object") boxes.push(o); });
  for (const box of boxes) {
    // 예전에 만든 집의 3D 파일에는 종류가 없다 → room.json의 종류로 채운다
    const cat = box.userData.category || categoryOf(box.name);
    if (!cat) continue;
    // 허리 높이 수납장은 주방 하부장이다: 상판 있는 하부장 모델로 그린다
    const look = lookOf(cat, box.scale.y);
    furnitureTemplate(look).then((t) => {
      if (!t || !isCurrent()) return;
      const fitted = fitFurniture(t.scene, t.ref, box.scale);
      fitted.position.set(box.position.x, box.position.y - box.scale.y / 2, box.position.z);
      fitted.quaternion.copy(box.quaternion);
      tintFurniture(fitted, look, colorOf(box.name), partColorsOf(box.name));
      fitted.traverse((o) => { if (o.isMesh) { o.userData.kind = "object"; o.name = box.name; } });
      fitted.userData.objectId = box.name; // 집어 들 때 상자와 같이 움직인다
      box.material.visible = false;   // 그리지는 않고 고르기에만
      box.castShadow = false;
      (box.parent || model).add(fitted);
    });
  }
}

// ---------- 방 다듬기 ----------
let plankTex = null;
function plankTexture() {
  if (plankTex) return plankTex;
  // 밝은 회색조 마루 무늬: 재질 색(마감재에서 고른 바닥 색)이 곱해져 색이 정해진다
  const cv = document.createElement("canvas");
  cv.width = cv.height = 1024;
  const g = cv.getContext("2d");
  const rows = 13, rowH = 1024 / rows;
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let r = 0; r < rows; r++) {
    let x = -rnd() * 400;
    while (x < 1024) {
      const len = 300 + rnd() * 260, v = 215 + rnd() * 40;
      g.fillStyle = `rgb(${v},${v - 6},${v - 14})`;
      g.fillRect(x, r * rowH, len, rowH);
      for (let k = 0; k < 6; k++) { // 나뭇결
        g.strokeStyle = `rgba(90,60,30,${0.04 + rnd() * 0.05})`;
        g.beginPath();
        const y = r * rowH + rnd() * rowH;
        g.moveTo(x, y);
        g.bezierCurveTo(x + len * 0.3, y + (rnd() - 0.5) * 8, x + len * 0.7, y + (rnd() - 0.5) * 8, x + len, y);
        g.stroke();
      }
      g.fillStyle = "rgba(60,40,20,.35)";
      g.fillRect(x, r * rowH, 2, rowH);       // 판 이음
      x += len;
    }
    g.fillStyle = "rgba(60,40,20,.3)";
    g.fillRect(0, r * rowH, 1024, 2);
  }
  plankTex = new THREE.CanvasTexture(cv);
  plankTex.colorSpace = THREE.SRGBColorSpace;
  plankTex.wrapS = plankTex.wrapT = THREE.RepeatWrapping;
  plankTex.anisotropy = 8;
  return plankTex;
}

const worldBox = (src, w, h, d, mat, y) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.copy(src.position);
  if (y !== undefined) m.position.y = y;
  m.quaternion.copy(src.quaternion);
  m.castShadow = false;
  m.receiveShadow = true;
  return m;
};

// ---------- 실제 채광용 그림자 껍데기 ----------
// 화면에는 안 그리고(colorWrite 끔) 해 그림자만 낸다: 창 자리를 뺀 벽 조각 + 천장.
// 그래서 해는 창으로만 들어오고, 컷어웨이로 흐리게 한 앞벽도 그림자는 그대로 낸다.
const SHADOW_ONLY = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false });

/** 벽 하나(단위 상자 × scale)에서 창·문 구멍을 뺀 조각들 [u0, u1, v0, v1] (벽 가운데 기준, m) */
export function wallPieces(L, H, holes) {
  const out = [], hs = [...holes].sort((a, b) => a[0] - b[0]);
  let cur = -L / 2;
  for (const [ua, ub, va, vb] of hs) {
    const a = Math.max(cur, Math.max(-L / 2, ua)), b = Math.min(L / 2, ub);
    if (b <= a) continue;
    if (a > cur + 1e-3) out.push([cur, a, -H / 2, H / 2]);
    if (va > -H / 2 + 1e-3) out.push([a, b, -H / 2, Math.min(va, H / 2)]);
    if (vb < H / 2 - 1e-3) out.push([a, b, Math.max(vb, -H / 2), H / 2]);
    cur = b;
  }
  if (cur < L / 2 - 1e-3) out.push([cur, L / 2, -H / 2, H / 2]);
  return out;
}

/** 조각들을 벽 한 장의 모양으로 합친다 (벽은 1×1×1 상자를 늘린 것이라 0~1 좌표로 만든다). */
function piecesGeometry(pieces, L, H) {
  const pos = [], nor = [], uv = [];
  for (const [u0, u1, v0, v1] of pieces) {
    const b = new THREE.BoxGeometry((u1 - u0) / L, (v1 - v0) / H, 1).toNonIndexed();
    b.translate((u0 + u1) / 2 / L, (v0 + v1) / 2 / H, 0);
    const P = b.attributes.position.array;
    pos.push(...P);
    nor.push(...b.attributes.normal.array);
    for (let i = 0; i < P.length; i += 3) uv.push(P[i] + 0.5, P[i + 1] + 0.5); // 벽지 무늬가 조각마다 끊기지 않게
    b.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  return g;
}

/** 벽 기준으로 본 창 자리들. spots: [{x, y, z, w, h}] 창 가운데와 크기 (m) */
function holesOn(w, spots, inv, p) {
  const L = w.scale.x, T = w.scale.z, holes = [];
  inv.compose(w.position, w.quaternion, ONE).invert();
  for (const s of spots) {
    p.set(s.x, s.y, s.z).applyMatrix4(inv);
    if (Math.abs(p.z) > T / 2 + 0.06 || Math.abs(p.x) > L / 2 + s.w / 2) continue;
    holes.push([p.x - s.w / 2, p.x + s.w / 2, p.y - s.h / 2, p.y + s.h / 2]);
  }
  return holes;
}
const ONE = new THREE.Vector3(1, 1, 1);
const spotsOf = (meshes) => meshes.map((o) => ({ x: o.position.x, y: o.position.y, z: o.position.z, w: o.scale.x, h: o.scale.y }));

// 창밖: 유리 너머로 보이는 하늘빛. 방 안쪽에서만 보인다 (밖에서 내려다볼 때는 안 보이게 한쪽 면만)
let skyTex = null;
function skyMaterial() {
  if (!skyTex) {
    const c = document.createElement("canvas");
    c.width = 4; c.height = 128;
    const x = c.getContext("2d"), g = x.createLinearGradient(0, 0, 0, 128);
    g.addColorStop(0, "#bcd6ec"); g.addColorStop(0.62, "#e4eef5"); g.addColorStop(1, "#f6f3ec");
    x.fillStyle = g; x.fillRect(0, 0, 4, 128);
    skyTex = new THREE.CanvasTexture(c);
    skyTex.colorSpace = THREE.SRGBColorSpace;
  }
  return new THREE.MeshBasicMaterial({ map: skyTex, toneMapped: false });
}

/** 창이 있는 자리의 벽을 뚫고 그 너머에 창밖 하늘빛을 둔다: 유리가 비쳐 보인다.
 *  extra = 새로 단 창·유리문 자리 (바뀔 때마다 다시 부른다) */
export function cutWalls(model, extra = []) {
  const walls = [], wins = [];
  model.traverse((o) => {
    if (!o.isMesh) return;
    if (o.userData?.kind === "wall") walls.push(o);
    else if (o.userData?.kind === "window" && o.visible) wins.push(o);
  });
  const old = model.getObjectByName("outside");
  if (old) { old.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); }); model.remove(old); }
  const outside = new THREE.Group();
  outside.name = "outside";
  const mid = new THREE.Vector3();
  walls.forEach((w) => mid.add(w.position));
  mid.divideScalar(walls.length || 1);
  const spots = [...spotsOf(wins), ...extra], inv = new THREE.Matrix4(), p = new THREE.Vector3();
  for (const w of walls) {
    const holes = holesOn(w, spots, inv, p);
    const out = -Math.sign(p.copy(mid).applyMatrix4(inv).z) || 1; // 방 가운데의 반대쪽이 밖
    for (const [u0, u1, v0, v1] of holes) {
      const sky = new THREE.Mesh(new THREE.PlaneGeometry(u1 - u0, v1 - v0), skyMaterial());
      sky.position.set((u0 + u1) / 2, (v0 + v1) / 2, out * (w.scale.z / 2 + 0.03)).applyQuaternion(w.quaternion).add(w.position);
      sky.quaternion.copy(w.quaternion);
      if (out > 0) sky.rotateY(Math.PI); // 앞면이 방 안을 보게
      sky.raycast = () => {};
      outside.add(sky);
    }
    const key = holes.map((h) => h.map((v) => v.toFixed(3)).join(",")).join("|");
    w.userData.solid ??= w.geometry;
    if ((w.userData.holeKey ?? "") === key) continue;
    if (w.geometry !== w.userData.solid) w.geometry.dispose();
    w.userData.holeKey = key;
    w.geometry = holes.length ? piecesGeometry(wallPieces(w.scale.x, w.scale.y, holes), w.scale.x, w.scale.y) : w.userData.solid;
  }
  model.add(outside);
}

export function shadowShell(model, extra = []) {
  const g = new THREE.Group();
  g.name = "shadowShell";
  const walls = [], ops = [];
  let floor = null;
  model.traverse((o) => {
    const k = o.userData?.kind;
    if (!o.isMesh) return;
    if (k === "wall") walls.push(o);
    else if (k === "window" || k === "door" || k === "opening") ops.push(o);
    else if (k === "floor") floor = o;
  });
  const inv = new THREE.Matrix4(), p = new THREE.Vector3();
  let top = 0;
  for (const w of walls) {
    const L = w.scale.x, H = w.scale.y, T = w.scale.z;
    top = Math.max(top, w.position.y + H / 2);
    inv.compose(w.position, w.quaternion, new THREE.Vector3(1, 1, 1)).invert();
    const holes = holesOn(w, [...spotsOf(ops), ...extra], inv, p);
    const frame = new THREE.Group();
    frame.position.copy(w.position);
    frame.quaternion.copy(w.quaternion);
    for (const [u0, u1, v0, v1] of wallPieces(L, H, holes)) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(u1 - u0, v1 - v0, T), SHADOW_ONLY);
      m.position.set((u0 + u1) / 2, (v0 + v1) / 2, 0);
      m.castShadow = true;
      m.userData.shadowOnly = true;
      frame.add(m);
    }
    g.add(frame);
  }
  if (floor) {
    const c = new THREE.Mesh(new THREE.BoxGeometry(floor.scale.x + 0.4, 0.06, floor.scale.z + 0.4), SHADOW_ONLY);
    c.position.set(floor.position.x, (top || 2.4) + 0.03, floor.position.z);
    c.castShadow = true;
    c.userData.shadowOnly = true;
    g.add(c);
    // 1인칭 둘러보기에서 보이는 천장 자리
    g.userData.ceiling = { x: floor.position.x, z: floor.position.z, w: floor.scale.x, d: floor.scale.z, y: top || 2.4 };
  }
  g.traverse((o) => { o.raycast = () => {}; }); // 고르기에 안 잡히게
  return g;
}

/** 고른 실제 벽지·바닥재 질감을 입힌다. size = 덮을 면의 (가로, 세로) m */
function finishMaterial(finish, color, w, h, extra = {}) {
  const map = finishTexture(finish), tm = tileMeters(finish);
  map.repeat.set(Math.max(1, w / tm), Math.max(1, h / tm));
  return new THREE.MeshStandardMaterial({ color, map, bumpMap: map, bumpScale: BUMP[finish.texture] ?? 0.004,
    roughness: ROUGH[finish.texture] ?? 0.9, envMapIntensity: finish.texture === "stone" ? 0.6 : 0.3, ...extra });
}

/** 바닥 모양 [[x, z], ...] → 눕히면 그 자리에 오는 면. 무늬는 네모 바닥과 같은 크기로 깔린다 */
export function outlineGeometry(outline) {
  const geo = new THREE.ShapeGeometry(new THREE.Shape(outline.map(([x, z]) => new THREE.Vector2(x, -z))));
  const xs = outline.map((p) => p[0]), zs = outline.map((p) => p[1]);
  const x0 = Math.min(...xs), z0 = Math.min(...zs), w = Math.max(...xs) - x0 || 1, d = Math.max(...zs) - z0 || 1;
  const pos = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, (pos.getX(i) - x0) / w, (-pos.getY(i) - z0) / d);
  return geo;
}

/** 바닥 마루, 벽 걸레받이, 창 유리·창틀, 문 나무·문틀. 반환: 컷어웨이(앞쪽 벽 흐리게)에 넣을 메시들
 *  finishes = { wall?: 마감재, floor?: 마감재 } (data/finishes의 항목) */
export function dressRoom(model, finishes = {}) {
  const extra = [], add = [];
  const trim = new THREE.MeshStandardMaterial({ color: 0xf3f2ee, roughness: 0.45 });
  model.traverse((o) => {
    if (!o.isMesh) return;
    const kind = o.userData?.kind, s = o.scale;
    if (kind === "floor") {
      let mat;
      if (finishes.floor) mat = finishMaterial(finishes.floor, o.material.color, s.x, s.z);
      else {
        const tex = plankTexture().clone();
        tex.needsUpdate = true;
        tex.repeat.set(s.x / PLANK_M, s.z / PLANK_M);
        mat = new THREE.MeshStandardMaterial({ color: o.material.color, map: tex, roughness: 0.62, envMapIntensity: 0.35 });
      }
      const outline = o.userData.outline; // 꺾인 집은 바깥벽을 따라 깐다 (서버 worker/outline.py)
      const floor = new THREE.Mesh(outline ? outlineGeometry(outline) : new THREE.PlaneGeometry(s.x, s.z), mat);
      floor.rotation.x = -Math.PI / 2;
      if (outline) floor.position.y = 0.0005;
      else floor.position.set(o.position.x, 0.0005, o.position.z);
      floor.receiveShadow = true;
      floor.userData.kind = "floor";
      o.material.visible = false;
      add.push(floor);
    } else if (kind === "wall") {
      if (finishes.wall) {
        const old = o.material;
        o.material = finishMaterial(finishes.wall, old.color, s.x, s.y,
          { transparent: old.transparent, opacity: old.opacity, depthWrite: old.depthWrite });
        old.dispose();
      } else Object.assign(o.material, { roughness: 0.92 });
      const bb = worldBox(o, s.x, BASEBOARD_H, s.z + 0.024, trim.clone(), BASEBOARD_H / 2);
      add.push(bb);
      extra.push(bb);
    } else if (kind === "window" || kind === "door") {
      const isWin = kind === "window", depth = s.z + 0.03;
      o.material = isWin
        ? new THREE.MeshPhysicalMaterial({ color: 0xd6e6ee, roughness: 0.04, metalness: 0, transparent: true, opacity: 0.28,
          envMapIntensity: 1.2, depthWrite: false })
        : new THREE.MeshStandardMaterial({ color: 0x9c7652, roughness: 0.6 });
      o.userData.baseOpacity = isWin ? 0.28 : 1;
      // 틀: 위·아래(창만)·좌·우
      const local = new THREE.Vector3();
      const piece = (w, h, dx, dy) => {
        const m = worldBox(o, w, h, depth, trim.clone());
        local.set(dx, dy, 0).applyQuaternion(o.quaternion);
        m.position.add(local);
        add.push(m);
        extra.push(m);
      };
      piece(s.x + FRAME_W * 2, FRAME_W, 0, s.y / 2 + FRAME_W / 2);
      if (isWin) {
        piece(s.x + FRAME_W * 2, FRAME_W, 0, -s.y / 2 - FRAME_W / 2);
        piece(FRAME_W * 0.6, s.y, 0, 0); // 가운데 창살
      }
      piece(FRAME_W, s.y, -s.x / 2 - FRAME_W / 2, 0);
      piece(FRAME_W, s.y, s.x / 2 + FRAME_W / 2, 0);
      if (isWin) o.scale.z = Math.max(0.01, o.scale.z * 0.25); // 유리는 얇게 (틀을 만든 뒤)
    }
  });
  add.forEach((m) => model.add(m));
  return extra;
}
