// 맞춤장 부재 배치와 3D 문 열림 근사 검사 (apps/web/js/cabinet.js). 실행: node --test tests/web/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { layout, doorsOf, doorCheck, cabObstacles, STEP_DEG, OPEN_DEG } from "../../apps/web/js/cabinet.js";

const fridgeCab = (parts = {}) => ({ kind: "fridge", mode: "new", outer_mm: { w: 958, h: 2269, d: 720 },
  parts: { side_l: 18, side_r: 18, back: 0, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, upper_h: 400, doors: 2, ...parts },
  finish: { front: "warmwhite_matte", body: "warmwhite_matte", top: "stone_white", handle: "steel" } });
const dwCab = (parts = {}) => ({ kind: "dishwasher", mode: "new", outer_mm: { w: 636, h: 850, d: 600 },
  parts: { side_l: 18, side_r: 18, back: 0, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, counter: 30, toe_kick: 150, kick_across: false, ...parts },
  finish: { front: "warmwhite_matte", body: "warmwhite_matte", top: "stone_white", handle: "steel" } });
const part = (L, name) => L.parts.find((p) => p.name === name);
const overlap = (a, b) => a[0] < b[3] - 1e-6 && b[0] < a[3] - 1e-6 && a[1] < b[4] - 1e-6 && b[1] < a[4] - 1e-6 && a[2] < b[5] - 1e-6 && b[2] < a[5] - 1e-6;

test("냉장고장: 좌우 측판과 위 수납장이 있고 제품 자리는 비어 있다", () => {
  const L = layout(fridgeCab());
  assert.deepEqual(L.cavity, [-461, 0, -360, 461, 1869, 360]);
  assert.deepEqual(part(L, "side_l").box, [-479, 0, -360, -461, 2269, 360]);
  assert.ok(L.parts.some((p) => p.name.startsWith("upper")));
  for (const p of L.parts) assert.ok(!overlap(p.box, L.cavity), `${p.name}가 빈 공간에 들어와 있다`);
});

test("측판을 두껍게 하면 외경은 그대로, 측판 자리가 바뀌고 빈 공간이 줄어든다", () => {
  const L = layout(fridgeCab({ side_l: 25, filler_r: 20 }));
  assert.deepEqual(part(L, "side_l").box.slice(0, 1).concat(part(L, "side_l").box[3]), [-479, -454]);
  assert.equal(part(L, "filler_r").box[3], 479);
  assert.equal(L.cavity[3] - L.cavity[0], 958 - 25 - 18 - 20);
});

test("식기세척기 자리: 상판 아래 비어 있고, 걸레받이를 앞까지 이으면 판이 생긴다", () => {
  const L = layout(dwCab());
  assert.deepEqual(L.cavity, [-300, 0, -300, 300, 820, 300]);
  assert.ok(part(L, "counter") && !part(L, "kick"));
  const K = layout(dwCab({ kick_across: true }));
  assert.equal(part(K, "kick").box[4], 150);
});

test("유리 상부장: 유리판과 프레임이 나뉘고, 몸통·선반은 불투명", () => {
  const L = layout({ kind: "glass_wall", outer_mm: { w: 800, h: 700, d: 370 }, glass: "clear",
    parts: { side_l: 18, side_r: 18, back: 9, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, shelves: 2, doors: 2 },
    finish: { front: "warmwhite_matte", body: "warmwhite_matte", top: "stone_white", handle: "black" } });
  const roles = new Set(L.parts.map((p) => p.role));
  assert.ok(roles.has("glass") && roles.has("frame") && roles.has("shelf"));
  assert.equal(L.parts.filter((p) => p.role === "glass").length, 2);
  assert.ok(L.parts.filter((p) => p.role === "glass").every((p) => p.door), "유리는 문짝에만");
  assert.ok(L.parts.filter((p) => p.role === "shelf").length >= 2);
});

test("하부장·팬트리는 문짝·서랍 앞판과 손잡이를 따로 낸다", () => {
  const L = layout({ kind: "drawer", outer_mm: { w: 600, h: 850, d: 600 },
    parts: { side_l: 18, side_r: 18, back: 9, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, counter: 30, toe_kick: 150, toe_recess: 50, drawers: 3 },
    finish: { front: "sage_matte", body: "warmwhite_matte", top: "stone_white", handle: "steel" } });
  assert.equal(L.parts.filter((p) => p.role === "front").length, 3);
  assert.equal(L.parts.filter((p) => p.role === "handle").length, 3);
  const push = layout({ ...{ kind: "drawer", outer_mm: { w: 600, h: 850, d: 600 }, parts: { side_l: 18, side_r: 18, back: 9, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, counter: 30, toe_kick: 150, toe_recess: 50, drawers: 3 } },
    finish: { front: "sage_matte", body: "warmwhite_matte", top: "stone_white", handle: "push" } });
  assert.equal(push.parts.filter((p) => p.role === "handle").length, 0);
});

// 냉장고는 원점, 정면 +z(yaw = 90°) 방향
const FR = { xz: [0, 0], yaw: Math.PI / 2, base: 0, w: 914, h: 1860, d: 709, category: "refrigerator" };
const box = (id, label, cx, cz, w, d, h, y0 = 0) => ({ id, label, poly: [[cx - w / 2, cz - d / 2], [cx + w / 2, cz - d / 2], [cx + w / 2, cz + d / 2], [cx - w / 2, cz + d / 2]], y0, y1: y0 + h });

test("문짝 모양: 넓은 냉장고는 양문, 좁은 것은 한 문, 식기세척기는 아래 경첩", () => {
  assert.equal(doorsOf(FR).length, 2);
  assert.equal(doorsOf({ ...FR, w: 697, category: "kimchi_refrigerator" }).length, 1);
  assert.equal(doorsOf({ ...FR, w: 598, h: 815, d: 567, category: "dishwasher", bottomMm: 150 })[0].type, "bottom");
});

test("빈 곳에서는 90°까지 3°마다 열어 봐도 안 걸린다", () => {
  const r = doorCheck(FR, []);
  assert.equal(r.clear, true);
  assert.equal(STEP_DEG, 3);
  assert.equal(r.openDeg, OPEN_DEG);
  assert.ok(r.steps >= 30);
});

test("냉장고 문 앞 옆에 직각으로 붙은 장이 있으면 몇 도부터 걸리는지 알려 준다", () => {
  // 냉장고 앞면 z=0.3545, 오른쪽 문짝 경첩 x=0.457. 그 앞 0.2 m에 하부장이 가로질러 있다
  const cab = box("pl9", "옆 장", 0.5, 0.3545 + 0.2 + 0.3, 0.6, 0.6, 0.85);
  const r = doorCheck(FR, [cab]);
  assert.equal(r.clear, false);
  const hit = r.hits[0];
  assert.equal(hit.id, "pl9");
  assert.equal(hit.fromDeg % 3, 0);
  assert.ok(hit.fromDeg > 0 && hit.fromDeg <= 90);
  // 높이가 겹치지 않는 상부장은 걸리지 않는다
  assert.equal(doorCheck(FR, [box("pl8", "상부장", 0.5, 0.75, 0.6, 0.35, 0.7, 1.95)]).clear, true);
});

test("식기세척기 문: 걸레받이가 문 밑보다 높으면 걸리고, 낮추거나 빼면 풀린다", () => {
  const cabPl = { placement_id: "c1", sku: "decor:cab_dishwasher", center_xz: [0, 0], yaw_rad: Math.PI / 2, base_m: 0, size_m: [0.636, 0.85, 0.6], cab: dwCab({ kick_across: true, toe_kick: 170 }) };
  const dw = { xz: [0, -0.3 + 0.567 / 2], yaw: Math.PI / 2, base: 0, w: 598, h: 815, d: 567, category: "dishwasher", bottomMm: 150 };
  const tall = doorCheck(dw, cabObstacles(cabPl, { host: true }));
  assert.equal(tall.clear, false);
  assert.match(tall.hits[0].label, /걸레받이/);
  assert.equal(doorCheck(dw, cabObstacles({ ...cabPl, cab: dwCab({ kick_across: true, toe_kick: 150 }) }, { host: true })).clear, true);
  assert.equal(doorCheck(dw, cabObstacles({ ...cabPl, cab: dwCab({ kick_across: false, toe_kick: 170 }) }, { host: true })).clear, true);
});

test("식기세척기 문을 내리는 자리에 아일랜드가 있으면 걸린다", () => {
  const dw = { xz: [0, 0], yaw: Math.PI / 2, base: 0, w: 598, h: 815, d: 567, category: "dishwasher", bottomMm: 150 };
  const front = 0.567 / 2;
  assert.equal(doorCheck(dw, [box("is", "아일랜드", 0, front + 0.5 + 0.45, 1.8, 0.9, 0.9)]).clear, false);
  assert.equal(doorCheck(dw, [box("is", "아일랜드", 0, front + 0.8 + 0.45, 1.8, 0.9, 0.9)]).clear, true);
});

test("다른 장은 부재마다 걸림 대상이 되고, 손잡이는 따로 이름이 붙는다", () => {
  const pl = { placement_id: "d1", sku: "decor:cab_drawer", center_xz: [1, 1], yaw_rad: Math.PI / 2, base_m: 0, size_m: [0.6, 0.85, 0.6],
    cab: { kind: "drawer", outer_mm: { w: 600, h: 850, d: 600 }, parts: { side_l: 18, side_r: 18, back: 9, filler_l: 0, filler_r: 0, end_l: 0, end_r: 0, counter: 30, toe_kick: 150, toe_recess: 50, drawers: 3 },
      finish: { front: "sage_matte", body: "warmwhite_matte", top: "stone_white", handle: "steel" } } };
  const obs = cabObstacles(pl);
  assert.ok(obs.some((o) => /손잡이/.test(o.label)));
  assert.ok(obs.every((o) => o.poly.length === 4 && o.y1 > o.y0));
});
