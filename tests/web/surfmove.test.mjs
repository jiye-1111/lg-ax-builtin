// 책상·식탁 위에 올린 물건 끌기: 잡은 높이의 평면을 따라가야 바닥 먼 곳으로 튀지 않는다
import { test } from "node:test";
import assert from "node:assert/strict";
import { onPlane, grabOffset } from "../../apps/web/js/surfmove.js";

const near = (a, b, eps = 1e-9) => a.every((v, i) => Math.abs(v - b[i]) < eps);

test("책상 높이 평면과 만나는 점을 준다", () => {
  const p = onPlane([0, 2.73, 0], [0, -1, 1], 0.73); // 카메라에서 45°로 내려다보는 광선
  assert.ok(near(p, [0, 2]));
});

test("같은 광선이라도 바닥 평면이면 더 멀리 간다 (책상 위 물건이 바닥 점을 따라가면 튄다)", () => {
  const desk = onPlane([0, 2.73, 0], [0, -1, 1], 0.73), floor = onPlane([0, 2.73, 0], [0, -1, 1], 0);
  assert.ok(floor[1] - desk[1] > 0.7);
});

test("평면과 나란하거나 위를 보는 광선은 점이 없다", () => {
  assert.equal(onPlane([0, 2, 0], [1, 0, 0], 0.73), null);
  assert.equal(onPlane([0, 2, 0], [0, 1, 0], 0.73), null);
});

test("잡은 자리와 물건 가운데 차이를 기억해서 처음 움직일 때 튀지 않는다", () => {
  const g = grabOffset([1, 2], [1.1, 1.9]);
  assert.ok(near(g, [-0.1, 0.1]));
  assert.deepEqual(grabOffset([1, 2], null), [0, 0]);
});
