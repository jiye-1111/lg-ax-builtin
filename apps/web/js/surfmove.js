// 위에 올린 물건(책상 위 정수기 등)을 끌 때 쓰는 계산. three.js 없이 배열만 쓴다
/** 광선(o 출발, d 방향)이 높이 h인 수평면과 만나는 바닥 좌표 [x, z]. 앞쪽에서 안 만나면 null */
export const onPlane = (o, d, h) => {
  if (Math.abs(d[1]) < 1e-6) return null;
  const t = (h - o[1]) / d[1];
  return t > 0 ? [o[0] + t * d[0], o[2] + t * d[2]] : null;
};
/** 물건 가운데 - 누른 점. 누른 점이 없으면 가운데를 잡은 것으로 본다 */
export const grabOffset = (center, at) => (at ? [center[0] - at[0], center[1] - at[1]] : [0, 0]);
