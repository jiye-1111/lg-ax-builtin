// 벽 그릴 때 Shift로 반듯하게 맞추기 (apps/web/js/wallsnap.js). 실행: node --test tests/web/
import test from "node:test";
import assert from "node:assert/strict";
import { straighten, snapStart } from "../../apps/web/js/wallsnap.js";

const ROOM = [
  { start: [0, 0], end: [8, 0] }, { start: [8, 0], end: [8, 5] }, { start: [8, 5], end: [0, 5] }, { start: [0, 5], end: [0, 0] },
];
const near = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol;

test("조금 비뚤게 끌어도 기존 벽과 나란하거나 직각으로 선다", () => {
  const p = straighten([3, 1], [3.2, 3.02], ROOM);
  assert.ok(near(p[0], 3), `x ${p[0]}`);
  const q = straighten([3, 1], [5.1, 1.3], ROOM);
  assert.ok(near(q[1], 1));
});

test("길이는 5 cm 단위로 떨어진다", () => {
  const p = straighten([3, 1], [3.1, 2.537], ROOM);
  assert.ok(near(p[1], 2.55), `z ${p[1]}`);
});

test("끝이 다른 벽 가까이 가면 그 벽에 딱 붙는다", () => {
  const p = straighten([3, 1], [3.1, 4.86], ROOM);
  assert.ok(near(p[0], 3) && near(p[1], 5), JSON.stringify(p));
});

test("비스듬한 집에서는 그 집 벽 방향을 따른다", () => {
  const c = Math.cos(0.3), s = Math.sin(0.3);
  const tilted = [{ start: [0, 0], end: [6 * c, 6 * s] }];
  const p = straighten([1, 2], [1 + 2 * Math.cos(0.36), 2 + 2 * Math.sin(0.36)], tilted);
  assert.ok(near(Math.atan2(p[1] - 2, p[0] - 1), 0.3, 1e-6));
});

test("벽이 하나도 없으면 가로세로에 맞춘다", () => {
  const p = straighten([0, 0], [2, 0.2], []);
  assert.ok(near(p[1], 0) && near(p[0], 2));
});

test("시작점도 벽 가까이에서 누르면 벽에 붙는다. 멀면 그대로", () => {
  assert.deepEqual(snapStart([3, 0.15], ROOM).map((v) => +v.toFixed(6)), [3, 0]);
  assert.deepEqual(snapStart([3, 2], ROOM), [3, 2]);
});
