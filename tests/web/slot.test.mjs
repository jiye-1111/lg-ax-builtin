// 장 칸에 끼워 넣는 자리 (서버 tests/unit/test_slot.py와 같은 숫자)
import test from "node:test";
import assert from "node:assert/strict";
import { slotPose } from "../../apps/web/js/slot.js";

const UP = Math.PI / 2;
const DW = { w: 0.598, h: 0.815, d: 0.567 };
const FRONT_Y = 0.35 + 0.3 - 0.02 - 0.567 / 2;
const cab = (id, x, w, more = {}) => ({ id, sku: "decor:basecab", xz: [x, 0.35], yaw: UP, w, h: 0.85, d: 0.6, ...more });
const near = (a, b, tol = 2e-3) => assert.ok(Math.abs(a - b) <= tol, `${a} ≉ ${b}`);

test("하부장 위로 가져가면 문짝 앞면에 맞춰 장과 같은 쪽을 본다", () => {
  const s = slotPose(DW, [2.0, 0.5], [cab("c1", 2.0, 1.8)]);
  assert.equal(s.host, "c1");
  near(s.xz[0], 2.0); near(s.xz[1], FRONT_Y); near(s.yaw, UP);
});

test("장 끝 가까이에서는 끝에 맞춘다", () => {
  near(slotPose(DW, [1.1 + 0.299 + 0.08, 0.4], [cab("c1", 2.0, 1.8)]).xz[0] - 0.299, 1.1);
  near(slotPose(DW, [2.9 + 0.299 + 0.07, 0.38], [cab("c1", 2.0, 1.8)]).xz[0] - 0.299, 2.9);
});

test("멀리 있으면 그대로 둔다", () => {
  assert.equal(slotPose(DW, [0.5, 0.4], [cab("c1", 2.5, 1.0)]), null);
  assert.equal(slotPose(DW, [2.5, 1.6], [cab("c1", 2.5, 1.0)]), null);
});

test("빈 칸에는 가까운 쪽 장에 붙는다", () => {
  near(slotPose(DW, [2.02, 0.4], [cab("a", 1.4, 0.6), cab("b", 2.6, 0.6)]).xz[0], 2.0);
});

test("자를 수 없는 장 위로는 끼우지 않고, 옆에는 붙는다", () => {
  assert.equal(slotPose(DW, [2.0, 0.4], [cab("c1", 2.0, 1.8, { keep: true })]), null);
  assert.ok(slotPose(DW, [2.9 + 0.299 + 0.05, 0.4], [cab("c1", 2.0, 1.8, { keep: true })]));
});

test("낮은 제품은 키큰장에, 키 큰 제품은 하부장에 끼우지 않는다", () => {
  const tall = { id: "t", sku: "decor:tallcab", xz: [2.0, 0.35], yaw: UP, w: 0.6, h: 2.0, d: 0.6 };
  assert.equal(slotPose(DW, [2.0, 0.4], [tall]), null);
  assert.equal(slotPose({ w: 0.914, h: 1.86, d: 0.709 }, [2.0, 0.4], [cab("c1", 2.0, 1.8)]), null);
});

test("장보다 깊은 냉장고는 등을 장 등에 맞추고 옆 여유를 남긴다", () => {
  const t = (id, x) => ({ id, sku: "decor:tallcab", xz: [x, 0.35], yaw: UP, w: 0.6, h: 2.0, d: 0.6 });
  const s = slotPose({ w: 0.914, h: 1.86, d: 0.709, side: 0.004 }, [1.8, 0.45], [t("t1", 1.0), t("t2", 2.6)]);
  near(s.xz[1] - 0.709 / 2, 0.05);
  assert.ok(s.xz[0] - 0.457 >= 1.304 - 1e-9);
});

// ---- 끄는 동안 미리 보여 줄 모습 (서버가 놓을 때 자르는 것과 같은 조각) ----
test("장 가운데에 가져가면 양쪽 조각과 덮는 상판이 나온다", () => {
  const s = slotPose(DW, [2.0, 0.5], [cab("c1", 2.0, 1.8)]);
  assert.equal(s.edits.length, 2);
  const [l, r] = s.edits;
  assert.equal(l.id, "c1"); assert.equal(r.like, "c1");
  near(l.w + r.w + 0.598, 1.8); near(l.xz[0] - l.w / 2, 1.1); near(r.xz[0] + r.w / 2, 2.9);
  assert.equal(s.cover.look, "basecab"); near(s.cover.top, 0.85); near(s.cover.off, 0.35 - FRONT_Y);
});

test("장 옆에 붙이면 자르는 것 없이 상판만 이어진다", () => {
  const s = slotPose(DW, [2.9 + 0.299 + 0.07, 0.38], [cab("c1", 2.0, 1.8)]);
  assert.deepEqual(s.edits, []);
  assert.ok(s.cover);
});

test("딱 맞는 폭이거나 자투리만 남으면 장이 없어진다", () => {
  assert.deepEqual(slotPose(DW, [2.0, 0.4], [cab("c1", 2.0, 0.7)]).edits, [{ id: "c1", remove: true }]);
});

test("싱크대는 끝에서만 줄고, 좁으면 옆에 붙는다", () => {
  const sink = (w) => ({ ...cab("s", 2.0, w), sku: "decor:sink", h: 0.88 });
  const a = slotPose(DW, [2.0, 0.4], [sink(1.6)]);
  assert.equal(a.edits.length, 1); near(a.edits[0].w, 1.6 - 0.598); near(Math.abs(a.xz[0] - 2.0), 0.8 - 0.299);
  const b = slotPose(DW, [2.1, 0.4], [sink(1.0)]);
  assert.deepEqual(b.edits, []); near(b.xz[0] - 0.299, 2.5);
});

test("아일랜드 식탁은 앉는 자리를 비우고 몸통 등에 맞춘다", () => {
  const t = { id: "t", sku: "decor:islandtable", xz: [3.0, 3.0], yaw: UP, w: 1.8, h: 0.89, d: 0.75 };
  const s = slotPose(DW, [3.0, 3.1], [t]);
  near(s.xz[1] - 0.567 / 2, 3.0 - 0.375 + 0.15); near(s.cover.seat, 0.15);
});

test("스캔한 장은 문짝 턱 없이 앞면에 맞춘다", () => {
  near(slotPose(DW, [2.0, 0.4], [cab("o1", 2.0, 1.8, { door: 0 })]).xz[1], 0.35 + 0.3 - 0.567 / 2);
});
