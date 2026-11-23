// 평면도 가구 기호 (apps/web/js/symbols.js). 실행: node --test tests/web/
import test from "node:test";
import assert from "node:assert/strict";
import { furnitureSymbol, hasSymbol } from "../../apps/web/js/symbols.js";

const nums = (svg, attr) => [...svg.matchAll(new RegExp(` ${attr}="(-?[\\d.]+)"`, "g"))].map((m) => +m[1]);

test("소파·의자·침대·식탁·수납장·화분은 저마다 다른 기호로 그린다", () => {
  const kinds = ["sofa", "chair", "bed", "table", "storage", "plant", "lamp", "sink"];
  const drawn = kinds.map((k) => furnitureSymbol(k, 1.2, 0.8));
  assert.equal(new Set(drawn).size, kinds.length);
  for (const k of kinds) assert.ok(hasSymbol(k));
  assert.ok(!hasSymbol("fireplace"));
});

test("기호는 가구 크기 밖으로 나가지 않는다", () => {
  for (const k of ["sofa", "chair", "bed", "table", "storage", "basecab", "sink", "rug", "fireplace"]) {
    const svg = furnitureSymbol(k, 2.2, 0.9);
    const xs = nums(svg, "x"), ws = nums(svg, "width");
    xs.forEach((x, i) => { assert.ok(x >= -1.1 - 1e-6, `${k} x ${x}`); assert.ok(x + ws[i] <= 1.1 + 1e-6, `${k} 오른쪽 ${x + ws[i]}`); });
  }
});

test("긴 소파는 방석이 늘고, 넓은 수납장은 문이 는다", () => {
  const count = (s, re) => (s.match(re) || []).length;
  assert.ok(count(furnitureSymbol("sofa", 2.4, 0.9), /<rect/g) > count(furnitureSymbol("sofa", 1.0, 0.9), /<rect/g));
  assert.ok(count(furnitureSymbol("storage", 2.4, 0.6), /<line/g) > count(furnitureSymbol("storage", 0.6, 0.6), /<line/g));
});

test("아주 작은 크기에도 음수 치수를 만들지 않는다", () => {
  for (const k of ["sofa", "chair", "bed", "table", "storage", "plant", "lamp", "rug"]) {
    const svg = furnitureSymbol(k, 0.05, 0.05);
    for (const v of [...nums(svg, "width"), ...nums(svg, "height"), ...nums(svg, "r")]) assert.ok(v > 0, `${k} ${v}`);
  }
});

test("벽 순서가 뒤섞여 있어도 방 테두리를 한 바퀴로 잇는다. 안 이어지면 바닥을 칠하지 않는다", async () => {
  const { roomOutline } = await import("../../apps/web/js/symbols.js");
  const w = (a, b) => ({ start: a, end: b });
  const mixed = [w([0, 0], [8, 0]), w([0, 5], [0, 0]), w([8, 5], [8, 0]), w([8, 5], [0, 5])];
  assert.deepEqual(roomOutline(mixed), [[0, 0], [8, 0], [8, 5], [0, 5]]);
  assert.equal(roomOutline([w([0, 0], [8, 0]), w([8, 0], [8, 5]), w([3, 3], [4, 4])]), null);
});
