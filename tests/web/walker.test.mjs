// 동선을 걷는 사람 모델의 순수 로직 (apps/web/js/walker.js). 실행: node --test tests/web/
// 좌표: 평면 (x, y) = 3D (x, z). heading = 3D y축 회전(rad), 0이면 +z를 본다 (사람 모델 정면 +Z).
import test from "node:test";
import assert from "node:assert/strict";
import { WALK_SPEED, pathLength, poseAt, routeClock, smoothPath, tourClock } from "../../apps/web/js/walker.js";

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

// 지예: 동선에서 사람이 부자연스럽게 걷는다 → 격자 경로의 5 cm 지그재그를 펴고, 출발·도착은 천천히
test("격자 지그재그를 펴서 방향이 갑자기 꺾이지 않는다", () => {
  const zig = [];
  for (let i = 0; i <= 40; i++) zig.push([i * 0.1, i % 2 ? 0.05 : 0]); // 4 m 직진, 5 cm 지그재그
  const sm = smoothPath(zig);
  assert.deepEqual(sm[0], zig[0]);
  assert.deepEqual(sm[sm.length - 1], zig[zig.length - 1]);
  let worst = 0;
  for (let s = 0.3; s < pathLength(sm) - 0.3; s += 0.05) {
    worst = Math.max(worst, Math.abs(Math.atan2(Math.sin(poseAt(sm, s).heading - Math.PI / 2), Math.cos(poseAt(sm, s).heading - Math.PI / 2))));
  }
  assert.ok(worst < 0.2, `heading wobble ${worst}`);
});

test("직각 모퉁이는 둥글게 돈다 (길이는 거의 그대로)", () => {
  const sq = [[0, 0], [2, 0], [2, 2]];
  const sm = smoothPath(sq);
  assert.ok(pathLength(sm) < 4 && pathLength(sm) > 3.6);
  const mid = poseAt(sm, pathLength(sm) / 2).heading; // 모퉁이 한가운데는 대각선 쪽을 본다
  assert.ok(mid > 0.3 && mid < Math.PI / 2 - 0.3);
});

test("출발할 때 천천히 가속하고 도착 전에 감속한다", () => {
  const clk = routeClock(7, { speed: 1, pause: 1, ease: 0.5 });
  assert.ok(clk(0.1).s < 0.1 * 0.5);              // 처음엔 느리게
  assert.ok(near(clk(4).s - clk(3).s, 1, 1e-6));  // 가운데는 보통 빠르기
  const walkT = 7 + 0.5;                            // 가감속만큼 조금 더 걸린다
  assert.equal(clk(walkT + 0.2).s, 7);
  assert.ok(clk(walkT - 0.05).s > 6.99);
});

test("왕복: 끝에 닿으면 처음으로 순간 이동하지 않고 돌아서 걸어온다", () => {
  const clk = routeClock(6, { speed: 1, pause: 1, roundTrip: true });
  assert.deepEqual([clk(3).s, clk(3).dir, clk(3).moving], [3, 1, true]);
  const rest = clk(6.5);                       // 끝에서 쉬는 중: 다음에 갈 쪽(돌아가는 쪽)을 알려 준다
  assert.deepEqual([rest.s, rest.moving, rest.dir], [6, false, -1]);
  const back = clk(9);                         // 돌아오는 길
  assert.deepEqual([back.s, back.dir, back.moving], [4, -1, true]);
  const home = clk(13.5);                      // 처음 자리에서 쉬는 중
  assert.deepEqual([home.s, home.moving, home.dir], [0, false, 1]);
  assert.equal(clk(14 + 3).s, 3);              // 다시 출발
  let prev = clk(0).s;
  for (let t = 0.05; t < 28; t += 0.05) { const s = clk(t).s; assert.ok(Math.abs(s - prev) < 0.06, `t=${t.toFixed(2)}에서 ${prev}→${s}로 뛰었다`); prev = s; }
});

// 지예: 동선이 지저분하다 → 사람은 한 명만. 가전마다 차례로 갔다가 출발 자리로 돌아온다
test("한 사람이 길마다 차례로 왕복한다 (끝나면 첫 길부터 다시)", () => {
  const clk = tourClock([4, 2], { speed: 1, pause: 1 });
  // 첫 길: 가는 데 4초, 쉬고 1초, 오는 데 4초, 쉬고 1초 = 10초
  assert.deepEqual([clk(2).leg, clk(2).s, clk(2).dir], [0, 2, 1]);
  assert.deepEqual([clk(7).leg, clk(7).s, clk(7).dir], [0, 2, -1]);
  // 둘째 길: 10초부터 6초 동안
  assert.deepEqual([clk(11).leg, clk(11).s, clk(11).moving], [1, 1, true]);
  assert.equal(clk(16 + 2).leg, 0);                // 한 바퀴 = 16초
  assert.ok(near(clk(16 + 2).s, 2));
});

test("길을 바꿀 때는 출발 자리에 서 있다가 바뀐다 (순간 이동 없음)", () => {
  const clk = tourClock([4, 2], { speed: 1, pause: 1, ease: 0.3 });
  for (let t = 0; t < 40; t += 0.02) {
    const a = clk(t), b = clk(t + 0.02);
    if (a.leg !== b.leg) assert.ok(a.s < 0.01 && b.s < 0.01, `t=${t.toFixed(2)} 길이 바뀔 때 ${a.s}→${b.s}`);
  }
});

test("길이 하나도 없으면 서 있는다", () => {
  assert.deepEqual(tourClock([], {})(3), { leg: -1, s: 0, moving: false, v: 0, dir: 1 });
});
