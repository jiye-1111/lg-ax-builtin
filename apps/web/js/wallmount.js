// 벽걸이 제품(벽걸이 TV·에어컨)을 벽에 건다. 마우스가 가리키는 벽 자리를 따라가고, 높이도 같이 따라온다.
// three.js 없이 배열만 쓴다. 판정과 저장할 때의 높이 맞추기는 서버(recommender/mount.py)가 같은 규칙으로 한다.
// 좌표: 평면 (x, y) = 3D (x, z), 높이 = 3D y. yaw = 정면 방향.
// walls: [{id, start, end, t(두께), h(높이), both}] · both = 양쪽 면 다 걸 수 있는 가벽. 스캔 벽은 방 안쪽 면에만 건다.
const TV_EYE_M = 1.1, AC_DROP_M = 0.15; // 서버 mount.py와 같은 값
const HOOD_BASE_M = 1.6; // 인덕션 없이 벽에 거는 후드의 밑면 높이 (서버 pose.py와 같은 값)
const STANDOFF_M = 0.0005; // 벽면에서 아주 조금 띄운다 (계산 오차로 벽에 박힌 것으로 보이지 않게)

const frame = (w, center) => {
  const dx = w.end[0] - w.start[0], dz = w.end[1] - w.start[1], L = Math.hypot(dx, dz);
  if (L < 1e-6) return null;
  const u = [dx / L, dz / L];
  let n = [-u[1], u[0]];
  const mid = [(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2];
  if (n[0] * (center[0] - mid[0]) + n[1] * (center[1] - mid[1]) < 0) n = [-n[0], -n[1]];
  return { u, n, L, mid };
};
const clamp = (v, lo, hi) => (hi < lo ? (lo + hi) / 2 : Math.min(Math.max(v, lo), hi));
const pose = (w, f, n, along, item) => {
  const a = clamp(along, item.w / 2 + w.t / 2, f.L - item.w / 2 - w.t / 2); // 모서리 옆 벽 두께만큼은 비운다
  const off = w.t / 2 + item.d / 2 + STANDOFF_M;
  return { xz: [w.start[0] + f.u[0] * a + n[0] * off, w.start[1] + f.u[1] * a + n[1] * off], yaw: Math.atan2(n[1], n[0]), wall: w.id };
};

// 스캔한 벽은 모서리가 딱 맞지 않는다: 건 자리가 옆 벽에 걸리면 벽을 따라 걸리지 않는 가장 가까운 자리로 민다
const SLIDE_M = 0.6, SLIDE_STEP_M = 0.02;
const box = (c, u, hw, hd) => ({ c, u, v: [-u[1], u[0]], hw, hd });
const apart = (a, b) => { // 두 사각형이 떨어져 있나 (맞닿기만 한 것도 떨어진 것)
  for (const ax of [a.u, a.v, b.u, b.v]) {
    const r = (q) => q.hw * Math.abs(q.u[0] * ax[0] + q.u[1] * ax[1]) + q.hd * Math.abs(q.v[0] * ax[0] + q.v[1] * ax[1]);
    if (Math.abs((b.c[0] - a.c[0]) * ax[0] + (b.c[1] - a.c[1]) * ax[1]) >= r(a) + r(b) - 1e-6) return true;
  }
  return false;
};
const settle = (r, walls, item) => {
  if (!r) return r;
  const u = [Math.sin(r.yaw), -Math.cos(r.yaw)];
  const rest = walls.filter((w) => w.id !== r.wall).map((w) => {
    const dx = w.end[0] - w.start[0], dz = w.end[1] - w.start[1], L = Math.hypot(dx, dz) || 1e-9;
    return box([(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2], [dx / L, dz / L], L / 2, w.t / 2);
  });
  for (let k = 0; k <= SLIDE_M / SLIDE_STEP_M; k++) {
    for (const s of k ? [k * SLIDE_STEP_M, -k * SLIDE_STEP_M] : [0]) {
      const c = [r.xz[0] + u[0] * s, r.xz[1] + u[1] * s];
      if (rest.every((b) => apart(box(c, u, item.w / 2, item.d / 2), b))) return { ...r, xz: c };
    }
  }
  return r;
};

export const clampBase = (base, h, ceiling) => Math.max(0, Math.min(base, ceiling - h));
/** 처음 걸 때의 밑면 높이 */
export const defaultBase = (category, h, ceiling) =>
  clampBase(category === "hood" ? HOOD_BASE_M : category === "air_conditioner" ? ceiling - AC_DROP_M - h : TV_EYE_M - h / 2, h, ceiling);

/** 광선(o 출발, d 방향)이 가리키는 벽 자리. item {w, h, d}. 벽을 안 가리키면 null */
export function hangAtRay(o, d, walls, item, center) {
  let best = null;
  for (const w of walls) {
    const f = frame(w, center);
    if (!f) continue;
    for (const n of w.both ? [f.n, [-f.n[0], -f.n[1]]] : [f.n]) {
      const facing = d[0] * n[0] + d[2] * n[1];
      if (facing > -1e-6) continue; // 등을 돌린 면
      const p0 = [f.mid[0] + (n[0] * w.t) / 2, f.mid[1] + (n[1] * w.t) / 2];
      const t = ((p0[0] - o[0]) * n[0] + (p0[1] - o[2]) * n[1]) / facing;
      if (t <= 0 || (best && t >= best.t)) continue;
      const hit = [o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t];
      const along = (hit[0] - w.start[0]) * f.u[0] + (hit[2] - w.start[1]) * f.u[1];
      if (along < 0 || along > f.L || hit[1] < 0 || hit[1] > w.h + 0.3) continue;
      if (f.L < item.w + w.t) continue; // 제품보다 짧은 벽(기둥 옆)에는 걸지 않는다
      best = { t, ...pose(w, f, n, along, item), base: clampBase(hit[1] - item.h / 2, item.h, w.h) };
    }
  }
  if (!best) return null;
  const { t, ...out } = best;
  return settle(out, walls, item);
}

/** 바닥 점에서 가장 가까운 벽에 건다 (높이는 부르는 쪽이 정한다). 벽이 없으면 null */
export function hangNear(xz, walls, item, center) {
  let best = null;
  const fits = (w) => Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]) >= item.w + w.t;
  const wide = walls.filter(fits); // 제품이 다 걸리는 벽부터. 하나도 없으면 가까운 벽
  for (const w of wide.length ? wide : walls) {
    const f = frame(w, center);
    if (!f) continue;
    const px = xz[0] - w.start[0], pz = xz[1] - w.start[1];
    const along = px * f.u[0] + pz * f.u[1], a = clamp(along, 0, f.L);
    const dist = Math.hypot(px - f.u[0] * a, pz - f.u[1] * a);
    if (best && dist >= best.dist) continue;
    const side = px * f.n[0] + pz * f.n[1];
    const n = w.both && side < 0 ? [-f.n[0], -f.n[1]] : f.n;
    best = { dist, ...pose(w, f, n, along, item), h: w.h };
  }
  if (!best) return null;
  const { dist, ...out } = best;
  return settle(out, walls, item);
}
