// 지금 집(방·배치·치운 것)을 전파 계산 입력으로 바꾼다. DOM 없음 (Worker·테스트에서도 쓴다)
import { MATERIALS } from "./materials.js";
import { roomOutline } from "../symbols.js";

const WALL_SKUS = { "decor:wall": "drywall", "decor:partition": "wood" }; // 가벽은 석고보드, 파티션은 패널
const HOLE_SKUS = { "decor:door": "door", "decor:window": "window", "decor:glassdoor": "window" };
export const ANTENNA_UP_M = 0.15; // 공유기 놓인 면에서 안테나 가운데까지

const inPoly = (p, poly) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if (zi > p[1] !== zj > p[1] && p[0] < ((xj - xi) * (p[1] - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
};
const wallH = (w) => w.measured?.height_m || w.scanned?.height_m || 2.4;

/** 바깥벽인지: 벽 가운데에서 양쪽으로 조금 나가 보고 한쪽이 집 밖이면 바깥벽 */
function isOuter(w, poly, box) {
  const mx = (w.start[0] + w.end[0]) / 2, mz = (w.start[1] + w.end[1]) / 2;
  const dx = w.end[0] - w.start[0], dz = w.end[1] - w.start[1], L = Math.hypot(dx, dz) || 1;
  const nx = -dz / L, nz = dx / L, k = 0.3;
  if (poly) return inPoly([mx + nx * k, mz + nz * k], poly) !== inPoly([mx - nx * k, mz - nz * k], poly);
  const near = (v, a) => Math.abs(v - a) < 0.2;
  return (near(w.start[0], box[0]) && near(w.end[0], box[0])) || (near(w.start[0], box[2]) && near(w.end[0], box[2]))
    || (near(w.start[1], box[1]) && near(w.end[1], box[1])) || (near(w.start[1], box[3]) && near(w.end[1], box[3]));
}
/** 재질을 안 정한 벽: 바깥벽(세대 경계)은 철근콘크리트, 안쪽 벽은 콘크리트로 본다 */
export const guessMaterial = (outer) => (outer ? "reinforced_concrete" : "concrete");

/**
 * room: room.json, ss: project.scene_state, categoryOf(sku): LG 제품 category (가구면 null)
 * 반환: { input (prepare에 넣을 것), router, outline, bounds, walls: [{id, material, guessed, outer, name}] }
 */
export function wifiScene(room, ss = {}, categoryOf = () => null) {
  const gone = new Set(ss.hidden_walls || []), shut = new Set(ss.hidden_openings || []), hiddenObj = new Set(ss.hidden_objects || []);
  const chosen = ss.wall_materials || {};
  const standing = (room.walls || []).filter((w) => !gone.has(w.wall_id));
  const outline = roomOutline(standing);
  const xs = standing.flatMap((w) => [w.start[0], w.end[0]]), zs = standing.flatMap((w) => [w.start[1], w.end[1]]);
  const box = xs.length ? [Math.min(...xs), Math.min(...zs), Math.max(...xs), Math.max(...zs)] : [0, 0, 1, 1];
  const walls = [], info = [];
  for (const w of standing) {
    const outer = isOuter(w, outline, box), pick = chosen[w.wall_id];
    const material = MATERIALS[pick] ? pick : guessMaterial(outer);
    walls.push({ id: w.wall_id, a: w.start, b: w.end, h: wallH(w), t: MATERIALS[material].t_ref, material });
    info.push({ id: w.wall_id, material, guessed: !MATERIALS[pick], outer });
  }
  const openings = (room.openings || []).filter((o) => o.wall_id && !gone.has(o.wall_id) && !shut.has(o.opening_id)).map((o) => ({
    id: o.opening_id, wall: o.wall_id, kind: o.type === "window" ? "window" : o.type === "door" ? "door" : "open",
    u0: o.offset_m, u1: o.offset_m + o.width_m, z0: o.sill_m || 0, z1: (o.sill_m || 0) + o.height_m,
  }));
  const objects = [], holes = [];
  for (const x of ss.placements || []) {
    if (!x.size_m) continue;
    const [w, h, d] = x.size_m, ang = (x.yaw_rad ?? Math.PI / 2) - Math.PI / 2; // 놓은 것은 폭 방향이 yaw - 90°
    const base = x.base_m || 0, c = x.center_xz;
    if (WALL_SKUS[x.sku]) {
      const ux = Math.cos(ang) * (w / 2), uz = Math.sin(ang) * (w / 2);
      const material = MATERIALS[chosen[x.placement_id]] ? chosen[x.placement_id] : WALL_SKUS[x.sku];
      walls.push({ id: x.placement_id, a: [c[0] - ux, c[1] - uz], b: [c[0] + ux, c[1] + uz], h: base + h, t: MATERIALS[material].t_ref, material });
      info.push({ id: x.placement_id, material, guessed: !MATERIALS[chosen[x.placement_id]], outer: false, added: true });
      continue;
    }
    if (HOLE_SKUS[x.sku]) { holes.push({ x, kind: HOLE_SKUS[x.sku], w, h, base: x.sku === "decor:window" ? base : 0, ang }); continue; }
    const kind = categoryOf(x.sku) || x.sku;
    objects.push({ id: x.placement_id, kind, c, ang, w, d, y0: base, y1: base + h });
  }
  // 벽에 단 문·창: 가장 가까운 나란한 벽에 구멍으로 붙인다
  for (const { x, kind, w, h, base, ang } of holes) {
    let best = null;
    for (const v of walls) {
      const dx = v.b[0] - v.a[0], dz = v.b[1] - v.a[1], L = Math.hypot(dx, dz) || 1;
      if (Math.abs(Math.cos(ang) * dx / L + Math.sin(ang) * dz / L) < 0.9) continue;
      const u = ((x.center_xz[0] - v.a[0]) * dx + (x.center_xz[1] - v.a[1]) * dz) / L;
      const off = Math.abs((x.center_xz[0] - v.a[0]) * -dz / L + (x.center_xz[1] - v.a[1]) * dx / L);
      if (u < -0.1 || u > L + 0.1 || off > 0.35) continue;
      if (!best || off < best.off) best = { v, u, off };
    }
    if (best) openings.push({ id: x.placement_id, wall: best.v.id, kind, u0: best.u - w / 2, u1: best.u + w / 2, z0: base, z1: base + h });
  }
  const poses = ss.object_poses || {};
  for (const o of room.objects || []) {
    if (hiddenObj.has(o.object_id)) continue;
    const q = poses[o.object_id];
    const c = q ? q.center_xz : [o.position[0], o.position[2]], yaw = q ? q.yaw_rad : o.yaw_rad || 0;
    const y0 = o.position[1] - o.bbox_m.h / 2;
    objects.push({ id: o.object_id, kind: o.category, c, ang: yaw, w: o.bbox_m.w, d: o.bbox_m.d, y0: Math.max(0, y0), y1: y0 + o.bbox_m.h });
  }
  const rt = ss.router;
  const router = rt ? { xz: rt.center_xz, h: (rt.height_m || 0) + ANTENNA_UP_M, band: rt.band || "5", width: rt.channel_mhz, enclosure: rt.enclosure || "open" } : null;
  return { input: { walls, openings, objects }, router, outline, bounds: [box[0] - 0.05, box[1] - 0.05, box[2] + 0.05, box[3] + 0.05], walls: info,
    inside: (p) => (outline ? inPoly(p, outline) : p[0] > box[0] && p[0] < box[2] && p[1] > box[1] && p[1] < box[3]) };
}
