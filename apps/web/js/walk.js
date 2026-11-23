// 1인칭 둘러보기 순수 로직: 눈높이, 걷는 방향, 벽·가구·제품 충돌 (three.js 없이 계산만)
// 좌표: 평면 (x, y) = 3D (x, z). 카메라 yaw 0 = -z를 본다 (three.js 기본), 왼쪽으로 돌면 yaw가 커진다.
export const EYE_H = 1.6;     // 눈높이 (m)
export const RADIUS = 0.25;   // 몸 반지름 (m): 어깨 폭 절반쯤
export const WALK = 1.4;      // 걷는 빠르기 (m/s)
export const RUN = 2.6;       // Shift
const MAX_STEP = RADIUS / 3;  // 한 번에 이보다 길게 움직이면 잘게 나눈다 (벽 뚫기 방지)

/** 회전 상자: 가운데 c, 반폭 hw·반깊이 hd, 폭 축 u = (cos a, sin a). glb.py 회전 규칙과 같다. */
const obb = (c, w, d, a) => ({ c, hw: w / 2, hd: d / 2, u: [Math.cos(a), Math.sin(a)] });

/** room.json + 놓은 제품 + 치운 가구 id → 충돌용 세계 */
export function buildWorld(room, placements = [], hidden = []) {
  const gone = new Set(hidden || []);
  const walls = (room.walls || []).map((w) => ({ a: w.start, b: w.end, t: w.thickness_m || 0.1 }));
  const boxes = [];
  for (const o of room.objects || []) {
    if (gone.has(o.object_id)) continue;
    boxes.push({ id: o.object_id, ...obb([o.position[0], o.position[2]], o.bbox_m.w, o.bbox_m.d, o.yaw_rad || 0) });
  }
  for (const p of placements || []) {
    if (!p.size_m || !p.center_xz) continue;
    // 제품 yaw는 벽 안쪽 법선 방향 → 상자 회전은 yaw - 90° (glb.py와 같음)
    boxes.push({ id: p.placement_id, ...obb(p.center_xz, p.size_m[0], p.size_m[2], (p.yaw_rad || 0) - Math.PI / 2) });
  }
  const xs = walls.flatMap((w) => [w.a[0], w.b[0]]), ys = walls.flatMap((w) => [w.a[1], w.b[1]]);
  const bounds = xs.length ? [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] : [-5, -5, 5, 5];
  return { walls, boxes, bounds, poly: outline(room.walls || []) };
}

/** 벽을 이어 방 외곽 다각형을 만든다 (끝점이 이어지는 순서). 못 이으면 null */
function outline(walls) {
  if (walls.length < 3) return null;
  const left = walls.map((w) => [w.start, w.end]);
  const pts = [left[0][0], left[0][1]];
  left.splice(0, 1);
  const same = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 0.05;
  while (left.length) {
    const last = pts[pts.length - 1];
    const i = left.findIndex(([s, e]) => same(s, last) || same(e, last));
    if (i < 0) return null;
    const [s, e] = left.splice(i, 1)[0];
    pts.push(same(s, last) ? e : s);
  }
  return pts.slice(0, -1);
}

function insidePoly([x, y], poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [x1, y1] = poly[i], [x2, y2] = poly[j];
    if ((y1 > y) !== (y2 > y) && x < ((x2 - x1) * (y - y1)) / (y2 - y1) + x1) c = !c;
  }
  return c;
}

const segDist = ([px, py], [ax, ay], [bx, by]) => {
  const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy || 1e-9;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
};

/** 상자 가장자리까지 거리 (안이면 0) */
const boxDist = ([px, py], b) => {
  const rx = px - b.c[0], ry = py - b.c[1];
  const lu = rx * b.u[0] + ry * b.u[1], lv = -rx * b.u[1] + ry * b.u[0];
  const ex = Math.max(0, Math.abs(lu) - b.hw), ey = Math.max(0, Math.abs(lv) - b.hd);
  return Math.hypot(ex, ey);
};

/** 그 자리에 서 있을 수 없으면 true: 벽·가구·제품과 몸 반지름 안, 또는 방 밖 */
export function isBlocked(p, world, r = RADIUS) {
  const [x0, y0, x1, y1] = world.bounds;
  if (p[0] < x0 || p[0] > x1 || p[1] < y0 || p[1] > y1) return true;
  if (world.poly && !insidePoly(p, world.poly)) return true;
  for (const w of world.walls) if (segDist(p, w.a, w.b) < w.t / 2 + r) return true;
  for (const b of world.boxes) if (boxDist(p, b) < r) return true;
  return false;
}

/** 보는 방향 yaw와 누른 키 {f, b, l, r} → 이번 프레임 이동 [dx, dz] (대각선도 같은 빠르기) */
export function moveVector(yaw, keys, speed, dt) {
  const fwd = (keys.f ? 1 : 0) - (keys.b ? 1 : 0), side = (keys.r ? 1 : 0) - (keys.l ? 1 : 0);
  if (!fwd && !side) return [0, 0];
  const f = [-Math.sin(yaw), -Math.cos(yaw)], s = [Math.cos(yaw), -Math.sin(yaw)];
  let x = f[0] * fwd + s[0] * side, z = f[1] * fwd + s[1] * side;
  const n = Math.hypot(x, z);
  x = (x / n) * speed * dt;
  z = (z / n) * speed * dt;
  return [x + 0, z + 0]; // -0 → 0
}

/** p에서 d만큼 걷는다. 막히면 x·z를 따로 시도해 벽을 따라 미끄러진다. 길면 잘게 나눈다. */
export function step(p, d, world) {
  const n = Math.max(1, Math.ceil(Math.hypot(d[0], d[1]) / MAX_STEP));
  let [x, z] = p;
  const sx = d[0] / n, sz = d[1] / n;
  for (let i = 0; i < n; i++) {
    if (!isBlocked([x + sx, z + sz], world)) { x += sx; z += sz; continue; }
    if (sx && !isBlocked([x + sx, z], world)) x += sx;
    else if (sz && !isBlocked([x, z + sz], world)) z += sz;
    else break; // 막다른 곳
  }
  return [x, z];
}

const ROOMY = [0.8, 0.5, RADIUS]; // 처음 설 때 둘레에 두고 싶은 빈 거리 (m): 넓은 곳부터 찾고, 없으면 좁혀 간다
const SPAWN_GRID = 0.2;

/** 처음 서는 자리: 둘레가 트인 곳 가운데 방 가운데에서 가장 가까운 곳 (가구·제품 코앞에 서지 않는다) */
export function spawnPoint(world) {
  const [x0, y0, x1, y1] = world.bounds;
  const c = [(x0 + x1) / 2, (y0 + y1) / 2];
  for (const r of ROOMY) {
    if (!isBlocked(c, world, r)) return c;
    let best = null, bd = Infinity;
    for (let x = x0 + SPAWN_GRID; x < x1; x += SPAWN_GRID) {
      for (let y = y0 + SPAWN_GRID; y < y1; y += SPAWN_GRID) {
        if (isBlocked([x, y], world, r)) continue;
        const d = Math.hypot(x - c[0], y - c[1]);
        if (d < bd) { bd = d; best = [x, y]; }
      }
    }
    if (best) return best;
  }
  return c;
}
