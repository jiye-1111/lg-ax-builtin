// 키보드로 화면 움직이기 (apps/web/js/camkeys.js). 실행: node --test tests/web/
import test from "node:test";
import assert from "node:assert/strict";
import { PAN_M_S, TURN_DEG_S, wantVelocity, ease, isMoving } from "../../apps/web/js/camkeys.js";

test("누르고 있는 키대로 가려는 속도가 정해진다. 반대 키를 같이 누르면 선다", () => {
  assert.deepEqual(wantVelocity({ w: true }), [0, PAN_M_S, 0]);
  assert.deepEqual(wantVelocity({ a: true, e: true }), [-PAN_M_S, 0, TURN_DEG_S]);
  assert.deepEqual(wantVelocity({ a: true, d: true, q: true, e: true }), [0, 0, 0]);
  assert.deepEqual(wantVelocity({}), [0, 0, 0]);
});

test("속도는 한 번에 바뀌지 않고 부드럽게 따라간다. 화면이 느려도 넘치지 않는다", () => {
  const a = ease([0, 0, 0], [0, PAN_M_S, 0], 1 / 60);
  assert.ok(a[1] > 0 && a[1] < PAN_M_S * 0.3);
  const slow = ease([0, 0, 0], [0, PAN_M_S, 0], 0.25);
  assert.ok(slow[1] <= PAN_M_S);
  let v = [0, PAN_M_S, 0];
  for (let i = 0; i < 60; i++) v = ease(v, [0, 0, 0], 1 / 60);
  assert.ok(!isMoving(v), "키를 놓고 1초면 선다");
  assert.ok(isMoving([0, 0.5, 0]));
});
