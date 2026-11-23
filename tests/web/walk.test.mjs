// 1인칭 둘러보기 순수 로직 (apps/web/js/walk.js). 실행: node --test tests/web/
// 좌표: 평면 (x, y) = 3D (x, z). 카메라 yaw 0 = -z(평면 -y)를 본다 (three.js 기본).
import test from "node:test";
import assert from "node:assert/strict";
import { EYE_H, RADIUS, buildWorld, moveVector, step, isBlocked, spawnPoint } from "../../apps/web/js/walk.js";

const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;

// 4 m × 3 m 방: 벽 두께 0.1, 가운데 (2, 1.5)
const ROOM = {
  walls: [
    { wall_id: "w1", start: [0, 0], end: [4, 0], thickness_m: 0.1 },
    { wall_id: "w2", start: [4, 0], end: [4, 3], thickness_m: 0.1 },
    { wall_id: "w3", start: [4, 3], end: [0, 3], thickness_m: 0.1 },
    { wall_id: "w4", start: [0, 3], end: [0, 0], thickness_m: 0.1 },
  ],
  objects: [
    { object_id: "o1", category: "table", position: [3, 0.37, 2], bbox_m: { w: 1.0, h: 0.74, d: 0.5 }, yaw_rad: 0 },
    { object_id: "o2", category: "chair", position: [1, 0.4, 2.5], bbox_m: { w: 0.5, h: 0.8, d: 0.5 }, yaw_rad: 0 },
  ],
};

test("눈높이는 1.6 m, 몸 반지름은 사람 어깨 정도", () => {
  assert.equal(EYE_H, 1.6);
  assert.ok(RADIUS >= 0.2 && RADIUS <= 0.35);
});

test("W는 보는 쪽으로, D는 오른쪽으로, 대각선은 빨라지지 않는다", () => {
  const [fx, fz] = moveVector(0, { f: true }, 1.4, 1);
  assert.ok(near(fx, 0) && near(fz, -1.4));
  const [rx, rz] = moveVector(0, { r: true }, 1.4, 1);
  assert.ok(near(rx, 1.4) && near(rz, 0));
  const [tx, tz] = moveVector(Math.PI / 2, { f: true }, 1, 1); // 왼쪽으로 90° 돌면 -x를 본다
  assert.ok(near(tx, -1) && near(tz, 0));
  const [dx, dz] = moveVector(0, { f: true, r: true }, 1, 1);
  assert.ok(near(Math.hypot(dx, dz), 1));
  assert.deepEqual(moveVector(0, { f: true, b: true }, 1, 1).map((v) => Math.abs(v)), [0, 0]);
});

test("벽 가까이는 못 간다 (벽 두께 반 + 몸 반지름)", () => {
  const w = buildWorld(ROOM, [], []);
  assert.equal(isBlocked([2, 0.1], w), true);
  assert.equal(isBlocked([2, 0.05 + RADIUS + 0.02], w), false);
  assert.equal(isBlocked([2, 1.5], w), false);
});

test("벽으로 비스듬히 걸으면 벽을 따라 미끄러진다", () => {
  const w = buildWorld(ROOM, [], []);
  const p = step([2, 0.5], [0.3, -0.6], w); // 아래(벽 쪽)·오른쪽으로
  assert.ok(p[1] >= 0.05 + RADIUS - 1e-6, "벽을 넘지 않음");
  assert.ok(p[0] > 2.2, "벽을 따라 옆으로는 움직임");
});

test("한 번에 크게 움직여도 벽을 뚫고 방 밖으로 나가지 않는다", () => {
  const w = buildWorld(ROOM, [], []);
  const p = step([2, 1.5], [0, -10], w);
  assert.ok(p[1] > 0 && p[1] < 3);
  const q = step([2, 1.5], [10, 0], w);
  assert.ok(q[0] < 4);
});

test("스캔 가구와 부딪힌다 (돌아간 가구도)", () => {
  const w = buildWorld(ROOM, [], []);
  assert.equal(isBlocked([3, 2], w), true); // 테이블 가운데
  assert.equal(isBlocked([3.5 + RADIUS - 0.05, 2], w), true); // 테이블 끝 + 반지름 안
  assert.equal(isBlocked([3, 2 - 0.25 - RADIUS - 0.05], w), false); // 테이블 앞
  const turned = buildWorld({ ...ROOM, objects: [{ ...ROOM.objects[0], yaw_rad: Math.PI / 2 }] }, [], []);
  assert.equal(isBlocked([3, 2 - 0.4], turned), true); // 90° 돌아 깊이 방향으로 길어짐
  assert.equal(isBlocked([3 + 0.25 + RADIUS + 0.05, 2], turned), false); // 이제 x 쪽은 반깊이 0.25만
});

test("치운 가구는 안 막는다", () => {
  const w = buildWorld(ROOM, [], ["o1"]);
  assert.equal(isBlocked([3, 2], w), false);
});

test("놓은 제품과 부딪힌다 (제품 yaw는 벽 안쪽 법선: 상자는 yaw-90°)", () => {
  // 폭 2 m·깊이 0.6 m 냉장고, yaw 90°(+y를 봄) → 상자 회전 0 → 폭이 x 방향
  const pl = [{ placement_id: "p1", center_xz: [2, 0.5], size_m: [2.0, 1.8, 0.6], yaw_rad: Math.PI / 2 }];
  const w = buildWorld({ ...ROOM, objects: [] }, pl, []);
  assert.equal(isBlocked([2.9, 0.5], w), true);
  assert.equal(isBlocked([2, 0.5 + 0.3 + RADIUS + 0.05], w), false);
});

test("시작 자리는 방 안의 빈 곳", () => {
  const w = buildWorld(ROOM, [], []);
  const s = spawnPoint(w);
  assert.equal(isBlocked(s, w), false);
  assert.ok(s[0] > 0 && s[0] < 4 && s[1] > 0 && s[1] < 3);
  const crowded = buildWorld({ ...ROOM, objects: [{ object_id: "big", category: "table", position: [2, 0.4, 1.5], bbox_m: { w: 1.5, h: 0.8, d: 1.2 }, yaw_rad: 0 }] }, [], []);
  assert.equal(isBlocked(spawnPoint(crowded), crowded), false); // 가운데가 막혀 있으면 옆 빈 곳
});

test("시작 자리는 가구·제품 코앞이 아니라 둘레가 트인 곳 (첫 화면이 냉장고 옆면으로 가득 차지 않게)", () => {
  // 가운데 바로 옆에 키 큰 제품이 있다: 가운데는 비어 있지만 25 cm 앞이 제품
  const fridge = { placement_id: "p1", center_xz: [2.75, 1.5], yaw_rad: 0, size_m: [0.9, 1.8, 0.7] };
  const w = buildWorld({ ...ROOM, objects: [] }, [fridge], []);
  const s = spawnPoint(w);
  assert.equal(isBlocked(s, w), false);
  assert.equal(isBlocked(s, w, 0.6), false, `제품·벽에서 0.6 m 안: ${s}`);
});
