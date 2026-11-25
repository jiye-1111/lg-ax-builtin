// 가구 색: 가구마다 칠할 부분과 고를 수 있는 색
import test from "node:test";
import assert from "node:assert/strict";
import { paintParts, coloursFor } from "../../apps/web/js/furncolors.js";

test("소파는 천을, 수납장은 문짝을, 식탁은 나무를 칠한다", () => {
  assert.deepEqual(paintParts("sofa"), ["fabric"]);
  assert.deepEqual(paintParts("basecab"), ["white"]);
  assert.deepEqual(paintParts("table"), ["top"]);
});

test("칠할 데가 없는 것은 색을 고르지 않는다", () => {
  assert.deepEqual(paintParts("없는 것"), []);
  assert.deepEqual(coloursFor("없는 것"), []);
});

test("재질에 맞는 색만 보여 준다: 천은 천 색, 나무는 나무 색", () => {
  const fabric = coloursFor("sofa").map((c) => c.name), wood = coloursFor("table").map((c) => c.name);
  assert.ok(fabric.includes("세이지 그린") && !fabric.includes("월넛"));
  assert.ok(wood.includes("월넛") && !wood.includes("세이지 그린"));
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

test("가구마다 부위별로 색을 바꾼다: 의자는 방석·등받이·다리, 침대는 헤드부터", async () => {
  const { partsOf, partOfMaterial, partColours } = await import("../../apps/web/js/furncolors.js");
  assert.deepEqual(partsOf("chair").map((q) => q.label), ["방석", "등받이", "다리"]);
  assert.equal(partsOf("bed")[0].label, "헤드");
  assert.deepEqual(partsOf("basecab").map((q) => q.key), ["door", "top"]);
  assert.equal(partOfMaterial("chair", "back").key, "back");   // 등받이를 누르면 등받이 색
  assert.equal(partOfMaterial("bed", "head").key, "head");
  assert.equal(partOfMaterial("chair", "없는 재질"), null);
  // 예전에 고른 색(hex)은 맨 앞 부위, 나머지는 part_colors
  assert.deepEqual(partColours("table", "#7A5638", { leg: "#2A2A2B", nope: "#000000" }), { top: "#7A5638", leg: "#2A2A2B" });
  assert.deepEqual(partColours("없는 것", "#7A5638", {}), {});
  // 장 상판 색은 top_hex 자리에서 읽는다
  assert.equal(partsOf("islandtable").find((q) => q.key === "top").field, "top_hex");
  assert.deepEqual(partColours("basecab", null, { top: "#000000" }, "#3A3B3D"), { top: "#3A3B3D" });
});

test("부위마다 색은 6~10가지, 이름은 겹치지 않고, 부위 이름은 서버가 받는 꼴", async () => {
  const { partsOf } = await import("../../apps/web/js/furncolors.js");
  for (const m of ["sofa", "chair", "bed", "table", "coffee", "desk", "shelf", "tvstand", "dresser", "storage", "wardrobe", "tallcab", "basecab", "sink", "island", "door", "window", "glassdoor"]) {
    const keys = partsOf(m).map((q) => q.key);
    assert.ok(keys.length >= 1 && new Set(keys).size === keys.length, m);
    for (const q of partsOf(m)) {
      assert.match(q.key, /^[a-z_]{1,20}$/);
      const names = q.colours.map((c) => c.name);
      assert.equal(new Set(names).size, names.length, `${m}.${q.key}`);
      assert.ok(names.length >= 4 && names.length <= 10, `${m}.${q.key}: ${names.length}`);
      for (const c of q.colours) assert.match(c.hex, /^#[0-9A-F]{6}$/);
    }
  }
});
