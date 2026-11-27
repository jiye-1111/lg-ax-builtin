import test from "node:test";
import assert from "node:assert/strict";
import { readLength, fmtMm, cardSpot } from "../../apps/web/js/measure.js";

test("mm로 넣은 값을 m로 읽는다", () => {
  assert.equal(readLength("3400", 3.42), 3.4);
  assert.equal(readLength("3,400 mm", 3.42), 3.4);
});

test("줄자 눈금대로 cm나 m로 넣어도 스캔 길이에 가까운 쪽으로 읽는다", () => {
  assert.equal(readLength("340.5", 3.42), 3.405);
  assert.equal(readLength("3.4", 3.42), 3.4);
  assert.equal(readLength("10900", 10.87), 10.9);
});

test("글자나 0, 음수는 읽지 않는다", () => {
  for (const t of ["", "abc", "0", "-3400", "3.4.1"]) assert.equal(readLength(t, 3.42), null);
});

test("어느 단위로도 스캔과 맞지 않으면 mm로 읽어 서버가 다시 묻게 한다", () => {
  assert.equal(readLength("8000", 3.42), 8);
});

test("길이는 mm에 쉼표를 찍어 보여 준다", () => {
  assert.equal(fmtMm(3.4), "3,400");
  assert.equal(fmtMm(10.8704), "10,870");
});

test("입력 카드는 벽 발치 아래에 두고 화면 밖으로 나가지 않는다", () => {
  assert.deepEqual(cardSpot([400, 300], { width: 800, height: 600 }, { width: 260, height: 120 }), { left: 270, top: 318 });
  assert.equal(cardSpot([5, 300], { width: 800, height: 600 }, { width: 260, height: 120 }).left, 8);
  assert.equal(cardSpot([790, 300], { width: 800, height: 600 }, { width: 260, height: 120 }).left, 532);
  // 아래에 자리가 없으면 발치 위로
  assert.equal(cardSpot([400, 560], { width: 800, height: 600 }, { width: 260, height: 120 }).top, 422);
});
