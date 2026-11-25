// 장 끝을 끌어 늘리기: 반대쪽 끝은 그대로 두고 잡은 끝만 움직인다. 벽이나 옆 가구에 가까워지면 딱 닿게 멈춘다.
// 좌표: 평면 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°.
export const STRETCH_SNAP_M = 0.08, STRETCH_STEP_M = 0.01, HANDLE_OUT_M = 0.16;

const axis = (yaw, side) => [Math.cos(yaw - Math.PI / 2) * side, Math.sin(yaw - Math.PI / 2) * side];

/** 잡지 않은 쪽 끝 (늘여도 안 움직이는 점) */
export const anchorOf = (item, side) => { const u = axis(item.yaw, side); return [item.xz[0] - (u[0] * item.w) / 2, item.xz[1] - (u[1] * item.w) / 2]; };

/** 바닥 점 p가 안 움직이는 끝에서 잡은 끝 쪽으로 얼마나 떨어져 있나 */
export const reachOf = (item, side, p) => { const u = axis(item.yaw, side), a = anchorOf(item, side); return (p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1]; };

/** item {xz, yaw, w, d} · side 잡은 끝(폭 축 +1/-1) · want 바라는 길이 · stops [{pts: 꼭짓점들, pad: 띄울 거리}]
 *  → {w, xz, hit: 닿은 것이 있으면 true}. free면 맞추지 않는다 */
export function stretchTo(item, side, want, stops = [], { min = 0.1, max = 8, free = false } = {}) {
  const u = axis(item.yaw, side), a = anchorOf(item, side), v = [-u[1], u[0]];
  let len = want, hit = false;
  if (!free) {
    let best = null;
    for (const s of stops) {
      const loc = s.pts.map((p) => [(p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1], (p[0] - a[0]) * v[0] + (p[1] - a[1]) * v[1]]);
      const lo = Math.min(...loc.map((q) => q[1])), hi = Math.max(...loc.map((q) => q[1]));
      if (hi <= -item.d / 2 + 0.01 || lo >= item.d / 2 - 0.01) continue; // 옆으로 비켜 있다
      const at = Math.min(...loc.map((q) => q[0])) - (s.pad || 0);
      if (at < min - 1e-9) continue; // 뒤쪽이거나 이미 겹친 것
      if (Math.abs(want - at) <= STRETCH_SNAP_M && (best === null || Math.abs(want - at) < Math.abs(want - best))) best = at;
    }
    if (best !== null) { len = best; hit = true; }
    else len = Math.round(want / STRETCH_STEP_M) * STRETCH_STEP_M;
  }
  len = Math.min(max, Math.max(min, len));
  return { w: len, xz: [a[0] + (u[0] * len) / 2, a[1] + (u[1] * len) / 2], hit };
}

// 끌어서 늘릴 수 있는 가구. 장·가벽은 양옆으로, 벽에서 떨어져 쓰는 것(아일랜드·식탁·테이블·소파·침대·러그)은 앞뒤로도 늘린다.
// 책상은 숫자 입력만 쓴다. 의자·조명·식물처럼 늘려서 쓸 일이 없는 것, 벽에 다는 문·창·후드도 뺀다.
const LONG = new Set(["decor:wall", "decor:partition"]);
const DEEP = new Set(["decor:island", "decor:islandtable", "decor:table", "decor:coffee", "decor:sofa", "decor:bed", "decor:rug"]);
const FIXED = new Set(["decor:desk", "decor:hood", "decor:islandhood"]);

/** sku와 가구 묶음(group) → 손잡이가 없으면 null, 있으면 {deep: 앞뒤 손잡이도 있는지} */
export function handlesFor(sku, group) {
  if (!String(sku || "").startsWith("decor:") || FIXED.has(sku)) return null;
  if (DEEP.has(sku)) return { deep: true };
  return group === "storage" || LONG.has(sku) ? { deep: false } : null;
}
