// 동선을 걷는 사람 모델의 순수 로직 (apps/web/js/walker.js). 실행: node --test tests/web/
// 좌표: 평면 (x, y) = 3D (x, z). heading = 3D y축 회전(rad), 0이면 +z를 본다 (사람 모델 정면 +Z).
import test from "node:test";
import assert from "node:assert/strict";
import { WALK_SPEED, pathLength, poseAt, routeClock } from "../../apps/web/js/walker.js";

const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
const L = [[0, 0], [3, 0], [3, 4]]; // 3 m 동쪽, 4 m 남쪽(+y) → 길이 7

test("경로 길이는 구간 길이의 합", () => {
  assert.equal(pathLength(L), 7);
  assert.equal(pathLength([[1, 1]]), 0);
  assert.equal(pathLength([]), 0);
});

test("걸은 거리에 맞는 자리와 바라보는 방향", () => {
  const a = poseAt(L, 1.5);
  assert.ok(near(a.xz[0], 1.5) && near(a.xz[1], 0));
  assert.ok(near(a.heading, Math.PI / 2)); // +x를 본다
  const b = poseAt(L, 5);
  assert.ok(near(b.xz[0], 3) && near(b.xz[1], 2));
  assert.ok(near(b.heading, 0)); // +y(3D +z)를 본다
});

test("범위 밖 거리는 양 끝에 멈춘다", () => {
  assert.deepEqual(poseAt(L, -2).xz, [0, 0]);
  assert.deepEqual(poseAt(L, 99).xz, [3, 4]);
  assert.ok(near(poseAt(L, 99).heading, 0));
});

test("점 하나·빈 경로도 깨지지 않는다", () => {
  assert.deepEqual(poseAt([[2, 3]], 1).xz, [2, 3]);
  assert.equal(poseAt([], 1), null);
});

test("걷는 빠르기는 사람 보통 걸음(1.2~1.4 m/s)", () => {
  assert.ok(WALK_SPEED >= 1.2 && WALK_SPEED <= 1.4);
});

test("시간이 지나면 끝까지 걷고 잠깐 선 뒤 다시 처음부터", () => {
  const clk = routeClock(7, { speed: 1, pause: 1 });
  assert.equal(clk(0).s, 0);
  assert.ok(near(clk(3.5).s, 3.5) && clk(3.5).moving);
  const end = clk(7.5); // 도착해서 서 있다
  assert.equal(end.s, 7);
  assert.equal(end.moving, false);
  assert.ok(near(clk(8.5).s, 0.5)); // 한 바퀴 = 7 + 1초
});
