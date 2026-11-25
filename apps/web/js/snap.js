// 벽·가전 옆에 착 붙이기. 화면에서 바로 계산해서 들고 다니는 동안 끊기지 않게 한다 (판정은 서버가 따로 한다).
// 좌표: 평면 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°.
//  - 벽: 등이 벽 가까이 오면 정면을 방 안으로 돌리고 등을 벽에 붙인다 (가전은 뒤 여유 backOff만큼 띄운다)
//    직접 돌려 둔 것(keepYaw)은 돌려놓지 않는다: 벽과 직각·나란한 방향이면 그 방향 그대로 벽 쪽 면만 붙이고, 비스듬하면 안 붙인다
//    등을 벽에 대야 설치되는 제품(mustBack)은 등이 벽을 볼 때만 붙는다
//  - 옆: 나란히 선 가전·장·옆 벽에 가까이 가면 옆면을 맞댄다. 가전이 요구하는 옆 여유(side)는 남긴다
//  - 방 가운데: 옆 가구와 방향이 비슷하면 방향과 등 선(안 되면 앞 선)을 맞춘다
export const SNAP_WALL_M = 0.2, SNAP_SIDE_M = 0.12, SNAP_YAW = (20 * Math.PI) / 180;
const SQUARE = (5 * Math.PI) / 180;

const axes = (yaw) => ({ u: [Math.sin(yaw), -Math.cos(yaw)], v: [Math.cos(yaw), Math.sin(yaw)] });
const angDiff = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));
const corners = (c, ux, hw, hd) => {
  const vx = [-ux[1], ux[0]];
  return [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([a, b]) => [c[0] + ux[0] * a + vx[0] * b, c[1] + ux[1] * a + vx[1] * b]);
};

/** item {xz, yaw, w, d, side, backOff, keepYaw, mustBack, reach(벽에 끌려가는 거리, 없으면 SNAP_WALL_M)} · walls [{start, end, t}] · others [{xz, yaw, w, d, side}] · center = 방 가운데 */
export function snapPose(item, walls = [], others = [], center = [0, 0]) {
  let [x, y] = item.xz, yaw = item.yaw;
  const { w, d } = item, side = item.side || 0, backOff = item.backOff || 0;
  const reach = item.reach ?? SNAP_WALL_M;
  let wall = false, sideHit = false;

  // 1) 벽
  let best = null;
  for (const wl of walls) {
    const dx = wl.end[0] - wl.start[0], dy = wl.end[1] - wl.start[1], L = Math.hypot(dx, dy);
    if (L < 1e-6) continue;
    const ux = [dx / L, dy / L];
    let n = [-ux[1], ux[0]];
    const mid = [(wl.start[0] + wl.end[0]) / 2, (wl.start[1] + wl.end[1]) / 2];
    if (n[0] * (center[0] - mid[0]) + n[1] * (center[1] - mid[1]) < 0) n = [-n[0], -n[1]];
    const along = (x - wl.start[0]) * ux[0] + (y - wl.start[1]) * ux[1];
    if (along < 0 || along > L) continue;
    const dist = (x - wl.start[0]) * n[0] + (y - wl.start[1]) * n[1];
    const nAng = Math.atan2(n[1], n[0]);
    let face = nAng, half = d / 2, keep = backOff;
    if (item.keepYaw) { // 직접 돌려 둔 방향은 지킨다: 가장 가까운 직각 방향으로만 맞춘다
      const q = [0, Math.PI / 2, -Math.PI / 2, Math.PI].find((k) => angDiff(nAng + k, yaw) <= SNAP_YAW);
      if (q === undefined || (item.mustBack && q !== 0)) continue;
      face = nAng + q;
      if (Math.abs(q) === Math.PI / 2) { half = w / 2; keep = side; } // 옆면이 벽을 본다
      else if (q === Math.PI) keep = 0;                              // 정면이 벽을 본다
    }
    const gap = dist - wl.t / 2 - half - keep;
    if (dist <= 0 || gap > reach) continue;
    if (!best || gap < best.gap) best = { gap, n, face, off: wl.t / 2 + keep + half, foot: [wl.start[0] + ux[0] * along, wl.start[1] + ux[1] * along] };
  }
  if (best) {
    x = best.foot[0] + best.n[0] * best.off; y = best.foot[1] + best.n[1] * best.off;
    yaw = best.face;
    wall = true;
  }

  // 2) 방 가운데: 가까운 가구의 방향과 등 선
  if (!wall) {
    const mate = others
      .filter((o) => angDiff(o.yaw, yaw) < SNAP_YAW && Math.hypot(o.xz[0] - x, o.xz[1] - y) < Math.max(w, d) / 2 + Math.max(o.w, o.d) / 2 + 0.3)
      .sort((a, b) => Math.hypot(a.xz[0] - x, a.xz[1] - y) - Math.hypot(b.xz[0] - x, b.xz[1] - y))[0];
    if (mate) {
      yaw = mate.yaw;
      const { v } = axes(yaw);
      const rel = (mate.xz[0] - x) * v[0] + (mate.xz[1] - y) * v[1]; // 내 기준 앞뒤로 그 가구 가운데까지
      const back = rel - mate.d / 2 + d / 2, front = rel + mate.d / 2 - d / 2;
      const sh = Math.abs(back) <= SNAP_SIDE_M ? back : Math.abs(front) <= SNAP_SIDE_M ? front : 0;
      x += v[0] * sh; y += v[1] * sh;
    }
  }

  // 3) 옆: 나란한 것들(벽 포함)의 옆면
  const { u, v } = axes(yaw);
  const boxes = [
    ...walls.map((wl) => {
      const dx = wl.end[0] - wl.start[0], dy = wl.end[1] - wl.start[1], L = Math.hypot(dx, dy) || 1e-9;
      return { ang: Math.atan2(dy, dx), pts: corners([(wl.start[0] + wl.end[0]) / 2, (wl.start[1] + wl.end[1]) / 2], [dx / L, dy / L], L / 2, wl.t / 2), need: side };
    }),
    ...others.map((o) => ({ ang: o.yaw - Math.PI / 2, pts: corners(o.xz, axes(o.yaw).u, o.w / 2, o.d / 2), need: Math.max(side, o.side || 0) })),
  ];
  const mine = yaw - Math.PI / 2;
  let shift = null;
  for (const b of boxes) {
    const q = angDiff(b.ang * 2, mine * 2) / 2; // 90° 단위로 나란한지
    if (Math.min(q, Math.PI / 2 - q) > SQUARE) continue;
    const lu = b.pts.map((p) => (p[0] - x) * u[0] + (p[1] - y) * u[1]), lv = b.pts.map((p) => (p[0] - x) * v[0] + (p[1] - y) * v[1]);
    const minU = Math.min(...lu), maxU = Math.max(...lu), minV = Math.min(...lv), maxV = Math.max(...lv);
    if (maxV < -d / 2 + 0.01 || minV > d / 2 - 0.01) continue; // 앞뒤로 비켜 있다
    const cu = (minU + maxU) / 2;
    const s = cu > 0 ? minU - w / 2 - b.need : maxU + w / 2 + b.need; // 이만큼 옮기면 딱 붙는다
    if (Math.abs(s) <= SNAP_SIDE_M && (shift === null || Math.abs(s) < Math.abs(shift))) shift = s;
  }
  if (shift !== null) { x += u[0] * shift; y += u[1] * shift; sideHit = true; }
  return { xz: [x, y], yaw, wall, side: sideHit };
}
