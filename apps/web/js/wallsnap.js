// 벽 그리기: Shift를 누르고 있으면 반듯하게 맞춘다.
// 방향은 기존 벽과 나란하거나 직각, 길이는 5 cm 단위, 끝이 다른 벽 가까이 가면 그 벽에 붙는다.
const STEP_M = 0.05;      // 길이 단위
const REACH_M = 0.25;     // 이 안에 벽이 있으면 붙는다

const angleOf = (w) => Math.atan2(w.end[1] - w.start[1], w.end[0] - w.start[0]);
const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));

/** 끌던 방향에 가장 가까운 '벽과 나란하거나 직각'인 방향 */
function nearestDirection(ang, walls) {
  const bases = walls.length ? walls.map(angleOf) : [0];
  let best = ang, gap = Infinity;
  for (const b of bases)
    for (let k = 0; k < 4; k++) {
      const cand = b + (k * Math.PI) / 2, d = Math.abs(wrap(ang - cand));
      if (d < gap) { gap = d; best = cand; }
    }
  return best;
}

/** from에서 dir 방향으로 나갈 때 벽 w를 만나는 거리 (안 만나면 null) */
function hitDistance(from, dir, w) {
  const ex = w.end[0] - w.start[0], ez = w.end[1] - w.start[1];
  const det = dir[0] * -ez + ex * dir[1];
  if (Math.abs(det) < 1e-9) return null;
  const sx = w.start[0] - from[0], sz = w.start[1] - from[1];
  const t = (sx * -ez + ex * sz) / det, u = (dir[0] * sz - dir[1] * sx) / det;
  return t > 0 && u >= -0.02 && u <= 1.02 ? t : null;
}

/** 시작점 a에서 마우스 p까지 끌 때, 반듯하게 맞춘 끝점 */
export function straighten(a, p, walls) {
  const ang = nearestDirection(Math.atan2(p[1] - a[1], p[0] - a[0]), walls), dir = [Math.cos(ang), Math.sin(ang)];
  const along = (p[0] - a[0]) * dir[0] + (p[1] - a[1]) * dir[1];
  let len = Math.round(along / STEP_M) * STEP_M;
  for (const w of walls) {
    const t = hitDistance(a, dir, w);
    if (t !== null && Math.abs(t - along) <= REACH_M) { len = t; break; }
  }
  return [a[0] + dir[0] * len, a[1] + dir[1] * len];
}

/** 시작점이 벽 가까이면 벽 위로 옮긴다 */
export function snapStart(p, walls) {
  let best = p, gap = REACH_M;
  for (const w of walls) {
    const ex = w.end[0] - w.start[0], ez = w.end[1] - w.start[1], l2 = ex * ex + ez * ez;
    if (!l2) continue;
    const t = Math.max(0, Math.min(1, ((p[0] - w.start[0]) * ex + (p[1] - w.start[1]) * ez) / l2));
    const q = [w.start[0] + ex * t, w.start[1] + ez * t], d = Math.hypot(p[0] - q[0], p[1] - q[1]);
    if (d < gap) { gap = d; best = q; }
  }
  return best;
}
