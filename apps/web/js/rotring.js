// 회전 고리: 고른 물건 둘레 바닥에 고리를 깔고 손잡이를 끌어 돌린다 (Planner 5D·Houzz처럼).
// 각도는 3D y 회전(라디안) 기준. 커서가 가는 쪽으로 물건이 같이 돈다.

export const SNAP_RAD = Math.PI / 4;     // 45°마다
export const MAGNET_RAD = Math.PI / 30;  // 6° 안으로 오면 착 붙는다
export const FINE_RAD = Math.PI / 12;    // Shift: 15°씩
const RING_GAP_M = 0.18, RING_MIN_M = 0.35, RING_MAX_M = 2.8;

/** 가운데 c에서 본 바닥 점 p 쪽 각도 (3D rotation.y와 같은 쪽: +z가 0, +x가 90°) */
export const pointerAngle = (c, p) => Math.atan2(p[0] - c[0], p[1] - c[1]);

/** 잡은 순간의 물건 회전(rot)과 커서 각도(grab)에서, 지금 커서 각도(now)일 때의 물건 회전 */
export const turnTo = ({ rot, grab }, now) => rot + (now - grab);

/** 45° 근처면 붙이고, fine이면 15°씩, free(Alt)면 붙지 않는다 */
export const snapTurn = (a, { fine = false, free = false } = {}) => {
  if (free) return a;
  if (fine) return Math.round(a / FINE_RAD) * FINE_RAD;
  const s = Math.round(a / SNAP_RAD) * SNAP_RAD;
  return Math.abs(a - s) < MAGNET_RAD ? s : a;
};

/** 바닥에서 본 물건 크기(m)로 고리 반지름 */
export const ringRadius = (w, d) => Math.min(RING_MAX_M, Math.max(RING_MIN_M, Math.hypot(w, d) / 2 + RING_GAP_M));

/** 화면에 띄울 각도 글자 */
export const degLabel = (a) => `${((Math.round((a * 180) / Math.PI) % 360) + 360) % 360}°`;
