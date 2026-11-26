// 와이파이 전파 계산. 받는 점 하나(trace)와 바닥 전체 격자(field)를 같은 식으로 구한다.
// 직접 경로 + 1차 반사(거울상) + 문틈·벽 끝 회절(나이프엣지)을 전력 합으로 더한다.
// 좌표: 평면 (x, z), 높이 y (m). 브라우저 Worker와 node 테스트 둘 다에서 돈다 (DOM 없음).
import {
  FREQ_MHZ, DEFAULT_WIDTH_MHZ, MATERIALS, materialOf, wallLoss, bandIndex, objectRf, ENCLOSURE,
  ANGLE_MAX_DEG, ANGLE_EXTRA_MAX_DB, MCS, WIDTH_SCALE, MAC_EFFICIENCY, NOISE_FIGURE_DB, CONGESTION_SHARE, MICROWAVE,
} from "./materials.js";

export const CAUSE_KINDS = ["none", "distance", "wall", "object", "antenna", "enclosure", "interference", "reflection", "diffraction"];
const K = Object.fromEntries(CAUSE_KINDS.map((k, i) => [k, i]));
const C_MHZ = 299.792458; // λ(m) = C / f(MHz)
const COS_MAX = Math.cos((ANGLE_MAX_DEG * Math.PI) / 180);
const MIN_D = 0.25; // 공유기 바로 옆은 이 거리로 본다
const HPBW = 60, ANT_MIN = -20;
const EPS = 1e-7;
const ACCEL_CELL = 1.0, FRESNEL_MAX = 0.6;
const ALL_ON = { distance: true, wall: true, object: true, reflection: true, diffraction: true, interference: true };

// ---------------------------------------------------------------- 장면 준비
/**
 * input: { walls: [{id, a:[x,z], b:[x,z], h, t, material, name?}],
 *          openings: [{id, wall, kind: 'door'|'window'|'open', u0, u1, z0, z1, material?}],
 *          objects: [{id, kind, name?, c:[x,z], ang, w, d, y0, y1, loss?: [2.4, 5, 6]}] }
 * ang = 폭(w) 축 방향 (라디안). u0/u1 = 벽 시작점에서 잰 거리(m), z0/z1 = 바닥에서 높이(m)
 */
export function prepare(input) {
  const walls = (input.walls || []).map((w, i) => {
    const dx = w.b[0] - w.a[0], dz = w.b[1] - w.a[1], L = Math.hypot(dx, dz) || 1e-6;
    const mat = materialOf(w.material);
    return {
      i, id: w.id, ax: w.a[0], az: w.a[1], bx: w.b[0], bz: w.b[1], dx, dz, L, nx: -dz / L, nz: dx / L,
      h: w.h ?? 2.4, material: MATERIALS[w.material] ? w.material : Object.keys(MATERIALS).find((k) => MATERIALS[k] === mat),
      loss: [0, 1, 2].map((b) => wallLoss(w.material, ["2.4", "5", "6"][b], w.t ?? mat.t_ref)), refl: mat.refl, ko: w.name || mat.ko, ops: [],
    };
  });
  const byId = new Map(walls.map((w) => [w.id, w]));
  const edges = [];
  for (const o of input.openings || []) {
    const w = byId.get(o.wall);
    if (!w) continue;
    const kind = o.kind === "window" ? "window" : o.kind === "door" ? "door" : "open";
    const gm = kind === "window" ? (MATERIALS[o.material] ? o.material : "double_glass") : null;
    const op = { id: o.id, kind, u0: Math.max(0, o.u0), u1: Math.min(w.L, o.u1), z0: o.z0 ?? 0, z1: o.z1 ?? 2.1, glass: gm && [0, 1, 2].map((b) => wallLoss(gm, ["2.4", "5", "6"][b], MATERIALS[gm].t_ref)), glassRefl: gm && MATERIALS[gm].refl, glassKo: gm && MATERIALS[gm].ko };
    w.ops.push(op);
    for (const u of [op.u0, op.u1]) { // 문틀 양쪽 세로 모서리
      if (u <= 0.01 || u >= w.L - 0.01) continue;
      edges.push({ x: w.ax + (w.dx * u) / w.L, z: w.az + (w.dz * u) / w.L, wall: w.i, y0: op.z0, y1: op.z1, glass: op.glass, opening: op, u, free: false });
    }
  }
  // 다른 벽에 붙지 않은 벽 끝 (가벽·칸막이 끝): 여기서도 돌아 들어간다
  for (const w of walls) {
    for (const [x, z, u] of [[w.ax, w.az, 0], [w.bx, w.bz, w.L]]) {
      const touches = walls.some((v) => v !== w && segDist(x, z, v) < 0.08);
      if (!touches) edges.push({ x, z, wall: w.i, y0: 0, y1: w.h, glass: null, opening: null, u, free: true });
    }
  }
  const objects = [];
  for (const o of input.objects || []) {
    const rf = o.loss ? { loss: o.loss, ko: o.name } : objectRf(o.kind);
    if (!rf || !(o.w > 0) || !(o.d > 0) || !(o.y1 > o.y0)) continue;
    objects.push({
      i: objects.length, id: o.id, kind: rf.kind || o.kind, ko: o.name || rf.ko, cx: o.c[0], cz: o.c[1], ca: Math.cos(o.ang || 0), sa: Math.sin(o.ang || 0),
      hw: o.w / 2, hd: o.d / 2, y0: o.y0, y1: o.y1, loss: rf.loss, microwave: (rf.kind || o.kind) === "microwave",
    });
  }
  const sc = { walls, edges, objects, microwaves: objects.filter((o) => o.microwave), block: new Uint32Array(walls.length), blockTick: 0 };
  buildAccel(sc);
  return sc;
}

function segDist(x, z, w) {
  const t = Math.max(0, Math.min(1, ((x - w.ax) * w.dx + (z - w.az) * w.dz) / (w.L * w.L)));
  return Math.hypot(w.ax + w.dx * t - x, w.az + w.dz * t - z);
}

// 벽·물체를 1 m 칸에 나눠 담아, 선분이 지나는 칸만 본다 (벽 300개, 물체 300개까지)
function buildAccel(sc) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  const grow = (x, z) => { x0 = Math.min(x0, x); z0 = Math.min(z0, z); x1 = Math.max(x1, x); z1 = Math.max(z1, z); };
  for (const w of sc.walls) { grow(w.ax, w.az); grow(w.bx, w.bz); }
  const ob = sc.objects.map((o) => {
    const r = Math.abs(o.hw * o.ca) + Math.abs(o.hd * o.sa) + FRESNEL_MAX, s = Math.abs(o.hw * o.sa) + Math.abs(o.hd * o.ca) + FRESNEL_MAX;
    grow(o.cx - r, o.cz - s); grow(o.cx + r, o.cz + s);
    return [o.cx - r, o.cz - s, o.cx + r, o.cz + s];
  });
  const n = sc.walls.length + sc.objects.length;
  if (!isFinite(x0) || n < 16) { sc.accel = null; return; } // 작은 집은 전부 보는 게 더 빠르다
  x0 -= 0.5; z0 -= 0.5; x1 += 0.5; z1 += 0.5;
  const nx = Math.max(1, Math.ceil((x1 - x0) / ACCEL_CELL)), nz = Math.max(1, Math.ceil((z1 - z0) / ACCEL_CELL));
  const cells = Array.from({ length: nx * nz }, () => []);
  const put = (bx0, bz0, bx1, bz1, id) => {
    const i0 = clampI((bx0 - x0) / ACCEL_CELL, nx), i1 = clampI((bx1 - x0) / ACCEL_CELL, nx), j0 = clampI((bz0 - z0) / ACCEL_CELL, nz), j1 = clampI((bz1 - z0) / ACCEL_CELL, nz);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) cells[j * nx + i].push(id);
  };
  for (const w of sc.walls) put(Math.min(w.ax, w.bx), Math.min(w.az, w.bz), Math.max(w.ax, w.bx), Math.max(w.az, w.bz), w.i);
  ob.forEach((b, k) => put(b[0], b[1], b[2], b[3], sc.walls.length + k));
  sc.accel = { x0, z0, nx, nz, cells, stamp: new Uint32Array(n), tick: 0, nW: sc.walls.length };
}
const clampI = (v, n) => Math.max(0, Math.min(n - 1, Math.floor(v)));

// ---------------------------------------------------------------- 선분 하나가 잃는 세기
// rec가 있으면 지나간 벽·물체를 적는다 (탐침용). skip = 이 벽은 보지 않는다 (반사·회절 점이 있는 벽)
// mark면 막은 벽에 표시하고 가장 크게 잃은 원인을 남긴다 (직접 경로). 격자 계산이 빨라야 해서 클로저 없이 모듈 변수로 돈다
let cPx = 0, cPy = 0, cPz = 0, cRx = 0, cRy = 0, cRz = 0, cLen = 1, cB = 0, cSkip = -1, cRec = null, cLamb = 0.06, cLoss = 0, cMark = false, cSc = null;
let hitMax = 0, hitCode = 0, blockedAny = false;
function castLoss(sc, b, P, Q, causes, skip, rec, lamb, mark = false) {
  cPx = P[0]; cPy = P[1]; cPz = P[2]; cRx = Q[0] - P[0]; cRy = Q[1] - P[1]; cRz = Q[2] - P[2];
  cLen = Math.hypot(cRx, cRy, cRz) || 1e-9; cB = b; cSkip = skip; cRec = rec; cLamb = lamb; cLoss = 0; cMark = mark; cSc = sc;
  const acc = sc.accel, cw = causes.wall, co = causes.object;
  if (!acc) {
    if (cw) for (let k = 0; k < sc.walls.length; k++) wallTest(sc.walls[k]);
    if (co) for (let k = 0; k < sc.objects.length; k++) objTest(sc.objects[k]);
    return cLoss;
  }
  // 지나가는 칸만 차례로 (Amanatides–Woo)
  let tick = ++acc.tick;
  if (tick >= 0xfffffff0) { acc.stamp.fill(0); acc.tick = tick = 1; }
  const stamp = acc.stamp, nW = acc.nW, cells = acc.cells, nx = acc.nx, nz = acc.nz;
  let i = clampI((cPx - acc.x0) / ACCEL_CELL, nx), j = clampI((cPz - acc.z0) / ACCEL_CELL, nz);
  const ie = clampI((Q[0] - acc.x0) / ACCEL_CELL, nx), je = clampI((Q[2] - acc.z0) / ACCEL_CELL, nz);
  const sx = cRx > 0 ? 1 : -1, sz = cRz > 0 ? 1 : -1;
  const tdx = cRx !== 0 ? Math.abs(ACCEL_CELL / cRx) : Infinity, tdz = cRz !== 0 ? Math.abs(ACCEL_CELL / cRz) : Infinity;
  let tmx = cRx !== 0 ? (acc.x0 + (i + (sx > 0 ? 1 : 0)) * ACCEL_CELL - cPx) / cRx : Infinity;
  let tmz = cRz !== 0 ? (acc.z0 + (j + (sz > 0 ? 1 : 0)) * ACCEL_CELL - cPz) / cRz : Infinity;
  for (let guard = 0; guard < 4096; guard++) {
    const list = cells[j * nx + i];
    for (let k = 0; k < list.length; k++) {
      const id = list[k];
      if (stamp[id] === tick) continue;
      stamp[id] = tick;
      if (id < nW) { if (cw) wallTest(sc.walls[id]); } else if (co) objTest(sc.objects[id - nW]);
    }
    if (i === ie && j === je) break;
    if (tmx < tmz) { if (tmx > 1) break; tmx += tdx; i += sx; if (i < 0 || i >= nx) break; }
    else { if (tmz > 1) break; tmz += tdz; j += sz; if (j < 0 || j >= nz) break; }
  }
  return cLoss;
}
function wallTest(w) {
  if (w.i === cSkip) return;
  const den = cRx * w.dz - cRz * w.dx;
  if (den > -1e-12 && den < 1e-12) return;
  const qx = w.ax - cPx, qz = w.az - cPz;
  const t = (qx * w.dz - qz * w.dx) / den;
  if (t <= EPS || t >= 1 - EPS) return;
  const u = (qx * cRz - qz * cRx) / den;
  if (u < 0 || u > 1) return;
  const y = cPy + t * cRy;
  if (y > w.h || y < 0) return; // 벽 위로 지나간다
  const pos = u * w.L;
  let L0 = w.loss[cB], ko = w.ko, glass = false;
  for (let k = 0; k < w.ops.length; k++) {
    const op = w.ops[k];
    if (pos >= op.u0 && pos <= op.u1 && y >= op.z0 && y <= op.z1) {
      if (!op.glass) return; // 문·뚫린 곳: 벽 손실 없음
      L0 = op.glass[cB]; ko = op.glassKo; glass = true;
      break;
    }
  }
  const cos = Math.max(COS_MAX, Math.abs(cRx * w.nx + cRz * w.nz) / cLen);
  const db = L0 + Math.min(ANGLE_EXTRA_MAX_DB, L0 / cos - L0);
  cLoss += db;
  if (cMark) {
    if (!glass) { cSc.block[w.i] = cSc.blockTick; blockedAny = true; }
    if (db > hitMax) { hitMax = db; hitCode = (K.wall << 12) | (w.i & 0xfff); }
  }
  if (cRec) cRec.push({ kind: "wall", refId: w.id, name: ko, glass, db, at: [cPx + t * cRx, y, cPz + t * cRz], code: (K.wall << 12) | (w.i & 0xfff) });
}
function objTest(o) {
  const f = objFraction(o, cPx, cPy, cPz, cRx, cRy, cRz, cLen, cLamb);
  if (f <= 0) return;
  const db = o.loss[cB] * f;
  cLoss += db;
  if (cMark && db > hitMax) { hitMax = db; hitCode = (K.object << 12) | (o.i & 0xfff); }
  if (cRec) cRec.push({ kind: "object", refId: o.id, name: o.ko, db, at: [o.cx, Math.min(o.y1, Math.max(o.y0, cPy + cRy * 0.5)), o.cz], code: (K.object << 12) | (o.i & 0xfff) });
}

// 물체가 선분을 얼마나 가리는지 0..1. 1차 프레넬 반경만큼 경계를 부드럽게 한다
function objFraction(o, Px, Py, Pz, rx, ry, rz, len3, lamb) {
  // 물체 기준 좌표 (u: 폭, v: 깊이)
  const px = Px - o.cx, pz = Pz - o.cz;
  const lu = px * o.ca + pz * o.sa, lv = -px * o.sa + pz * o.ca, ly = Py;
  const du = rx * o.ca + rz * o.sa, dv = -rx * o.sa + rz * o.ca;
  const ym = (o.y0 + o.y1) / 2, hy = (o.y1 - o.y0) / 2;
  // 가운데에 가장 가까운 곳에서 프레넬 반경
  const tc = Math.max(0.02, Math.min(0.98, -(lu * du + lv * dv + (ly - ym) * ry) / (len3 * len3)));
  const rF = Math.min(FRESNEL_MAX, Math.max(0.02, Math.sqrt((lamb * tc * (1 - tc) * len3 * len3) / len3)));
  const yc = ly - ym;
  if (!slabAll(lu, du, o.hw + rF, lv, dv, o.hd + rF, yc, ry, hy + rF)) return 0;
  const inner = -Math.min(rF / 2, Math.min(o.hw, o.hd, hy) * 0.95);
  if (slabAll(lu, du, o.hw + inner, lv, dv, o.hd + inner, yc, ry, hy + inner)) return inner <= -rF / 2 + 1e-9 ? 1 : 0.5 - inner / rF;
  let lo = inner, hi = rF; // lo: 안 닿음, hi: 닿음 → 닿기 시작하는 여유 c
  for (let k = 0; k < 5; k++) { const m = (lo + hi) / 2; if (slabAll(lu, du, o.hw + m, lv, dv, o.hd + m, yc, ry, hy + m)) hi = m; else lo = m; }
  return Math.max(0, Math.min(1, 0.5 - (lo + hi) / 2 / rF));
}
// 세 축 구간이 [0,1] 안에서 겹치는지
let sT0 = 0, sT1 = 1;
function axis(p, d, h) {
  if (!(h > 0)) return false;
  if (d > -1e-12 && d < 1e-12) return p >= -h && p <= h;
  let a = (-h - p) / d, c = (h - p) / d;
  if (a > c) { const x = a; a = c; c = x; }
  if (a > sT0) sT0 = a;
  if (c < sT1) sT1 = c;
  return sT0 <= sT1;
}
function slabAll(pu, du, hu, pv, dv, hv, py, dy, hy) {
  sT0 = 0; sT1 = 1;
  return axis(pu, du, hu) && axis(pv, dv, hv) && axis(py, dy, hy);
}

// ---------------------------------------------------------------- 기본 식
const fspl = (d, f, n, on) => 20 * Math.log10(f) - 27.55 + (on ? 10 * n * Math.log10(Math.max(MIN_D, d)) : 0);
function antenna(P, Q, on) {
  if (!on) return 0;
  const hz = Math.hypot(Q[0] - P[0], Q[2] - P[2]), dy = Math.abs(Q[1] - P[1]);
  const phi = (Math.atan2(dy, hz) * 180) / Math.PI;
  return Math.max(ANT_MIN, -12 * (phi / HPBW) ** 2);
}
// 나이프엣지 회절 J(ν) (ITU-R P.526)
export const knifeEdge = (v) => (v <= -0.78 ? 0 : 6.9 + 20 * Math.log10(Math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1));
const dist3 = (A, B) => Math.hypot(B[0] - A[0], B[1] - A[1], B[2] - A[2]);
const toDb = (p) => (p > 0 ? 10 * Math.log10(p) : -300);
const lin = (db) => 10 ** (db / 10);

function context(router, opts = {}) {
  const band = String(router.band ?? "5"), b = bandIndex(band), f = FREQ_MHZ[band] ?? FREQ_MHZ[5];
  const causes = { ...ALL_ON, ...(opts.causes || {}) };
  const width = router.width ?? DEFAULT_WIDTH_MHZ[band] ?? 80;
  const itf = opts.interference || {};
  const noiseBase = -174 + 10 * Math.log10(width * 1e6) + NOISE_FIGURE_DB + (causes.interference ? (itf.congestion || 0) * (CONGESTION_SHARE[band] ?? 1) : 0);
  return {
    band, b, f, lamb: C_MHZ / f, causes, n: opts.n ?? 2.0, width, noiseBase,
    microwaveOn: !!(causes.interference && itf.microwaveOn && band === "2.4"),
    tx: router.tx ?? 20, enc: ENCLOSURE[router.enclosure]?.db ?? 0, antennaOn: opts.antenna !== false && router.antennaPattern !== "flat",
    P: [router.xz[0], router.h ?? 1.0, router.xz[1]], rxH: opts.rxH ?? 1.0,
    multi: true, multiOnly: false, extra: 0,
    prune: opts.preview ? 12 : 22, // 직접 경로보다 이만큼 약한 길은 건너뛴다 (미리보기는 더 과감히)
  };
}

// ---------------------------------------------------------------- 받는 점 하나
// detail이면 원인·경로까지, 아니면 숫자만 (격자용)
function evaluate(sc, cx, Q, detail) {
  const { P, b, f, lamb, causes, n } = cx;
  const recD = detail ? [] : null;
  const dD = dist3(P, Q);
  const fsD = fspl(dD, f, n, causes.distance);
  const antD = antenna(P, Q, cx.antennaOn);
  // 직접 경로. 막은 벽(유리 말고)은 sc.block에 이번 차례 번호로 표시된다
  if (++sc.blockTick >= 0xfffffff0) { sc.block.fill(0); sc.blockTick = 1; }
  const tickB = sc.blockTick, block = sc.block;
  hitMax = 0; hitCode = 0; blockedAny = false;
  const wallObjD = castLoss(sc, b, P, Q, causes, -1, recD, lamb, true);
  const worstHit = hitMax, worstCode = hitCode, blocked = blockedAny;
  // 문틀·벽 끝 근처를 스칠 때 (보이는 쪽) 조금 잃는다 → 그림자 경계가 이어진다
  let litJ = 0, litEdge = null;
  const rx = Q[0] - P[0], rz = Q[2] - P[2], r2 = rx * rx + rz * rz;
  const edgeOn = causes.diffraction && causes.wall && r2 > 1e-9;
  if (edgeOn) {
    for (const e of sc.edges) {
      if (block[e.wall] === tickB) continue;
      const s = ((e.x - P[0]) * rx + (e.z - P[2]) * rz) / r2;
      if (s <= 0.01 || s >= 0.99) continue;
      const hgt = Math.abs((e.x - P[0]) * rz - (e.z - P[2]) * rx) / Math.sqrt(r2);
      if (hgt > 1.5) continue;
      if (!edgeFaces(sc, e, P, Q)) continue;
      const d1 = s * dD, d2 = (1 - s) * dD;
      const J = knifeEdge(-hgt * Math.sqrt((2 * (d1 + d2)) / (lamb * d1 * d2)));
      if (J > litJ) { litJ = J; litEdge = e; }
    }
  }
  const lossD = fsD + wallObjD - antD + cx.enc + litJ;
  const pD = cx.tx - lossD;
  let sumR = 0, sumF = 0;
  const best = detail ? [] : null;
  // 반사: 벽마다 거울상 공유기 (격자의 가는 칸에서는 굵은 칸에서 구한 값을 이어 쓴다: cx.multi = false)
  if (causes.reflection && cx.multi) {
    const floorLoss = lossD + cx.prune; // 이보다 훨씬 약한 경로는 더해도 티가 안 난다
    for (const w of sc.walls) {
      const sP = (P[0] - w.ax) * w.nx + (P[2] - w.az) * w.nz, sQ = (Q[0] - w.ax) * w.nx + (Q[2] - w.az) * w.nz;
      if (sP * sQ <= 0) continue; // 같은 쪽에 있어야 튕겨 온다
      const ix = P[0] - 2 * sP * w.nx, iz = P[2] - 2 * sP * w.nz;
      const tq = sP / (sP + sQ); // 거울상 → Q 선분이 벽선을 지나는 곳
      const hx = ix + (Q[0] - ix) * tq, hz = iz + (Q[2] - iz) * tq;
      const u = ((hx - w.ax) * w.dx + (hz - w.az) * w.dz) / w.L;
      if (u < 0 || u > w.L) continue;
      const hy = P[1] + (Q[1] - P[1]) * tq;
      if (hy < 0 || hy > w.h) continue;
      let refl = w.refl, through = false;
      for (const op of w.ops) if (u >= op.u0 && u <= op.u1 && hy >= op.z0 && hy <= op.z1) { if (!op.glass) through = true; else refl = op.glassRefl; break; }
      if (through) continue;
      const len = Math.hypot(Q[0] - ix, Q[1] - P[1], Q[2] - iz);
      const H = detail ? [hx, hy, hz] : (SH[0] = hx, SH[1] = hy, SH[2] = hz, SH);
      const lower = fspl(len, f, n, causes.distance) + refl + cx.enc;
      if (lower > floorLoss) continue;
      const rec = detail ? [] : null;
      const legs = castLoss(sc, b, P, H, causes, w.i, rec, lamb) + castLoss(sc, b, H, Q, causes, w.i, rec, lamb);
      const pr = cx.tx - (lower + legs - antenna(P, H, cx.antennaOn));
      sumR += lin(pr);
      if (detail) best.push({ kind: "reflection", pts: [P, H, Q], db: pr, refId: w.id, name: w.ko, hits: rec });
    }
  }
  // 회절: 직선이 벽에 막혔을 때만, 문틀·벽 끝을 돌아서
  if (edgeOn && blocked && cx.multi) {
    const floorLoss = lossD + cx.prune;
    for (const e of sc.edges) {
      const d1h = Math.hypot(e.x - P[0], e.z - P[2]), d2h = Math.hypot(Q[0] - e.x, Q[2] - e.z);
      const ey = Math.max(e.y0 + 0.05, Math.min(e.y1 - 0.05, P[1] + ((Q[1] - P[1]) * d1h) / (d1h + d2h || 1)));
      const E = detail ? [e.x, ey, e.z] : (SH[0] = e.x, SH[1] = ey, SH[2] = e.z, SH);
      const d1 = dist3(P, E), d2 = dist3(E, Q);
      if (d1 < 0.05 || d2 < 0.05) continue;
      const cosA = ((E[0] - P[0]) * (Q[0] - E[0]) + (E[1] - P[1]) * (Q[1] - E[1]) + (E[2] - P[2]) * (Q[2] - E[2])) / (d1 * d2);
      const alpha = Math.acos(Math.max(-1, Math.min(1, cosA)));
      const J = knifeEdge(alpha * Math.sqrt((2 * d1 * d2) / (lamb * (d1 + d2))));
      const glass = e.glass ? e.glass[b] : 0;
      const lower = fspl(d1 + d2, f, n, causes.distance) + J + glass + cx.enc;
      if (lower > floorLoss) continue;
      const rec = detail ? [] : null;
      const legs = castLoss(sc, b, P, E, causes, e.wall, rec, lamb) + castLoss(sc, b, E, Q, causes, e.wall, rec, lamb);
      const pf = cx.tx - (lower + legs - antenna(P, E, cx.antennaOn));
      sumF += lin(pf);
      if (detail) best.push({ kind: "diffraction", pts: [P, E, Q], db: pf, refId: e.opening?.id ?? sc.walls[e.wall].id, name: e.free ? "벽 끝" : e.opening.kind === "window" ? "창틀" : "문틀", hits: rec });
    }
  }
  if (!detail && cx.multiOnly) { out.multi = sumR + sumF; return out; }
  const linD = lin(pD), total = linD + sumR + sumF + (cx.extra || 0);
  const rssi = toDb(total);
  // 잡음: 바닥 잡음 + 혼잡 + 켠 전자레인지 (2.4 GHz)
  let rise = 0, riseFrom = null;
  if (cx.microwaveOn) for (const m of sc.microwaves) {
    const d = Math.hypot(Q[0] - m.cx, Q[1] - (m.y0 + m.y1) / 2, Q[2] - m.cz);
    const r = MICROWAVE.rise_db / (1 + (d / MICROWAVE.half_m) ** 2);
    if (r > rise) { rise = r; riseFrom = m; }
  }
  const noise = cx.noiseBase + rise;
  const snr = rssi - noise;
  // 가장 많이 잃게 한 원인 (거리는 빼고)
  let code = K.distance << 12, worst = 1;
  if (worstHit > worst) { worst = worstHit; code = worstCode; }
  if (-antD > worst) { worst = -antD; code = K.antenna << 12; }
  if (cx.enc > worst) { worst = cx.enc; code = K.enclosure << 12; }
  if (rise > worst && snr < 25) code = (K.interference << 12) | (riseFrom.i & 0xfff);
  if (!detail) { out.rssi = rssi; out.snr = snr; out.code = code; out.noise = noise; return out; }
  // 원인별 나누기: 출력 + Σ contributions = rssi
  const contributions = [{ kind: "distance", db: -fsD }];
  for (const h of recD) contributions.push({ kind: h.kind, refId: h.refId, name: h.name, db: -h.db, at: h.at });
  if (antD < 0) contributions.push({ kind: "antenna", db: antD });
  if (cx.enc) contributions.push({ kind: "enclosure", db: -cx.enc });
  if (litJ > 0.05) contributions.push({ kind: "diffraction", refId: litEdge.opening?.id, name: litEdge.free ? "벽 끝 가까이" : "문틀 가까이", db: -litJ, at: [litEdge.x, cx.rxH, litEdge.z] });
  const gain = rssi - pD;
  if (gain > 0.005) {
    const shareR = sumR / (sumR + sumF || 1);
    if (sumR > 0) contributions.push({ kind: "reflection", db: gain * shareR });
    if (sumF > 0) contributions.push({ kind: "diffraction", db: gain * (1 - shareR), gain: true });
  }
  best.sort((a, c) => c.db - a.db);
  const paths = [{ kind: "direct", pts: [P, Q], db: pD, hits: recD }, ...best];
  return { rssi, snr, noise, mbps: speed(snr, cx.width), contributions, paths, interference: rise > 0 ? [{ kind: "interference", refId: riseFrom.id, name: riseFrom.ko, db: rise }] : [], code };
}
const out = { rssi: 0, snr: 0, code: 0, noise: 0, multi: 0 };
const SH = [0, 0, 0]; // 격자 계산용 꺾이는 점 (새 배열을 안 만든다)
// 지금 선분이 이 모서리를 "보이는 쪽"에서 지나는지: 문틀이면 그 문 구멍으로 지나야 하고, 벽 끝이면 그 벽을 안 건너야 한다
function edgeFaces(sc, e, P, Q) {
  const w = sc.walls[e.wall];
  const rx = Q[0] - P[0], rz = Q[2] - P[2];
  const den = rx * w.dz - rz * w.dx;
  if (Math.abs(den) < 1e-12) return e.free;
  const qx = w.ax - P[0], qz = w.az - P[2];
  const t = (qx * w.dz - qz * w.dx) / den, u = ((qx * rz - qz * rx) / den) * w.L;
  const crosses = t > EPS && t < 1 - EPS && u >= 0 && u <= w.L;
  if (e.free) return !crosses;
  if (!crosses) return false;
  const y = P[1] + t * (Q[1] - P[1]);
  return u >= e.opening.u0 && u <= e.opening.u1 && y >= e.opening.z0 && y <= e.opening.z1;
}

/** 받는 세기에 맞는 예상 속도 (Mbps, 실제 체감 기준). 공간 평균이라 MCS 단계 사이는 이어서 본다 */
export function speed(snr, width = 80) {
  let r = 0;
  if (snr >= MCS[MCS.length - 1][0]) r = MCS[MCS.length - 1][1];
  else if (snr > 0) {
    let lo = [0, 0];
    for (const m of MCS) { if (snr < m[0]) { r = lo[1] + ((m[1] - lo[1]) * (snr - lo[0])) / (m[0] - lo[0]); break; } lo = m; }
  }
  return Math.round(r * (WIDTH_SCALE[width] ?? 1) * MAC_EFFICIENCY);
}

/**
 * 받는 점 하나. router: {xz, h, band, tx?, width?, enclosure?}, rx: [x, z]
 * opts: {rxH, causes, interference: {microwaveOn, congestion}, n, antenna}
 */
export function trace(sc, router, rx, opts = {}) {
  const cx = context(router, opts);
  return evaluate(sc, cx, [rx[0], cx.rxH, rx[1]], true);
}

/** 바닥 격자. bounds [x0, z0, x1, z1], cell(m). rssi·snr: Float32Array, cause: Uint16Array (종류 << 12 | 번호)
 * 직접 경로는 칸마다, 반사·회절(천천히 변한다)은 두 배 굵은 칸에서 구해 선형 세기로 이어 붙인다 */
export function field(sc, router, opts = {}) {
  const cx = context(router, opts), c = opts.cell ?? 0.1;
  const [x0, z0, x1, z1] = opts.bounds;
  const nx = Math.max(1, Math.ceil((x1 - x0) / c - 1e-9)), ny = Math.max(1, Math.ceil((z1 - z0) / c - 1e-9));
  const rssi = new Float32Array(nx * ny), snr = new Float32Array(nx * ny), mbps = new Float32Array(nx * ny), cause = new Uint16Array(nx * ny);
  const Q = [0, cx.rxH, 0];
  const step = opts.multiStep ?? (opts.preview ? 3 : 2), C2 = c * step; // 미리보기는 반사·회절을 더 굵게
  const mx = Math.ceil((x1 - x0) / C2) + 2, mz = Math.ceil((z1 - z0) / C2) + 2;
  const multi = new Float32Array(mx * mz);
  const anyMulti = cx.causes.reflection || cx.causes.diffraction;
  if (anyMulti) {
    cx.multiOnly = true;
    for (let j = 0; j < mz; j++) {
      Q[2] = z0 + (j - 0.5) * C2 + c / 2;
      for (let i = 0; i < mx; i++) { Q[0] = x0 + (i - 0.5) * C2 + c / 2; multi[j * mx + i] = evaluate(sc, cx, Q, false).multi; }
    }
    cx.multiOnly = false;
  }
  cx.multi = false;
  for (let j = 0; j < ny; j++) {
    const zq = z0 + (j + 0.5) * c;
    Q[2] = zq;
    const fz = (zq - (z0 + c / 2)) / C2 + 0.5, jz = Math.min(mz - 2, Math.floor(fz)), tz = fz - jz;
    for (let i = 0; i < nx; i++) {
      const xq = x0 + (i + 0.5) * c;
      Q[0] = xq;
      if (anyMulti) {
        const fx = (xq - (x0 + c / 2)) / C2 + 0.5, ix = Math.min(mx - 2, Math.floor(fx)), tx = fx - ix;
        const a = multi[jz * mx + ix], b = multi[jz * mx + ix + 1], d = multi[(jz + 1) * mx + ix], e = multi[(jz + 1) * mx + ix + 1];
        cx.extra = (a * (1 - tx) + b * tx) * (1 - tz) + (d * (1 - tx) + e * tx) * tz;
      }
      const r = evaluate(sc, cx, Q, false), k = j * nx + i;
      rssi[k] = r.rssi; snr[k] = r.snr; cause[k] = r.code; mbps[k] = speed(r.snr, cx.width);
    }
  }
  return { origin: [x0, z0], cell: c, nx, ny, rssi, snr, mbps, cause, band: cx.band };
}

/** -67 dBm 이상 면적이 가장 넓은 공유기 자리 k곳 (서로 1 m 넘게 떨어진). inside(xz)로 방 안만 본다 */
export function bestSpots(sc, router, opts = {}, k = 3) {
  const [x0, z0, x1, z1] = opts.bounds, inside = opts.inside || (() => true);
  const target = opts.target ?? -67, cand = opts.candStep ?? 0.6, probe = opts.probeStep ?? 0.5;
  const pts = [];
  for (let z = z0 + probe / 2; z < z1; z += probe) for (let x = x0 + probe / 2; x < x1; x += probe) if (inside([x, z])) pts.push([x, z]);
  const scored = [];
  const lean = { ...opts, causes: { ...(opts.causes || {}), reflection: false } }; // 후보 비교는 반사 없이 (빠르게)
  for (let z = z0 + cand / 2; z < z1; z += cand) for (let x = x0 + cand / 2; x < x1; x += cand) {
    if (!inside([x, z])) continue;
    const cx = context({ ...router, xz: [x, z] }, lean);
    let good = 0;
    const Q = [0, cx.rxH, 0];
    for (const p of pts) { Q[0] = p[0]; Q[2] = p[1]; if (evaluate(sc, cx, Q, false).rssi >= target) good++; }
    scored.push({ xz: [x, z], share: pts.length ? good / pts.length : 0 });
  }
  scored.sort((a, b) => b.share - a.share);
  const picked = [];
  for (const s of scored) {
    if (picked.every((p) => Math.hypot(p.xz[0] - s.xz[0], p.xz[1] - s.xz[1]) >= 1)) picked.push(s);
    if (picked.length === k) break;
  }
  return picked.map((s) => ({ xz: [Math.round(s.xz[0] * 100) / 100, Math.round(s.xz[1] * 100) / 100], share: Math.round(s.share * 1000) / 1000 }));
}
