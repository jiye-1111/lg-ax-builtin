// 회전 고리 (apps/web/js/rotring.js). 실행: node --test tests/web/
import test from "node:test";
import assert from "node:assert/strict";
import { pointerAngle, turnTo, snapTurn, SNAP_RAD, MAGNET_RAD, ringRadius, degLabel } from "../../apps/web/js/rotring.js";

const deg = (d) => (d * Math.PI) / 180;
const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("고리 손잡이 각도는 물건 가운데에서 본 커서 방향이다 (3D y 회전과 같은 쪽)", () => {
  near(pointerAngle([0, 0], [0, 1]), 0);           // +z 앞
  near(pointerAngle([0, 0], [1, 0]), Math.PI / 2); // +x
  near(pointerAngle([2, 2], [2, 1]), Math.PI);
});

test("잡은 자리를 기준으로 돈다: 손잡이를 조금 비껴 잡아도 물건이 튀지 않는다", () => {
  const start = { rot: deg(30), grab: deg(40) };
  near(turnTo(start, deg(40)), deg(30));
  near(turnTo(start, deg(100)), deg(90));
});

test("45°마다 자석처럼 붙고, 그 사이는 자유롭게 돈다", () => {
  near(snapTurn(deg(88)), deg(90));
  near(snapTurn(deg(-43)), deg(-45));
  near(snapTurn(deg(70)), deg(70));
  assert.ok(MAGNET_RAD < SNAP_RAD / 2);
});

test("Shift를 누르면 15°씩만 돈다", () => {
  near(snapTurn(deg(22), { fine: true }), deg(15));
  near(snapTurn(deg(23), { fine: true }), deg(30));
});

test("고리는 물건보다 조금 크고, 너무 작거나 크지 않다", () => {
  assert.ok(ringRadius(0.6, 0.4) > 0.36 && ringRadius(0.6, 0.4) < 0.7);
  assert.ok(ringRadius(0.05, 0.05) >= 0.35);
  assert.ok(ringRadius(4, 3) <= 2.8);
});

test("화면에 보이는 각도는 0~359°", () => {
  assert.equal(degLabel(deg(-90)), "270°");
  assert.equal(degLabel(deg(360)), "0°");
  assert.equal(degLabel(deg(44.6)), "45°");
});

test("Alt를 누르면 45° 근처에서도 붙지 않는다", () => {
  near(snapTurn(deg(88), { free: true }), deg(88));
});
