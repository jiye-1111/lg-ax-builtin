// 와이파이 히트맵 3D 층: 바닥 위 평면 하나 + 셰이더(연속 색 + 등고선), 등고선 글자, 탐침 경로, 추천 자리 핀
import * as THREE from "three";
import { rampBytes, colorAt, diffColorAt } from "./palette.js";

const Y = 0.03; // 바닥(러그 12 mm) 바로 위
const INK = new THREE.Color("#1c2024");

const VERT = /* glsl */ `
varying vec2 vXZ;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vXZ = w.xz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;
// uTop → 램프 왼쪽 끝, uBottom → 오른쪽 끝. 등고선: uStep마다 얇게, uBold 세 값에서 굵게 (fwidth로 1~2 px)
const FRAG = /* glsl */ `
uniform sampler2D uField, uRamp;
uniform vec2 uOrigin, uSpan;
uniform float uTop, uBottom, uStep, uOpacity, uBoldN;
uniform vec3 uBold;
uniform vec3 uInk;
varying vec2 vXZ;
float lineAt(float d, float w, float px) { return 1.0 - smoothstep(w * px * 0.5, w * (px * 0.5 + 1.0), d); }
void main() {
  vec2 uv = (vXZ - uOrigin) / uSpan;
  float v = texture2D(uField, uv).r;
  float t = clamp((v - uTop) / (uBottom - uTop), 0.0, 1.0);
  vec3 col = texture2D(uRamp, vec2(t * 0.996 + 0.002, 0.5)).rgb;
  float w = max(fwidth(v), 1e-4);
  float k = v / uStep;
  float thin = lineAt(abs(fract(k + 0.5) - 0.5) * uStep, w, 1.0);
  float bold = 0.0;
  if (uBoldN > 0.5) bold = max(bold, lineAt(abs(v - uBold.x), w, 2.4));
  if (uBoldN > 1.5) bold = max(bold, lineAt(abs(v - uBold.y), w, 2.4));
  if (uBoldN > 2.5) bold = max(bold, lineAt(abs(v - uBold.z), w, 2.4));
  float a = max(thin * 0.32, bold * 0.78);
  gl_FragColor = vec4(mix(col, uInk, a), min(1.0, uOpacity + a * 0.4));
  #include <colorspace_fragment>
}`;

function rampTexture(fn, from, to) {
  const t = new THREE.DataTexture(rampBytes(fn, from, to, 256), 256, 1, THREE.RGBAFormat);
  t.colorSpace = THREE.SRGBColorSpace;
  t.magFilter = t.minFilter = THREE.LinearFilter;
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.needsUpdate = true;
  return t;
}

// 글자 스프라이트 (같은 글은 텍스처를 다시 쓴다)
const texCache = new Map();
function textSprite(text, { bg = "rgba(255,255,255,.9)", fg = "#1c2024", h = 0.2, bold = false } = {}) {
  const k = `${text}|${bg}|${fg}|${bold}`;
  let tex = texCache.get(k);
  if (!tex) {
    const cv = document.createElement("canvas"), g = cv.getContext("2d"), px = 44;
    g.font = `${bold ? 700 : 600} ${px}px Pretendard, sans-serif`;
    const w = Math.ceil(g.measureText(text).width) + px;
    cv.width = w; cv.height = px * 1.6;
    g.font = `${bold ? 700 : 600} ${px}px Pretendard, sans-serif`;
    g.fillStyle = bg;
    const r = cv.height / 2;
    g.beginPath(); g.roundRect(0, 0, w, cv.height, r); g.fill();
    g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(text, w / 2, cv.height / 2 + 2);
    tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.userData.aspect = w / cv.height;
    texCache.set(k, tex);
  }
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthWrite: false, transparent: true }));
  s.scale.set(h * tex.userData.aspect, h, 1);
  s.renderOrder = 6;
  return s;
}
const disposeKids = (g) => { for (const c of [...g.children]) { g.remove(c); c.geometry?.dispose?.(); if (c.material && !c.material.map) c.material.dispose?.(); else c.material?.dispose?.(); } };

export function makeWifiLayer(scene) {
  const group = new THREE.Group();
  group.name = "wifi";
  scene.add(group);
  const ramps = { dbm: rampTexture(colorAt, -30, -90), diff: rampTexture(diffColorAt, 12, -12) };
  const uniforms = {
    uField: { value: null }, uRamp: { value: ramps.dbm }, uOrigin: { value: new THREE.Vector2() }, uSpan: { value: new THREE.Vector2(1, 1) },
    uTop: { value: -30 }, uBottom: { value: -90 }, uStep: { value: 5 }, uOpacity: { value: 0.55 }, uBold: { value: new THREE.Vector3(-50, -67, -75) }, uBoldN: { value: 3 },
    uInk: { value: INK },
  };
  const mat = new THREE.ShaderMaterial({ uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, extensions: { derivatives: true } });
  let mesh = null, shapeKey = "", tex = null, half = null;
  const labels = new THREE.Group(), probe = new THREE.Group(), pins = new THREE.Group();
  group.add(labels, probe, pins);

  const setShape = (outline, bounds) => {
    const pts = outline || [[bounds[0], bounds[1]], [bounds[2], bounds[1]], [bounds[2], bounds[3]], [bounds[0], bounds[3]]];
    const k = JSON.stringify(pts);
    if (k === shapeKey && mesh) return;
    shapeKey = k;
    if (mesh) { group.remove(mesh); mesh.geometry.dispose(); }
    const geo = new THREE.ShapeGeometry(new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, z))));
    geo.rotateX(Math.PI / 2); // (x, z, 0) → (x, 0, z)
    mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = Y;
    mesh.renderOrder = 2;
    mesh.frustumCulled = false;
    group.add(mesh);
  };

  return {
    group,
    /**
     * f: {origin, cell, nx, ny}, values: Float32Array (표시할 값), mode: 'dbm'|'mbps'|'diff'
     * range: {top, bottom, step, bold: []}, labels: [{xz, text}]
     */
    setHeat(f, values, { outline, bounds, range, mode = "dbm", opacity = 0.55, labels: labs = [] } = {}) {
      if (!f) { group.visible = false; return; }
      setShape(outline, bounds);
      const n = f.nx * f.ny;
      if (!half || half.length !== n) half = new Uint16Array(n);
      for (let i = 0; i < n; i++) half[i] = THREE.DataUtils.toHalfFloat(values[i]);
      if (!tex || tex.image.width !== f.nx || tex.image.height !== f.ny) {
        tex?.dispose();
        tex = new THREE.DataTexture(half, f.nx, f.ny, THREE.RedFormat, THREE.HalfFloatType);
        tex.magFilter = tex.minFilter = THREE.LinearFilter;
        tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
        tex.generateMipmaps = false;
      } else tex.image.data = half;
      tex.needsUpdate = true;
      uniforms.uField.value = tex;
      uniforms.uOrigin.value.set(f.origin[0], f.origin[1]);
      uniforms.uSpan.value.set(f.nx * f.cell, f.ny * f.cell);
      uniforms.uRamp.value = mode === "diff" ? ramps.diff : ramps.dbm;
      uniforms.uTop.value = range.top; uniforms.uBottom.value = range.bottom; uniforms.uStep.value = range.step;
      const b = range.bold || [];
      uniforms.uBold.value.set(b[0] ?? 0, b[1] ?? 0, b[2] ?? 0);
      uniforms.uBoldN.value = b.length;
      uniforms.uOpacity.value = opacity;
      disposeKids(labels);
      for (const l of labs) { const s = textSprite(l.text, { h: 0.22, bold: true }); s.position.set(l.xz[0], 0.1, l.xz[1]); labels.add(s); }
      group.visible = true;
    },
    clear() { group.visible = false; disposeKids(probe); disposeKids(pins); disposeKids(labels); },
    /** 탐침: paths [{kind, pts:[[x,y,z]...]}], badges [{at:[x,y,z], text}], at: 받는 점 */
    setProbe(p) {
      disposeKids(probe);
      if (!p) return;
      const COL = { direct: "#1c2024", reflection: "#0f7576", diffraction: "#b26b00" };
      for (const path of p.paths) {
        const c = new THREE.Color(COL[path.kind] || COL.direct);
        for (let k = 1; k < path.pts.length; k++) {
          const a = new THREE.Vector3(...path.pts[k - 1]), b = new THREE.Vector3(...path.pts[k]);
          const len = a.distanceTo(b);
          if (len < 1e-3) continue;
          const m = new THREE.Mesh(new THREE.CylinderGeometry(path.kind === "direct" ? 0.014 : 0.009, path.kind === "direct" ? 0.014 : 0.009, len, 6, 1, true),
            new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: path.kind === "direct" ? 0.9 : 0.6, depthWrite: false }));
          m.position.copy(a).add(b).multiplyScalar(0.5);
          m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
          m.renderOrder = 5;
          probe.add(m);
        }
      }
      for (const bd of p.badges || []) { const s = textSprite(bd.text, { h: 0.24, bg: "rgba(28,32,36,.88)", fg: "#fff" }); s.position.set(bd.at[0], bd.at[1] + 0.22, bd.at[2]); probe.add(s); }
      if (p.at) {
        const ring = new THREE.Mesh(new THREE.RingGeometry(0.07, 0.1, 28), new THREE.MeshBasicMaterial({ color: INK, transparent: true, opacity: 0.85, depthWrite: false, side: THREE.DoubleSide }));
        ring.rotation.x = -Math.PI / 2; ring.position.set(p.at[0], Y + 0.005, p.at[2]); ring.renderOrder = 5;
        probe.add(ring);
      }
    },
    /** 추천 자리 핀: [{xz, text}] */
    setPins(list) {
      disposeKids(pins);
      for (const [k, p] of (list || []).entries()) {
        const s = textSprite(p.text ?? String(k + 1), { h: 0.24, bg: "#1c2024", fg: "#fff", bold: true });
        s.position.set(p.xz[0], 0.55, p.xz[1]);
        pins.add(s);
        const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.45, 6), new THREE.MeshBasicMaterial({ color: INK }));
        stem.position.set(p.xz[0], 0.25, p.xz[1]);
        pins.add(stem);
        const dot = new THREE.Mesh(new THREE.CircleGeometry(0.09, 24), new THREE.MeshBasicMaterial({ color: INK, transparent: true, opacity: 0.35, depthWrite: false, side: THREE.DoubleSide }));
        dot.rotation.x = -Math.PI / 2; dot.position.set(p.xz[0], Y + 0.004, p.xz[1]);
        pins.add(dot);
      }
    },
    setVisible(on) { group.visible = !!on; },
  };
}
