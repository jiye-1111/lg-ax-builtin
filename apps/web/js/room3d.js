// 스캔한 방 다듬기: 마루 바닥, 걸레받이, 창 유리·창틀, 문틀 + 스캔 가구를 Blender 모델로 바꾸기
// 방 glb(glb.py)는 노드마다 단위 상자를 scale로 늘린 모양이다. 노드 scale = (폭, 높이, 깊이).
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const FURN_DIR = "models/furniture/";
const PLANK_M = 2.4;          // 바닥 무늬 한 장이 덮는 길이 (m)
const BASEBOARD_H = 0.08;
const FRAME_W = 0.05;

// ---------- 스캔 가구 모델 ----------
const loader = new GLTFLoader();
let furnIndex = null;
const furnTemplates = new Map();
function furnitureTemplate(cat) {
  furnIndex ??= fetch(FURN_DIR + "index.json").then((r) => (r.ok ? r.json() : { models: {} })).catch(() => ({ models: {} }));
  if (!furnTemplates.has(cat)) {
    furnTemplates.set(cat, furnIndex.then((idx) => {
      const e = idx.models?.[cat];
      if (!e) return null;
      return loader.loadAsync(FURN_DIR + e.file).then((g) => ({ scene: g.scene, ref: e.ref_m }), () => null);
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

/** 스캔 가구 상자를 모델로 바꾼다. 상자는 안 보이게 두고 고르기(raycast)에만 쓴다. */
export function furnish(model, isCurrent, categoryOf = () => null) {
  const boxes = [];
  model.traverse((o) => { if (o.isMesh && o.userData?.kind === "object") boxes.push(o); });
  for (const box of boxes) {
    // 예전에 만든 집의 3D 파일에는 종류가 없다 → room.json의 종류로 채운다
    const cat = box.userData.category || categoryOf(box.name);
    if (!cat) continue;
    furnitureTemplate(cat).then((t) => {
      if (!t || !isCurrent()) return;
      const fitted = fitFurniture(t.scene, t.ref, box.scale);
      fitted.position.set(box.position.x, box.position.y - box.scale.y / 2, box.position.z);
      fitted.quaternion.copy(box.quaternion);
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

/** 바닥 마루, 벽 걸레받이, 창 유리·창틀, 문 나무·문틀. 반환: 컷어웨이(앞쪽 벽 흐리게)에 넣을 메시들 */
export function dressRoom(model) {
  const extra = [], add = [];
  const trim = new THREE.MeshStandardMaterial({ color: 0xf3f2ee, roughness: 0.45 });
  model.traverse((o) => {
    if (!o.isMesh) return;
    const kind = o.userData?.kind, s = o.scale;
    if (kind === "floor") {
      const tex = plankTexture().clone();
      tex.needsUpdate = true;
      tex.repeat.set(s.x / PLANK_M, s.z / PLANK_M);
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(s.x, s.z),
        new THREE.MeshStandardMaterial({ color: o.material.color, map: tex, roughness: 0.62, envMapIntensity: 0.35 }));
      floor.rotation.x = -Math.PI / 2;
      floor.position.set(o.position.x, 0.0005, o.position.z);
      floor.receiveShadow = true;
      floor.userData.kind = "floor";
      o.material.visible = false;
      add.push(floor);
    } else if (kind === "wall") {
      Object.assign(o.material, { roughness: 0.92 });
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
