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

/** 경로 길이 length를 speed로 걷고 pause초 쉬었다가 처음부터 다시. 시각 t(초) → {s, moving, v}
 *  ease(초): 출발할 때 그만큼 걸려 보통 빠르기가 되고, 도착 전에도 그만큼 감속한다 (0이면 바로 출발·정지) */
export function routeClock(length, { speed = WALK_SPEED, pause = 1.2, ease = 0, roundTrip = false } = {}) {
  const e = Math.min(ease, length / speed), walkT = length / speed + e, loop = walkT + pause;
  const oneWay = oneWayClock(length, speed, e, walkT, loop);
  if (!roundTrip) return oneWay;
  // 왕복: 끝에서 쉬고 돌아서 걸어온다 (처음 자리로 순간 이동하지 않는다). dir = 가는 쪽(+1)·오는 쪽(-1), 쉴 때는 다음에 갈 쪽
  return (t) => {
    if (!(length > 0)) return { ...oneWay(t), dir: 1 };
    const u = ((t % (2 * loop)) + 2 * loop) % (2 * loop), back = u >= loop, leg = oneWay(back ? u - loop : u);
    const dir = (back ? -1 : 1) * (leg.moving ? 1 : -1);
    return { s: back ? length - leg.s : leg.s, moving: leg.moving, v: leg.v, dir };
  };
}

function oneWayClock(length, speed, e, walkT, loop) {
  return (t) => {
    if (!(length > 0)) return { s: 0, moving: false, v: 0 };
    const u = ((t % loop) + loop) % loop;
    if (u >= walkT) return { s: length, moving: false, v: 0 };
    if (e > 0 && u < e) return { s: 0.5 * speed * u * u / e, moving: true, v: speed * u / e };
    if (e > 0 && u > walkT - e) { const r = walkT - u; return { s: length - 0.5 * speed * r * r / e, moving: true, v: speed * r / e }; }
    return { s: speed * (u - e / 2), moving: true, v: speed };
  };
}

const STEP_M = 0.1, SMOOTH_M = 0.4; // 다시 고르는 간격, 앞뒤로 평균 내는 거리

/** 길찾기 격자 경로(5~10 cm 계단)를 사람이 걷는 선처럼 편다: 고르게 다시 찍고 앞뒤 평균. 양 끝은 그대로 */
export function smoothPath(pts) {
  if (!pts || pts.length < 3) return pts ? pts.map((p) => [...p]) : [];
  const len = pathLength(pts), n = Math.max(2, Math.round(len / STEP_M));
  const even = [];
  for (let i = 0; i <= n; i++) even.push(poseAt(pts, (len * i) / n).xz);
  const k = Math.max(1, Math.round(SMOOTH_M / (len / n)));
  let cur = even;
  for (let pass = 0; pass < 2; pass++) {
    cur = cur.map((p, i) => {
      if (i === 0 || i === cur.length - 1) return p;
      const r = Math.min(k, i, cur.length - 1 - i); // 끝에 가까우면 창을 줄여 끝점이 끌려가지 않게
      let x = 0, y = 0;
      for (let j = i - r; j <= i + r; j++) { x += cur[j][0]; y += cur[j][1]; }
      return [x / (2 * r + 1), y / (2 * r + 1)];
    });
  }
  cur[0] = [...pts[0]];
  cur[cur.length - 1] = [...pts[pts.length - 1]];
  return cur;
}
