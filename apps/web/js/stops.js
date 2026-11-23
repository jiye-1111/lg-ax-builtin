// 걸어 보기에서 들를 곳과 그 사이 길 (three.js 없이 계산만)
// 스캔에는 방 이름이 없어서, 문·창·큰 가구·놓은 가전을 보고 들를 곳을 정한다.
// 좌표: 평면 (x, y) = 3D (x, z). 카메라 yaw 0 = -z를 본다, 왼쪽으로 돌면 커진다 (walk.js와 같다).
import { EYE_H, RADIUS, isBlocked } from "./walk.js";
import { smoothPath } from "./walker.js";

const MAX_STOPS = 8;
const BODY = RADIUS + 0.1;        // 서는 자리 둘레에 두는 빈 거리 (m)
const DOOR_IN = 0.9;              // 문에서 안으로 들어와 서는 거리
const WINDOW_INS = [1.8, 1.2]; // 창에서 떨어져 서는 거리 (창틀이 다 보이게 넉넉한 곳부터)
const VIEW_GAPS = [2.2, 1.6, 1.2, 0.9, 0.6]; // 가구·가전을 볼 때 떨어져 서는 거리: 넉넉한 곳부터
const APART = 0.8;                // 들를 곳끼리 이보다 가까우면 하나만 남긴다
const NEAR_STOP = 1.0;            // 이 안에 서 있으면 그 곳에 있는 것으로 본다
const VISIT = ["sofa", "bed", "table"]; // 스캔 가구 가운데 들르는 종류 (종류마다 가장 큰 것 하나)
const CELL = 0.15, PATH_BODY = RADIUS + 0.05, MAX_CELLS = 40000;

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** from에 서서 to를 볼 때 카메라 yaw */
export const lookYaw = (from, to) => Math.atan2(-(to[0] - from[0]), -(to[1] - from[1])) + 0;

/** d만큼 떨어진 높이 h짜리 물건을 볼 때 고개 숙임 (음수 = 아래). 물건의 위쪽 3분의 1쯤을 본다 */
const PITCH_LEVEL = -0.06, PITCH_MAX = -0.5;
const lookPitch = (d, h) => Math.max(PITCH_MAX, Math.min(PITCH_LEVEL, -Math.atan2(EYE_H - Math.min(h * 0.65, 1.3), d) * 0.85));

/** p에서 가장 가까운 설 수 있는 자리. reach 안에 없으면 null */
export function nearFree(p, world, reach = 1.5, r = BODY) {
  if (!isBlocked(p, world, r)) return [...p];
  for (let d = 0.1; d <= reach + 1e-9; d += 0.1) {
    const n = Math.max(8, Math.round((2 * Math.PI * d) / 0.1));
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 2 * Math.PI, q = [p[0] + Math.cos(a) * d, p[1] + Math.sin(a) * d];
      if (!isBlocked(q, world, r)) return q;
    }
  }
  return null;
}

const SIGHT_H = 1.2; // 이보다 낮은 가구(의자·탁자)는 시야를 가리지 않는다
/** a에서 b 쪽을 볼 때 stop m 앞까지 키 큰 가구·제품·벽에 가리지 않는지 (10 cm 간격으로 본다) */
function sees(a, b, world, stop) {
  const d = dist(a, b), n = Math.ceil(Math.max(0, d - stop) / 0.1);
  for (let i = 1; i <= n; i++) {
    const t = (i * 0.1) / d;
    if (isBlocked([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], world, 0.05, SIGHT_H)) return false;
  }
  return true;
}

/** 벽에 난 문·창의 가운데와 방 안쪽을 향하는 단위 벡터 */
function openingPose(op, room, world) {
  const w = (room.walls || []).find((x) => x.wall_id === op.wall_id);
  if (!w) return null;
  const dx = w.end[0] - w.start[0], dy = w.end[1] - w.start[1], L = Math.hypot(dx, dy) || 1;
  const u = [dx / L, dy / L], at = (op.offset_m || 0) + (op.width_m || 0) / 2;
  const c = [w.start[0] + u[0] * at, w.start[1] + u[1] * at];
  const n = [-u[1], u[0]], probe = (s) => [c[0] + n[0] * s, c[1] + n[1] * s];
  const inward = !isBlocked(probe(0.5), world, 0.05) ? 1 : !isBlocked(probe(-0.5), world, 0.05) ? -1 : 0;
  return inward ? { c, n: [n[0] * inward, n[1] * inward] } : null;
}

/** 상자(가운데 c, 반지름쯤 half)를 보기 좋은 자리. 넉넉히 떨어진 곳부터 찾고, front가 있으면 정면에 가까운 쪽,
 *  없으면 방 가운데에 가까운 쪽. 이미 정한 곳(taken)과 겹치지 않게 한다 */
function viewSpot(c, half, world, mid, front, taken) {
  for (const gap of VIEW_GAPS) {
    const d = half + gap;
    let best = null, bs = -Infinity;
    for (let i = 0; i < 16; i++) {
      const a = (i / 16) * 2 * Math.PI, dir = [Math.cos(a), Math.sin(a)], q = [c[0] + dir[0] * d, c[1] + dir[1] * d];
      const facing = front ? dir[0] * front[0] + dir[1] * front[1] : 0;
      if (front && facing < 0.3) continue; // 옆이나 뒤에서 보지 않는다
      if (isBlocked(q, world, BODY) || taken.some((t) => dist(t, q) < APART)) continue;
      if (!sees(q, c, world, half + 0.15)) continue; // 사이에 다른 가구가 끼면 그것만 보인다
      const score = front ? facing : -dist(q, mid);
      if (score > bs + 1e-9) { bs = score; best = q; }
    }
    if (best) return best;
  }
  return null;
}

/**
 * 들를 곳 목록 [{ id, name, pos: [x, z], yaw, pitch }]. 현관에서 시작해 가까운 곳부터 돈다.
 * names = { objects: { sofa: "소파", … }, placement: (p) => "냉장고" | null }
 */
export function tourStops(room, placements, hidden, world, names = {}) {
  const gone = new Set(hidden || []);
  const [x0, y0, x1, y1] = world.bounds, mid = [(x0 + x1) / 2, (y0 + y1) / 2];
  const kept = [];
  const add = (id, name, pos, yaw, pitch = PITCH_LEVEL) => {
    if (!pos || !name || kept.length >= MAX_STOPS || kept.some((k) => k.name === name)) return;
    kept.push({ id, name, pos: [+pos[0].toFixed(3), +pos[1].toFixed(3)], yaw, pitch });
  };
  const taken = () => kept.map((k) => k.pos);

  // 중요한 것부터: 현관, 놓은 가전, 창, 큰 가구. 여덟 곳이 차면 그만 넣는다
  const ops = room.openings || [];
  const widest = (type) => ops.filter((o) => o.type === type).sort((a, b) => (b.width_m || 0) - (a.width_m || 0))[0];
  const door = widest("door") && openingPose(widest("door"), room, world);
  if (door) add("door", "현관", nearFree([door.c[0] + door.n[0] * DOOR_IN, door.c[1] + door.n[1] * DOOR_IN], world), lookYaw([0, 0], door.n));
  for (const p of placements || []) {
    const name = names.placement?.(p);
    if (!name || !p.center_xz || !p.size_m) continue;
    const front = [Math.cos(p.yaw_rad || 0), Math.sin(p.yaw_rad || 0)]; // 제품 yaw = 벽 안쪽 방향
    const pos = viewSpot(p.center_xz, p.size_m[2] / 2, world, mid, front, taken());
    if (pos) add(`pl:${p.placement_id}`, `${name} 앞`, pos, lookYaw(pos, p.center_xz), lookPitch(dist(pos, p.center_xz), p.size_m[1]));
  }
  const win = widest("window") && openingPose(widest("window"), room, world);
  if (win) {
    for (const back of WINDOW_INS) { // 창이 가려지지 않는 가장 넉넉한 자리. 없으면 창 앞은 들르지 않는다
      const pos = [win.c[0] + win.n[0] * back, win.c[1] + win.n[1] * back];
      if (isBlocked(pos, world, BODY) || !sees(pos, win.c, world, 0.3) || taken().some((t) => dist(t, pos) < APART)) continue;
      add("window", "창 앞", pos, lookYaw([0, 0], [-win.n[0], -win.n[1]]), 0);
      break;
    }
  }
  for (const cat of VISIT) {
    const o = (room.objects || []).filter((x) => x.category === cat && !gone.has(x.object_id))
      .sort((a, b) => b.bbox_m.w * b.bbox_m.d - a.bbox_m.w * a.bbox_m.d)[0];
    if (!o || !names.objects?.[cat]) continue;
    const c = [o.position[0], o.position[2]], pos = viewSpot(c, Math.min(o.bbox_m.w, o.bbox_m.d) / 2, world, mid, null, taken());
    if (pos) add(`obj:${o.object_id}`, `${names.objects[cat]} 앞`, pos, lookYaw(pos, c), lookPitch(dist(pos, c), o.bbox_m.h));
  }
  if (!kept.length) {
    const pos = nearFree(mid, world, Math.max(x1 - x0, y1 - y0)) || mid;
    return [{ id: "mid", name: "방 가운데", pos, yaw: 0, pitch: PITCH_LEVEL }];
  }
  // 첫 곳에서 시작해 가까운 곳부터
  const order = [kept.shift()];
  while (kept.length) {
    const last = order[order.length - 1].pos;
    let bi = 0;
    for (let i = 1; i < kept.length; i++) if (dist(kept[i].pos, last) < dist(kept[bi].pos, last)) bi = i;
    order.push(kept.splice(bi, 1)[0]);
  }
  return order;
}

/** 지금 선 자리 p가 어느 들를 곳인지 (없으면 -1) */
export function nearestStop(stops, p) {
  let bi = -1, bd = NEAR_STOP;
  stops.forEach((s, i) => { const d = dist(s.pos, p); if (d < bd) { bd = d; bi = i; } });
  return bi;
}

/** a에서 b까지 벽·가구·제품을 피해 걷는 길 (부드럽게 편 점들). 갈 수 없으면 null */
export function findPath(a, b, world) {
  const [x0, y0, x1, y1] = world.bounds;
  const nx = Math.ceil((x1 - x0) / CELL) + 1, ny = Math.ceil((y1 - y0) / CELL) + 1;
  if (nx * ny > MAX_CELLS) return null;
  const at = (i, j) => [x0 + i * CELL, y0 + j * CELL];
  const free = new Int8Array(nx * ny).fill(-1); // -1 아직 모름
  const ok = (i, j) => {
    if (i < 0 || j < 0 || i >= nx || j >= ny) return false;
    const k = j * nx + i;
    if (free[k] < 0) free[k] = isBlocked(at(i, j), world, PATH_BODY) ? 0 : 1;
    return free[k] === 1;
  };
  const cellNear = (p) => {
    const ci = Math.round((p[0] - x0) / CELL), cj = Math.round((p[1] - y0) / CELL);
    for (let r = 0; r <= 4; r++)
      for (let i = ci - r; i <= ci + r; i++) for (let j = cj - r; j <= cj + r; j++)
        if (Math.max(Math.abs(i - ci), Math.abs(j - cj)) === r && ok(i, j)) return [i, j];
    return null;
  };
  const s = cellNear(a), g = cellNear(b);
  if (!s || !g) return null;
  const key = (c) => c[1] * nx + c[0], goal = key(g);
  const cost = new Float32Array(nx * ny).fill(Infinity), from = new Int32Array(nx * ny).fill(-1);
  const open = [[0, key(s)]];
  cost[key(s)] = 0;
  const h = (k) => Math.hypot((k % nx) - g[0], Math.floor(k / nx) - g[1]);
  while (open.length) {
    let mi = 0;
    for (let i = 1; i < open.length; i++) if (open[i][0] < open[mi][0]) mi = i;
    const [, k] = open.splice(mi, 1)[0];
    if (k === goal) break;
    const i = k % nx, j = Math.floor(k / nx);
    for (let di = -1; di <= 1; di++) for (let dj = -1; dj <= 1; dj++) {
      if (!di && !dj) continue;
      if (!ok(i + di, j + dj)) continue;
      if (di && dj && (!ok(i + di, j) || !ok(i, j + dj))) continue; // 모서리를 비스듬히 뚫지 않는다
      const nk = (j + dj) * nx + i + di, c = cost[k] + Math.hypot(di, dj);
      if (c < cost[nk]) { cost[nk] = c; from[nk] = k; open.push([c + h(nk), nk]); }
    }
  }
  if (cost[goal] === Infinity) return null;
  const cells = [];
  for (let k = goal; k >= 0; k = from[k]) cells.push(at(k % nx, Math.floor(k / nx)));
  cells.reverse();
  return smoothPath([[...a], ...cells, [...b]]);
}
