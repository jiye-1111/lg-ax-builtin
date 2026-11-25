// 가구 색: 가구마다 칠할 부분과 고를 수 있는 색
import test from "node:test";
import assert from "node:assert/strict";
import { paintParts, coloursFor } from "../../apps/web/js/furncolors.js";

test("소파는 천을, 수납장은 문짝을, 식탁은 나무를 칠한다", () => {
  assert.deepEqual(paintParts("sofa"), ["sofa", "sofa_seat"]);
  assert.deepEqual(paintParts("basecab"), ["white"]);
  assert.deepEqual(paintParts("table"), ["oak"]);
});

test("칠할 데가 없는 것은 색을 고르지 않는다", () => {
  assert.deepEqual(paintParts("plant"), []);
  assert.deepEqual(coloursFor("plant"), []);
  assert.deepEqual(coloursFor("없는 것"), []);
});

test("재질에 맞는 색만 보여 준다: 천은 천 색, 나무는 나무 색", () => {
  const fabric = coloursFor("sofa").map((c) => c.name), wood = coloursFor("table").map((c) => c.name);
  assert.ok(fabric.includes("세이지") && !fabric.includes("월넛"));
  assert.ok(wood.includes("월넛") && !wood.includes("세이지"));
  for (const c of [...coloursFor("sofa"), ...coloursFor("table"), ...coloursFor("basecab")]) assert.match(c.hex, /^#[0-9A-F]{6}$/);
});

test("색 이름은 한 팔레트 안에서 겹치지 않는다", () => {
  for (const m of ["sofa", "table", "basecab", "wall"]) {
    const names = coloursFor(m).map((c) => c.name);
    assert.equal(new Set(names).size, names.length);
    assert.ok(names.length >= 6 && names.length <= 10, `${m}: ${names.length}`);
  }
});

test("붙어 있는 하부장 한 줄은 색을 같이 바꾼다. 떨어진 장이나 다른 가구는 그대로", async () => {
  const { runOf } = await import("../../apps/web/js/furncolors.js");
  const cab = (id, x, h = 0.9) => ({ object_id: id, category: "storage", position: [x, h / 2, 0.3], bbox_m: { w: 0.6, h, d: 0.6 } });
  const objects = [cab("a", 0.3), cab("b", 0.9), cab("c", 1.5), cab("far", 4.0), cab("tall", 2.1, 2.0),
    { object_id: "sofa", category: "sofa", position: [2.1, 0.4, 0.3], bbox_m: { w: 0.6, h: 0.8, d: 0.6 } }];
  assert.deepEqual(runOf(objects, "b").sort(), ["a", "b", "c"]);
  assert.deepEqual(runOf(objects, "far"), ["far"]);
  assert.deepEqual(runOf(objects, "none"), []);
});

test("의자·탁자처럼 따로 쓰는 가구는 붙어 있어도 고른 하나만 바꾼다", async () => {
  const { runOf } = await import("../../apps/web/js/furncolors.js");
  const chair = (id, x) => ({ object_id: id, category: "chair", position: [x, 0.4, 0.3], bbox_m: { w: 0.45, h: 0.8, d: 0.45 } });
  const table = (id, x) => ({ object_id: id, category: "table", position: [x, 0.37, 2], bbox_m: { w: 1.2, h: 0.74, d: 0.6 } });
  assert.deepEqual(runOf([chair("c1", 0.3), chair("c2", 0.78)], "c1"), ["c1"]);
  assert.deepEqual(runOf([table("t1", 0.6), table("t2", 1.8)], "t2"), ["t2"]);
});

test("상판이 있는 가구는 상판 색을 따로 고른다. 상판이 없으면 고를 색이 없다", async () => {
  const { topParts, topColoursFor } = await import("../../apps/web/js/furncolors.js");
  for (const m of ["islandtable", "island", "basecab", "sink"]) {
    assert.deepEqual(topParts(m), ["stone"]);
    const names = topColoursFor(m).map((c) => c.name);
    assert.ok(names.length >= 6 && names.length <= 10 && new Set(names).size === names.length);
    for (const c of topColoursFor(m)) assert.match(c.hex, /^#[0-9A-F]{6}$/);
  }
  assert.deepEqual(topParts("sofa"), []);
  assert.deepEqual(topColoursFor("table"), []);
});
