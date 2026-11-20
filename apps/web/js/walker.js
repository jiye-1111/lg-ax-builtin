// 동선을 따라 걷는 사람: 경로 위 자리·방향·시간 (three.js 없이 계산만)
// 평면 (x, y) = 3D (x, z). heading = 3D y축 회전, 0이면 +z를 본다 (사람 모델 정면 +Z)

export const WALK_SPEED = 1.3; // m/s, 집 안 보통 걸음

export function pathLength(pts) {
  let s = 0;
  for (let i = 1; i < pts.length; i++) s += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return s;
}

const headingOf = (a, b) => Math.atan2(b[0] - a[0], b[1] - a[1]);

/** 경로 처음부터 s m 걸었을 때 자리와 바라보는 방향. 빈 경로면 null */
export function poseAt(pts, s) {
  if (!pts?.length) return null;
  if (pts.length === 1) return { xz: [...pts[0]], heading: 0 };
  let left = Math.max(0, s);
  let heading = 0;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < 1e-9) continue;
    heading = headingOf(a, b);
    if (left <= len) {
      const t = left / len;
      return { xz: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], heading };
    }
    left -= len;
  }
  return { xz: [...pts[pts.length - 1]], heading };
}

/** 경로 길이 length를 speed로 걷고 pause초 쉬었다가 처음부터 다시. 시각 t(초) → {s, moving} */
export function routeClock(length, { speed = WALK_SPEED, pause = 1.2 } = {}) {
  const walkT = length / speed, loop = walkT + pause;
  return (t) => {
    if (!(length > 0)) return { s: 0, moving: false };
    const u = ((t % loop) + loop) % loop;
    return u < walkT ? { s: u * speed, moving: true } : { s: length, moving: false };
  };
}
