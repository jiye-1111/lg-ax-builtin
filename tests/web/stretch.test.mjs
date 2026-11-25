// 장 끝을 끌어 늘리기
import test from "node:test";
import assert from "node:assert/strict";
import { stretchTo, anchorOf, reachOf } from "../../apps/web/js/stretch.js";

const UP = Math.PI / 2; // 정면 +y, 폭 축 +x
const cab = { xz: [2.0, 0.35], yaw: UP, w: 1.2, d: 0.6 };
const near = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≉ ${b}`);
const box = (x0, x1, y0 = 0.05, y1 = 0.65) => ({ pts: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] });

test("오른쪽 끝을 끌면 왼쪽 끝은 그대로 있다", () => {
  const r = stretchTo(cab, 1, 1.8);
  near(r.w, 1.8); near(r.xz[0] - r.w / 2, 1.4); near(r.xz[1], 0.35);
});

test("왼쪽 끝을 끌면 오른쪽 끝은 그대로 있다", () => {
  const r = stretchTo(cab, -1, 0.9);
  near(r.w, 0.9); near(r.xz[0] + r.w / 2, 2.6);
});

test("1 cm 단위로 맞춘다", () => near(stretchTo(cab, 1, 1.234).w, 1.23));

test("옆 가전 가까이 가면 딱 닿게 멈추고, 요구하는 옆 여유는 남긴다", () => {
  const r = stretchTo(cab, 1, 1.56, [box(3.0, 3.6)]);
  near(r.w, 1.6); assert.equal(r.hit, true);
  near(stretchTo(cab, 1, 1.56, [{ ...box(3.0, 3.6), pad: 0.004 }]).w, 1.596);
});

test("멀리 있는 것, 옆으로 비켜 있는 것, 뒤쪽 것에는 안 붙는다", () => {
  near(stretchTo(cab, 1, 1.4, [box(3.0, 3.6)]).w, 1.4);
  near(stretchTo(cab, 1, 1.57, [box(3.0, 3.6, 0.8, 1.4)]).w, 1.57);
  near(stretchTo(cab, 1, 0.52, [box(0.6, 1.4 + 0.5)]).w, 0.52);
});

test("Alt를 누르면 붙지 않는다", () => near(stretchTo(cab, 1, 1.563, [box(3.0, 3.6)], { free: true }).w, 1.563));

test("너무 짧거나 길게는 안 된다", () => {
  near(stretchTo(cab, 1, 0.01, [], { min: 0.1 }).w, 0.1);
  near(stretchTo(cab, 1, 20, [], { max: 8 }).w, 8);
});

test("돌려 놓은 장도 제 방향으로 늘어난다", () => {
  const side = { xz: [0.35, 1.5], yaw: 0, w: 1.2, d: 0.6 }; // 정면 +x, 폭 축 -y
  const r = stretchTo(side, 1, 1.8);
  near(r.xz[0], 0.35); near(r.xz[1], 1.5 - 0.3);
  near(reachOf(side, 1, [0.35, 0.3]), 1.8);
  near(anchorOf(side, 1)[1], 2.1);
});
