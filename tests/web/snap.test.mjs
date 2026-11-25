// 벽·가전 옆에 붙이기 (apps/web/js/snap.js). 실행: node --test tests/web/
// 좌표: 평면 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°. 4 x 3 m 방, 벽 두께 0.1 (안쪽 면 0.05)
import test from "node:test";
import assert from "node:assert/strict";
import { snapPose } from "../../apps/web/js/snap.js";

const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
const UP = Math.PI / 2;
const walls = [[[0, 0], [4, 0]], [[4, 0], [4, 3]], [[4, 3], [0, 3]], [[0, 3], [0, 0]]].map(([start, end]) => ({ start, end, t: 0.1 }));
const C = [2, 1.5];
const cab = (xz, o = {}) => ({ xz, yaw: UP, w: 0.6, d: 0.6, side: 0, backOff: 0, ...o });

test("벽 가까이 가면 등을 벽에 붙이고 정면을 방 안으로 돌린다", () => {
  const r = snapPose(cab([2, 0.5], { yaw: 0 }), walls, [], C); // 등까지 0.15
  assert.ok(r.wall);
  assert.ok(near(r.xz[0], 2) && near(r.xz[1], 0.05 + 0.3));
  assert.ok(near(r.yaw, UP));
});

test("벽에서 멀면 그대로 둔다", () => {
  const r = snapPose(cab([2, 1.5], { yaw: 0.3 }), walls, [], C);
  assert.ok(!r.wall && near(r.xz[0], 2) && near(r.xz[1], 1.5) && near(r.yaw, 0.3));
});

test("가전은 뒤 여유만큼 띄워서 붙는다", () => {
  const r = snapPose(cab([2, 0.5], { backOff: 0.03 }), walls, [], C);
  assert.ok(near(r.xz[1], 0.05 + 0.03 + 0.3));
});

test("옆 가전에 붙을 때 가전이 요구하는 옆 여유를 남긴다", () => {
  // 냉장고: 가운데 1.0, 폭 0.9 → 오른쪽 면 1.45, 옆 4 mm. 장을 그 오른쪽 5 cm 떨어진 곳에 가져간다
  const fridge = { xz: [1.0, 0.4], yaw: UP, w: 0.9, d: 0.7, side: 0.004 };
  const r = snapPose(cab([1.45 + 0.05 + 0.3, 0.36]), walls, [fridge], C);
  assert.ok(r.side);
  assert.ok(near(r.xz[0], 1.45 + 0.004 + 0.3), `x=${r.xz[0]}`);
  assert.ok(near(r.xz[1], 0.35)); // 벽에도 붙었다
});

test("왼쪽에서도 같은 틈으로 붙는다", () => {
  const fridge = { xz: [2.0, 0.4], yaw: UP, w: 0.9, d: 0.7, side: 0.004 };
  const r = snapPose(cab([1.55 - 0.08 - 0.3, 0.36]), walls, [fridge], C);
  assert.ok(near(r.xz[0], 1.55 - 0.004 - 0.3), `x=${r.xz[0]}`);
});

test("옆에서 멀면 옆으로는 안 붙는다", () => {
  const fridge = { xz: [1.0, 0.4], yaw: UP, w: 0.9, d: 0.7, side: 0.004 };
  const r = snapPose(cab([2.5, 0.36]), walls, [fridge], C);
  assert.ok(!r.side && near(r.xz[0], 2.5));
});

test("구석에서는 옆 벽에도 붙는다", () => {
  const r = snapPose(cab([0.42, 0.4]), walls, [], C); // 왼쪽 면 0.12 → 벽 면 0.05
  assert.ok(near(r.xz[0], 0.05 + 0.3) && near(r.xz[1], 0.35));
});

test("방 가운데에서는 옆 가구의 방향과 등 선에 맞춘다", () => {
  const island = { xz: [2.0, 2.0], yaw: 0, w: 1.2, d: 0.6, side: 0 }; // 정면 +x, 폭 축 -y
  const r = snapPose(cab([2.03, 2.0 - 0.6 - 0.3 - 0.05], { yaw: 0.2 }), walls, [island], C);
  assert.ok(near(r.yaw, 0));
  assert.ok(near(r.xz[0], 2.0), `x=${r.xz[0]}`);            // 등 선 맞춤 (깊이가 같으니 가운데도 같다)
  assert.ok(near(r.xz[1], 2.0 - 0.6 - 0.3), `y=${r.xz[1]}`); // 옆면끼리 붙음
});

test("맞은편에 앞뒤로 떨어진 가구에는 붙지 않는다", () => {
  const far = { xz: [2.0, 2.6], yaw: -UP, w: 0.9, d: 0.7, side: 0 };
  const r = snapPose(cab([2.65, 0.36]), walls, [far], C);
  assert.ok(!r.side && near(r.xz[0], 2.65));
});

test("직접 돌려 둔 방향은 벽이 다시 돌려놓지 않는다: 옆면을 벽에 붙인다", () => {
  // 폭 0.9 깊이 0.7 냉장고를 옆으로 돌려(yaw 0) 아래 벽에 가져간다 → 방향은 그대로, 옆면이 옆 여유만큼 띄워 붙는다
  const r = snapPose({ xz: [2, 0.6], yaw: 0, w: 0.9, d: 0.7, side: 0.004, backOff: 0.03, keepYaw: true }, walls, [], C);
  assert.ok(r.wall && near(r.yaw, 0));
  assert.ok(near(r.xz[1], 0.05 + 0.004 + 0.45), `y=${r.xz[1]}`);
});

test("돌려 둔 것이 등을 벽 쪽으로 하고 있으면 전처럼 등을 붙인다", () => {
  const r = snapPose(cab([2, 0.5], { yaw: UP + 0.2, keepYaw: true, backOff: 0.03 }), walls, [], C);
  assert.ok(r.wall && near(r.yaw, UP) && near(r.xz[1], 0.05 + 0.03 + 0.3));
});

test("정면이 벽을 보게 돌려 둔 것도 그대로 둔다", () => {
  const r = snapPose(cab([2, 0.5], { yaw: -UP, keepYaw: true, backOff: 0.03 }), walls, [], C);
  assert.ok(r.wall && near(Math.abs(Math.atan2(Math.sin(r.yaw + UP), Math.cos(r.yaw + UP))), 0) && near(r.xz[1], 0.05 + 0.3));
});

test("비스듬히 돌려 둔 것은 벽에 붙이지 않는다", () => {
  const r = snapPose(cab([2, 0.5], { yaw: UP + Math.PI / 4, keepYaw: true }), walls, [], C);
  assert.ok(!r.wall && near(r.yaw, UP + Math.PI / 4) && near(r.xz[1], 0.5));
});

test("등을 벽에 대야 하는 제품은 옆으로 돌려 두면 벽에 붙지 않는다", () => {
  const r = snapPose(cab([2, 0.5], { yaw: 0, keepYaw: true, mustBack: true }), walls, [], C);
  assert.ok(!r.wall && near(r.yaw, 0) && near(r.xz[1], 0.5));
});

test("돌린 적 없는 것은 전처럼 정면을 방 안으로 돌린다", () => {
  const r = snapPose({ xz: [2, 0.6], yaw: 0, w: 0.9, d: 0.7, side: 0.004, backOff: 0.03 }, walls, [], C);
  assert.ok(r.wall && near(r.yaw, UP) && near(r.xz[1], 0.05 + 0.03 + 0.35));
});

