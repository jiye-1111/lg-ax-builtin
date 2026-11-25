// 벽걸이 제품을 벽에 거는 계산 (apps/web/js/wallmount.js). 실행: node --test tests/web/
// 좌표: 평면 (x, y) = 3D (x, z), 높이는 3D y. 4 x 3 m 방, 벽 두께 0.1 (안쪽 면 0.05), 천장 2.4
import test from "node:test";
import assert from "node:assert/strict";
import { hangAtRay, hangNear, defaultBase } from "../../apps/web/js/wallmount.js";

const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
const UP = Math.PI / 2;
const walls = [[[0, 0], [4, 0]], [[4, 0], [4, 3]], [[4, 3], [0, 3]], [[0, 3], [0, 0]]]
  .map(([start, end], i) => ({ id: `w${i + 1}`, start, end, t: 0.1, h: 2.4 }));
const C = [2, 1.5];
const tv = { w: 1.4, h: 0.8, d: 0.05 };
// 방 안 (2, 1.6, 2.5)에서 벽 w1(z=0)의 한 점을 바라보는 광선
const rayTo = (from, to) => { const d = to.map((v, i) => v - from[i]); const L = Math.hypot(...d); return [from, d.map((v) => v / L)]; };

test("벽을 가리키면 그 자리에 등을 붙이고 가리킨 높이에 가운데가 온다", () => {
  const [o, d] = rayTo([2, 1.6, 2.5], [2.5, 1.2, 0.05]);
  const r = hangAtRay(o, d, walls, tv, C);
  assert.equal(r.wall, "w1");
  assert.ok(near(r.xz[0], 2.5) && near(r.xz[1], 0.05 + 0.025, 1e-3));
  assert.ok(near(r.yaw, UP));
  assert.ok(near(r.base, 1.2 - 0.4));
});

test("천장과 바닥을 넘지 않는다", () => {
  let [o, d] = rayTo([2, 1.6, 2.5], [2, 2.35, 0.05]);
  assert.ok(near(hangAtRay(o, d, walls, tv, C).base, 2.4 - 0.8));
  [o, d] = rayTo([2, 1.6, 2.5], [2, 0.1, 0.05]);
  assert.ok(near(hangAtRay(o, d, walls, tv, C).base, 0));
});

test("벽 끝을 넘지 않게 당긴다", () => {
  const [o, d] = rayTo([2, 1.6, 2.5], [0.2, 1.2, 0.05]);
  const r = hangAtRay(o, d, walls, tv, C);
  assert.ok(near(r.xz[0], 0.05 + 0.7));
});

test("방 밖에서 보면 가까운 벽을 지나 건너편 벽에 건다", () => {
  const [o, d] = rayTo([2, 3, -4], [2, 1.2, 2.95]); // w1 바깥에서 w3 안쪽 면을 본다
  const r = hangAtRay(o, d, walls, tv, C);
  assert.equal(r.wall, "w3");
  assert.ok(near(r.xz[1], 2.95 - 0.025, 1e-3) && near(r.yaw, -UP));
});

test("바닥을 가리키면 벽을 못 찾는다", () => {
  const [o, d] = rayTo([2, 4, 1.5], [2, 0, 1.4]);
  assert.equal(hangAtRay(o, d, walls, tv, C), null);
});

test("가벽은 보이는 쪽 면에 건다", () => {
  const part = { id: "pl9", start: [1, 1.5], end: [3, 1.5], t: 0.1, h: 2.4, both: true };
  const [o, d] = rayTo([2, 1.6, 0.4], [2, 1.2, 1.45]); // 가벽의 -z 쪽 면
  const r = hangAtRay(o, d, [...walls, part], tv, C);
  assert.equal(r.wall, "pl9");
  assert.ok(near(r.xz[1], 1.45 - 0.025, 1e-3) && near(r.yaw, -UP));
});

test("바닥 점에서는 가장 가까운 벽에 건다", () => {
  const r = hangNear([2.2, 0.8], walls, tv, C);
  assert.equal(r.wall, "w1");
  assert.ok(near(r.xz[0], 2.2) && near(r.xz[1], 0.075, 1e-3) && near(r.yaw, UP));
});

test("제품보다 짧은 벽은 건너뛴다", () => {
  const stub = { id: "stub", start: [1.8, 0.9], end: [2.2, 0.9], t: 0.1, h: 2.4 };
  assert.equal(hangNear([2, 1.0], [...walls, stub], tv, C).wall, "w1");
  const [o, d] = rayTo([2, 1.6, 2.5], [2, 1.2, 0.95]); // 짧은 벽을 가리켜도 그 뒤 벽에 건다
  assert.equal(hangAtRay(o, d, [...walls, stub], tv, C).wall, "w1");
});

test("모서리 근처에서 방 안으로 튀어나온 벽을 피해 옆으로 민다", () => {
  const poke = { id: "poke", start: [3.4, 0], end: [3.4, 0.5], t: 0.1, h: 2.4 };
  const r = hangNear([3.0, 0.3], [...walls, poke], tv, C);
  assert.equal(r.wall, "w1");
  assert.ok(r.xz[0] + 0.7 <= 3.35 + 1e-6);
});

test("처음 거는 높이: TV는 눈높이, 에어컨은 천장 아래", () => {
  assert.ok(near(defaultBase("tv", 0.8, 2.4), 1.1 - 0.4));
  assert.ok(near(defaultBase("air_conditioner", 0.33, 2.4), 2.4 - 0.15 - 0.33));
});
