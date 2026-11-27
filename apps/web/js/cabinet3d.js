// 맞춤장 3D: cabinet.js layout의 부재를 상자로 쌓고, 부위별 마감(무광·유광·나뭇결·돌·금속·유리)을 입힌다.
// 늘이거나 줄이지 않고 부재 자리로 크기를 바꾼다. 가전 모델은 따로 그 자리에 놓인다 (viewer.js).
import * as THREE from "three";
import { layout } from "./cabinet.js";

let palette = { panel: [], top: [], handle: [], glass: [] };
let kinds = {};
/** 서버 /api/cabinet/kinds를 받으면 한 번 부른다: 마감(LG 가전 색과 따로 쓰는 미리보기 마감)과 장 종류 기본 부재 */
export function setCabinetKinds(data) {
  if (data?.finishes) palette = data.finishes;
  for (const k of data?.kinds || []) kinds[k.kind] = k;
  mats.clear();
}
export const CAB_PREFIX = "decor:cab_";
/** 배치의 장 설정. 놓기 전 미리 보기(cab이 아직 없음)는 그 종류의 기본 부재로 */
export function cabOf(p) {
  if (p?.cab) return p.cab;
  if (!p?.sku?.startsWith(CAB_PREFIX) || !p.size_m) return null;
  const k = kinds[p.sku.slice(CAB_PREFIX.length)];
  if (!k) return null;
  return { kind: k.kind, mode: "new", outer_mm: { w: p.size_m[0] * 1000, h: p.size_m[1] * 1000, d: p.size_m[2] * 1000 }, parts: { ...k.parts },
    finish: { front: "warmwhite_matte", body: "warmwhite_matte", top: "stone_white", handle: "steel" }, ...(k.glass ? { glass: "clear" } : {}) };
}
const find = (group, id) => palette[group]?.find((f) => f.id === id) || palette[group]?.[0] || null;

// ---------- 무늬: 나뭇결·돌결·골유리 (한 번만 그리고 모든 장이 같이 쓴다) ----------
const texCache = {};
function canvasTex(key, size, draw, colour = true) {
  if (texCache[key]) return texCache[key];
  if (typeof document === "undefined") return null;
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  draw(cv.getContext("2d"), size);
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (colour) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return (texCache[key] = t);
}
const rng = (seed) => () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
// 세로로 흐르는 나뭇결 (밝은 회색 바탕이라 재질 색과 곱해진다)
const woodTex = () => canvasTex("wood", 512, (g, n) => {
  g.fillStyle = "#efefef"; g.fillRect(0, 0, n, n);
  const r = rng(7);
  for (let i = 0; i < 220; i++) {
    const x = r() * n, w = 0.6 + r() * 2.4, a = 0.05 + r() * 0.16;
    g.strokeStyle = `rgba(70,45,25,${a})`; g.lineWidth = w;
    g.beginPath(); g.moveTo(x, 0);
    for (let y = 0; y <= n; y += 16) g.lineTo(x + Math.sin(y / (40 + r() * 30) + i) * (2 + r() * 3), y);
    g.stroke();
  }
  for (let k = 0; k < 6; k++) { // 옹이 결
    const cx = r() * n, cy = r() * n;
    for (let j = 1; j < 9; j++) { g.strokeStyle = `rgba(80,50,30,${0.05 + 0.02 * (9 - j)})`; g.beginPath(); g.ellipse(cx, cy, j * 3, j * 14, 0, 0, Math.PI * 2); g.stroke(); }
  }
});
// 돌결: 고운 알갱이 + 옅은 물결 무늬
const stoneTex = () => canvasTex("stone", 512, (g, n) => {
  g.fillStyle = "#f2f2f2"; g.fillRect(0, 0, n, n);
  const r = rng(29), img = g.getImageData(0, 0, n, n);
  for (let i = 0; i < img.data.length; i += 4) { const v = 236 + (r() - 0.5) * 22; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; }
  g.putImageData(img, 0, 0);
  for (let k = 0; k < 9; k++) {
    g.strokeStyle = `rgba(120,115,108,${0.08 + r() * 0.12})`; g.lineWidth = 0.6 + r() * 1.6;
    g.beginPath(); let x = r() * n, y = r() * n; g.moveTo(x, y);
    for (let s = 0; s < 30; s++) { x += (r() - 0.3) * 40; y += (r() - 0.5) * 22; g.lineTo(x, y); }
    g.stroke();
  }
});
// 골유리: 세로 골 (밝고 어두운 줄)
const ribTex = () => canvasTex("rib", 256, (g, n) => {
  for (let x = 0; x < n; x++) { const v = 200 + 55 * Math.sin((x / n) * Math.PI * 2 * 16); g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, 0, 1, n); }
});

// ---------- 재질 ----------
const mats = new Map();
function finishMat(f, role) {
  const key = `${role}|${f?.id}`;
  if (mats.has(key)) return mats.get(key);
  const hex = f?.hex || "#eeeeee";
  let m;
  switch (f?.kind) {
    case "gloss": m = new THREE.MeshPhysicalMaterial({ color: hex, roughness: 0.16, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.06, envMapIntensity: 1.0 }); break;
    case "wood": m = new THREE.MeshStandardMaterial({ color: hex, map: woodTex(), roughness: 0.62, metalness: 0, envMapIntensity: 0.4 }); break;
    case "stone": m = new THREE.MeshPhysicalMaterial({ color: hex, map: stoneTex(), roughness: f.id === "ceramic_dark" ? 0.5 : 0.28, clearcoat: f.id === "ceramic_dark" ? 0.2 : 0.5, clearcoatRoughness: 0.2, envMapIntensity: 0.7 }); break;
    case "metal": m = new THREE.MeshStandardMaterial({ color: hex, roughness: f.id === "black" ? 0.45 : 0.28, metalness: f.id === "black" ? 0.4 : 0.95, envMapIntensity: 1 }); break;
    case "glass":
    case "glass_ribbed":
      m = new THREE.MeshPhysicalMaterial({ color: hex, transparent: true, opacity: f.opacity ?? 0.15, roughness: f.kind === "glass_ribbed" ? 0.35 : 0.04,
        metalness: 0, depthWrite: false, envMapIntensity: 0.8, side: THREE.DoubleSide, ...(f.kind === "glass_ribbed" ? { map: ribTex() } : {}) });
      break;
    default: m = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.88, metalness: 0, envMapIntensity: 0.25 }); // 무광
  }
  m.name = `cab_${role}`;
  m.userData.cabFinish = f?.id;
  mats.set(key, m);
  return m;
}
const STEEL = { id: "steel_fix", hex: "#C9CBCC", kind: "metal" };
const SHADOW_GAP = { id: "gap", hex: "#2b2a28", kind: "matte" };
function matFor(cab, role) {
  const fin = cab.finish || {};
  if (role === "front") return finishMat(find("panel", fin.front), "front");
  if (role === "top") return finishMat(find("top", fin.top), "top");
  if (role === "handle" || role === "frame") return finishMat(find("handle", fin.handle === "push" ? "steel" : fin.handle), "handle");
  if (role === "glass") return finishMat(find("glass", cab.glass || "clear"), "glass");
  if (role === "bowl" || role === "faucet") return finishMat(STEEL, "metal");
  if (role === "gap" || role === "cable") return finishMat(SHADOW_GAP, "gap");
  return finishMat(find("panel", fin.body), "body"); // 몸통·측판·마감판·틈막이·선반·걸레받이
}

// 상자 면 UV를 실제 크기(m)에 맞춘다: 나뭇결·돌결이 늘어나지 않는다 (0.6 m마다 무늬 한 번)
function scaleUv(geo, w, h, d) {
  const uv = geo.attributes.uv, T = 0.6;
  const faces = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]]; // +x −x +y −y +z −z
  for (let f = 0; f < 6; f++) for (let i = 0; i < 4; i++) {
    const k = f * 4 + i;
    uv.setXY(k, uv.getX(k) * faces[f][0] / T, uv.getY(k) * faces[f][1] / T);
  }
  uv.needsUpdate = true;
}

/** 장 하나의 3D (단위 m, 바닥 가운데 원점, 정면 +z). 부재마다 메시 하나: userData {cabPart, role} */
export function buildCabinet(cab, { preview = false } = {}) {
  const g = new THREE.Group();
  const { parts } = layout(cab);
  for (const p of parts) {
    const [x0, y0, z0, x1, y1, z1] = p.box.map((v) => v / 1000);
    const w = Math.max(x1 - x0, 0.001), h = Math.max(y1 - y0, 0.001), d = Math.max(z1 - z0, 0.001);
    const geo = new THREE.BoxGeometry(w, h, d);
    scaleUv(geo, w, h, d);
    let mat = matFor(cab, p.role);
    if (preview) { mat = mat.clone(); Object.assign(mat, { transparent: true, opacity: Math.min(mat.opacity ?? 1, 0.5), depthWrite: false }); }
    const m = new THREE.Mesh(geo, mat);
    m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    const glassy = p.role === "glass";
    m.castShadow = !preview && !glassy;
    m.receiveShadow = !glassy;
    if (glassy) m.renderOrder = 2;
    m.userData = { cabPart: p.name, role: p.role, shared: false, ownMaterial: preview };
    g.add(m);
  }
  // 문짝 사이 그림자 줄: 문짝마다 바로 뒤에 조금 큰 어두운 판 (유리문·옆을 보는 문은 빼고). TV월 빈 칸처럼 문 사이가 넓어도 칸을 덮지 않는다
  for (const p of parts) {
    if (!p.door || p.role !== "front" || p.face) continue;
    const [x0, y0, z0, x1, y1, z1] = p.box.map((v) => v / 1000);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0 + 0.003, y1 - y0 + 0.003), matFor(cab, "gap"));
    const zBack = (p.dir ?? 1) > 0 ? z0 - 0.0015 : z1 + 0.0015;
    back.position.set((x0 + x1) / 2, (y0 + y1) / 2, zBack);
    if ((p.dir ?? 1) < 0) back.rotation.y = Math.PI;
    back.userData = { cabPart: "gap", role: "gap" };
    g.add(back);
  }
  g.userData.cab = true;
  return g;
}

/** 문 열림 경고: 꼭짓점 8개(아래 넷 → 위 넷)로 된 문짝 모양 */
export function leafMesh(corners, colour = 0xb3261e, opacity = 0.35) {
  const pos = new Float32Array(corners.flat());
  const idx = [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 3, 7, 4, 3, 4, 0];
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: colour, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide }));
  m.renderOrder = 3;
  m.userData.doorWarn = true;
  return m;
}
