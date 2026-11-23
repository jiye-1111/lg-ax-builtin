// 둘러보기에서 들를 곳과 그 사이 길 (apps/web/js/stops.js). 실행: node --test tests/web/*.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { buildWorld, isBlocked } from "../../apps/web/js/walk.js";
import { tourStops, findPath, lookYaw, nearestStop } from "../../apps/web/js/stops.js";

// 6 m × 4 m 방. 아래 벽(w3)에 문, 오른쪽 벽(w2)에 큰 창, 위 벽에 작은 창
const ROOM = {
  walls: [
    { wall_id: "w1", start: [0, 0], end: [6, 0], thickness_m: 0.1 },
    { wall_id: "w2", start: [6, 0], end: [6, 4], thickness_m: 0.1 },
    { wall_id: "w3", start: [6, 4], end: [0, 4], thickness_m: 0.1 },
    { wall_id: "w4", start: [0, 4], end: [0, 0], thickness_m: 0.1 },
  ],
  openings: [
    { opening_id: "d1", type: "door", wall_id: "w3", offset_m: 4.5, width_m: 0.9 },
    { opening_id: "win1", type: "window", wall_id: "w2", offset_m: 1.0, width_m: 2.4 },
    { opening_id: "win2", type: "window", wall_id: "w1", offset_m: 1.0, width_m: 0.8 },
  ],
  objects: [
    { object_id: "o1", category: "table", position: [3, 0.37, 2], bbox_m: { w: 1.4, h: 0.74, d: 0.8 }, yaw_rad: 0 },
    { object_id: "o2", category: "chair", position: [3, 0.4, 1.3], bbox_m: { w: 0.45, h: 0.8, d: 0.45 }, yaw_rad: 0 },
    { object_id: "o3", category: "sofa", position: [5.3, 0.4, 0.6], bbox_m: { w: 1.2, h: 0.8, d: 0.8 }, yaw_rad: 0 },
  ],
};
// 왼쪽 벽에 붙인 냉장고 (yaw 0 = +x가 방 안쪽)
const FRIDGE = { placement_id: "pl1", sku: "F1", center_xz: [0.45, 2], size_m: [0.9, 1.8, 0.7], yaw_rad: 0 };
const NAMES = { objects: { table: "테이블", sofa: "소파", chair: "의자" }, placement: (p) => (p.sku === "F1" ? "냉장고" : null) };
const stopsOf = (pls = [FRIDGE], hidden = []) => tourStops(ROOM, pls, hidden, buildWorld(ROOM, pls, hidden), NAMES);

test("문 앞에서 시작하고 창 앞, 가구 앞, 놓은 가전 앞에 들른다", () => {
  const names = stopsOf().map((s) => s.name);
  assert.equal(names[0], "현관");
  for (const n of ["창 앞", "테이블 앞", "소파 앞", "냉장고 앞"]) assert.ok(names.includes(n), `${n} 없음: ${names}`);
  assert.ok(!names.includes("의자 앞"), "의자마다 들르지 않는다");
  assert.equal(new Set(names).size, names.length, "같은 이름이 두 번 나오지 않는다");
});

test("서는 자리는 모두 걸을 수 있는 곳이고 서로 떨어져 있다", () => {
  const world = buildWorld(ROOM, [FRIDGE]);
  const stops = stopsOf();
  for (const s of stops) assert.ok(!isBlocked(s.pos, world), `${s.name} 자리가 막혀 있다`);
  for (let i = 0; i < stops.length; i++) for (let j = i + 1; j < stops.length; j++)
    assert.ok(Math.hypot(stops[i].pos[0] - stops[j].pos[0], stops[i].pos[1] - stops[j].pos[1]) > 0.5);
});

test("현관에서는 방 안쪽을, 가전 앞에서는 가전을, 창 앞에서는 창밖을 본다", () => {
  const stops = stopsOf();
  const fwd = (s) => [-Math.sin(s.yaw), -Math.cos(s.yaw)];
  const door = stops[0];
  assert.ok(fwd(door)[1] < -0.7, "문은 아래 벽이라 위쪽(-y)을 본다");
  const fr = stops.find((s) => s.name === "냉장고 앞");
  assert.ok(fr.pos[0] > FRIDGE.center_xz[0] + 0.8 && fwd(fr)[0] < -0.9, "냉장고 정면에서 냉장고를 본다");
  const win = stops.find((s) => s.name === "창 앞");
  assert.ok(win.pos[0] > 4.5 && fwd(win)[0] > 0.9, "큰 창(오른쪽 벽) 앞에서 밖을 본다");
});

test("가전을 안 놓았거나 가구를 치우면 그 곳은 빠진다", () => {
  assert.ok(!stopsOf([]).some((s) => s.name === "냉장고 앞"));
  assert.ok(!stopsOf([], ["o3"]).some((s) => s.name === "소파 앞"));
});

test("문이 없는 방도 들를 곳이 하나는 있다", () => {
  const room = { ...ROOM, openings: [], objects: [] };
  const stops = tourStops(room, [], [], buildWorld(room), NAMES);
  assert.ok(stops.length >= 1);
});

test("들를 곳은 여덟 곳을 넘지 않는다", () => {
  const many = Array.from({ length: 12 }, (_, i) => ({ ...FRIDGE, placement_id: `p${i}`, sku: `S${i}`, center_xz: [0.45 + (i % 6) * 0.95, i < 6 ? 0.45 : 3.5], yaw_rad: i < 6 ? Math.PI / 2 : -Math.PI / 2 }));
  const names = { ...NAMES, placement: (p) => `가전${p.sku}` };
  const stops = tourStops({ ...ROOM, objects: [] }, many, [], buildWorld({ ...ROOM, objects: [] }, many), names);
  assert.ok(stops.length <= 8, String(stops.length));
});

test("길은 가구를 돌아서 간다", () => {
  const world = buildWorld(ROOM, [FRIDGE]);
  const path = findPath([3, 3.2], [3, 0.5], world); // 테이블과 의자를 사이에 두고
  assert.ok(path && path.length > 2);
  assert.deepEqual(path[0], [3, 3.2]);
  assert.deepEqual(path[path.length - 1], [3, 0.5]);
  for (const p of path) assert.ok(!isBlocked(p, world, 0.15), `길이 가구를 지난다: ${p}`);
  for (let i = 1; i < path.length; i++) assert.ok(Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) < 0.5, "길이 끊기지 않는다");
});

test("갈 수 없는 곳이면 길이 없다", () => {
  const world = buildWorld(ROOM, []);
  assert.equal(findPath([3, 3.2], [9, 9], world), null);
});

test("보는 방향: yaw 0은 -z, 왼쪽으로 돌면 커진다", () => {
  assert.ok(Math.abs(lookYaw([0, 0], [0, -1])) < 1e-9);
  assert.ok(Math.abs(lookYaw([0, 0], [-1, 0]) - Math.PI / 2) < 1e-9);
});

test("지금 선 곳에서 가까운 들를 곳을 찾는다", () => {
  const stops = stopsOf();
  assert.equal(nearestStop(stops, stops[2].pos), 2);
  assert.equal(nearestStop(stops, [-50, -50]), -1);
});

test("가구 위를 고르면 그 옆 설 수 있는 자리를 준다", async () => {
  const { nearFree } = await import("../../apps/web/js/stops.js");
  const world = buildWorld(ROOM, []);
  const p = nearFree([3, 2], world); // 테이블 한가운데
  assert.ok(p && !isBlocked(p, world) && Math.hypot(p[0] - 3, p[1] - 2) < 1.5);
  assert.equal(nearFree([30, 30], world), null);
});
