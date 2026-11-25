// 장 칸에 끼워 넣기: 빌트인 가전을 들고 하부장·키큰장 줄에 가까이 가면 줄에 맞춘 자리를 돌려준다.
// 서버 recommender/slot.py와 같은 계산 (자리만. 장을 자르는 것은 놓을 때 서버가 한다).
// 좌표: 평면 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°.
export const DOOR_BACK_M = { "decor:basecab": 0.02, "decor:tallcab": 0 };
export const UNDER_MAX_M = 1.0, REACH_M = 0.3, EDGE_M = 0.15;
const LINE_M = 0.03, YAW_RAD = (3 * Math.PI) / 180, STANDOFF_M = 0.0005;

const turn = (a) => Math.abs(Math.atan2(Math.sin(a), Math.cos(a)));
const frame = (c) => ({ u: [Math.cos(c.yaw - Math.PI / 2), Math.sin(c.yaw - Math.PI / 2)], f: [Math.cos(c.yaw), Math.sin(c.yaw)] });
const local = (c, p) => {
  const { u, f } = frame(c), dx = p[0] - c.xz[0], dy = p[1] - c.xz[1];
  return [dx * u[0] + dy * u[1], dx * f[0] + dy * f[1]];
};
const world = (c, a, b) => { const { u, f } = frame(c); return [c.xz[0] + u[0] * a + f[0] * b, c.xz[1] + u[1] * a + f[1] * b]; };
const v0 = (item, c) => {
  const door = DOOR_BACK_M[c.sku];
  return item.d <= c.d - door + 1e-9 ? c.d / 2 - door - item.d / 2 : -c.d / 2 + (item.back || 0) + STANDOFF_M + item.d / 2;
};

/** item {w, h, d, side, back} · xz 놓으려는 자리 · cabinets [{id, sku, xz, yaw, w, h, d, keep}] → {xz, yaw, host} 또는 null */
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
  // 자를 수 없는 장(고정했거나 정수기가 든 장)과 겹치면 끼우지 않는다
  if (run.some((r) => r.c.keep && Math.min(r.b, s + half) - Math.max(r.a, s - half) > 1e-4)) return null;
  return { xz: world(host, s, v0(item, host)), yaw: host.yaw, host: host.id };
}
