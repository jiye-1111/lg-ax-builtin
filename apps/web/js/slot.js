// 장 칸에 끼워 넣기: 빌트인 가전을 들고 하부장·키큰장 줄에 가까이 가면 줄에 맞춘 자리를 돌려준다.
// 서버 recommender/slot.py와 같은 계산. 장을 실제로 자르는 것은 놓을 때 서버가 하고, 여기서는 끄는 동안 미리 보여 줄 모습(edits)만 낸다.
// 좌표: 평면 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°.
export const DOOR_BACK_M = { "decor:basecab": 0.02, "decor:sink": 0.02, "decor:island": 0.02, "decor:islandtable": 0.035, "decor:tallcab": 0 };
const SOLID_MIN_M = { "decor:sink": 0.6 }, SEAT_RATIO = { "decor:islandtable": 0.2 }, MIN_PIECE_M = 0.15;
export const UNDER_MAX_M = 1.0, REACH_M = 0.3, EDGE_M = 0.15;
const LINE_M = 0.03, YAW_RAD = (3 * Math.PI) / 180, STANDOFF_M = 0.0005;

const turn = (a) => Math.abs(Math.atan2(Math.sin(a), Math.cos(a)));
const frame = (c) => ({ u: [Math.cos(c.yaw - Math.PI / 2), Math.sin(c.yaw - Math.PI / 2)], f: [Math.cos(c.yaw), Math.sin(c.yaw)] });
const local = (c, p) => {
  const { u, f } = frame(c), dx = p[0] - c.xz[0], dy = p[1] - c.xz[1];
  return [dx * u[0] + dy * u[1], dx * f[0] + dy * f[1]];
};
const world = (c, a, b) => { const { u, f } = frame(c); return [c.xz[0] + u[0] * a + f[0] * b, c.xz[1] + u[1] * a + f[1] * b]; };
const doorOf = (c) => c.door ?? DOOR_BACK_M[c.sku];
const seatOf = (c) => c.d * (SEAT_RATIO[c.sku] || 0);
const v0 = (item, c) => {
  const door = doorOf(c), seat = seatOf(c);
  return item.d <= c.d - door - seat + 1e-9 ? c.d / 2 - door - item.d / 2 : -c.d / 2 + seat + (item.back || 0) + STANDOFF_M + item.d / 2;
};

/** item {w, h, d, side, back} · xz 놓으려는 자리 · cabinets [{id, sku, xz, yaw, w, h, d, keep, door}]
 *  → {xz, yaw, host, edits, cover} 또는 null.
 *  edits: 칸을 내주며 바뀌는 장 [{id, xz, w} | {id, remove: true} | {like, xz, w}] · cover: 위를 덮는 판 {top, depth, off, look, hex, seat} */
export function slotPose(item, xz, cabinets = []) {
  const hosts = cabinets.filter((c) => c.sku in DOOR_BACK_M && c.h + 1e-9 >= item.h && (c.h <= UNDER_MAX_M) === (item.h <= UNDER_MAX_M));
  const half = item.w / 2 + (item.side || 0) + STANDOFF_M;
  let best = null;
  for (const c of hosts) {
    const [u, v] = local(c, xz);
    const offV = Math.abs(v - v0(item, c)), gap = Math.abs(u) - c.w / 2 - half;
    if (offV > REACH_M || gap > EDGE_M) continue;
    const key = [Math.max(0, gap), offV];
    if (!best || key[0] < best.key[0] || (key[0] === best.key[0] && key[1] < best.key[1])) best = { key, c };
  }
  if (!best) return null;
  const host = best.c;
  const run = [];
  for (const c of hosts) {
    if (turn(c.yaw - host.yaw) > YAW_RAD) continue;
    const [u, v] = local(host, c.xz);
    if (Math.abs(v - c.d / 2 + host.d / 2) > LINE_M) continue;
    run.push({ a: u - c.w / 2, b: u + c.w / 2, c });
  }
  run.sort((p, q) => p.a - q.a);
  let s = local(host, xz)[0], shift = null;
  for (const r of run) for (const edge of [r.a, r.b]) for (const mine of [s - half, s + half]) {
    const d = edge - mine;
    if (Math.abs(d) <= EDGE_M && (shift === null || Math.abs(d) < Math.abs(shift) - 1e-9)) shift = d;
  }
  s += shift || 0;
  // 가를 수 없는 장(싱크대) 위라면 가까운 끝으로 비킨다
  for (const r of run) {
    const least = SOLID_MIN_M[r.c.sku];
    if (least === undefined || Math.min(r.b, s + half) - Math.max(r.a, s - half) <= 1e-4) continue;
    const ends = [r.a - half, r.b + half, ...(r.b - r.a - 2 * half >= least - 1e-9 ? [r.a + half, r.b - half] : [])];
    s = ends.reduce((p, q) => (Math.abs(q - s) < Math.abs(p - s) ? q : p));
    break;
  }
  const lo = s - half, hi = s + half, edits = [];
  let tall = null;
  for (const r of run) {
    const over = Math.min(r.b, hi) - Math.max(r.a, lo);
    if (over > -((item.side || 0) + 0.011) && (!tall || r.c.h > tall.h)) tall = r.c; // 옆에 붙은 장 가운데 가장 높은 것의 윗면으로 덮는다
    if (over <= 1e-4) continue;
    if (r.c.keep) return null; // 자를 수 없는 장(고정했거나 정수기가 든 장)
    const pieces = [[r.a, lo], [hi, r.b]].filter(([x, y]) => y - x >= MIN_PIECE_M);
    const least = SOLID_MIN_M[r.c.sku];
    if (least !== undefined && (pieces.length !== 1 || pieces[0][1] - pieces[0][0] < least - 1e-9)) return null;
    if (!pieces.length) { edits.push({ id: r.c.id, remove: true }); continue; }
    const v = local(host, r.c.xz)[1];
    pieces.forEach(([x, y], i) => edits.push({ [i ? "like" : "id"]: r.c.id, xz: world(host, (x + y) / 2, v), w: y - x }));
  }
  const at = v0(item, host);
  const cover = tall && tall.h - item.h >= 0.005
    ? { top: tall.h, depth: tall.d, off: local(host, tall.xz)[1] - at, look: tall.sku.split(":")[1], hex: tall.hex || null, seat: seatOf(tall) } : null;
  return { xz: world(host, s, at), yaw: host.yaw, host: host.id, edits, cover };
}
