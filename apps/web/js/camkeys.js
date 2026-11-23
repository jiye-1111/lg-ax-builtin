// 키보드로 화면 움직이기: 키를 누르고 있는 동안 일정한 빠르기로 미끄러지듯 움직인다.
// (키가 반복 입력될 때마다 한 칸씩 뛰면 뚝뚝 끊겨 보인다)
export const PAN_M_S = 3.2;     // W A S D
export const TURN_DEG_S = 80;   // Q E
const EASE_PER_S = 9;           // 속도가 따라붙는 빠르기
const STOP = 0.01;

/** 누른 키 → 가려는 속도 [오른쪽 m/s, 앞 m/s, 돌기 도/s] */
export function wantVelocity(keys) {
  const axis = (plus, minus) => (keys[plus] ? 1 : 0) - (keys[minus] ? 1 : 0);
  return [axis("d", "a") * PAN_M_S, axis("w", "s") * PAN_M_S, axis("e", "q") * TURN_DEG_S];
}

/** 지금 속도를 가려는 속도 쪽으로 조금 옮긴다 */
export function ease(v, want, dt) {
  const k = Math.min(1, dt * EASE_PER_S);
  return v.map((x, i) => x + (want[i] - x) * k);
}

export const isMoving = (v) => Math.abs(v[0]) > STOP || Math.abs(v[1]) > STOP || Math.abs(v[2]) > STOP * 10;
