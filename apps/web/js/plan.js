// 평면도 (SVG). 평면 좌표 (x, y) = 3D (x, z), 단위 m
import { esc, OBJ, PURPOSE } from "./core.js";

export function planView(svg, room, opts = {}) {
  const pts = room.walls.flatMap((w) => [w.start, w.end]);
  const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
  const pad = 0.5;
  svg.setAttribute("viewBox", `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`);
  const k = (maxX - minX + 2 * pad) / 600; // 화면 1px ≈ k m
  const sw = (px) => px * k;
  const wallLen = (w) => (w.measured?.length_m ?? w.scanned.length_m);
  let html = `<g class="grid">`;  // 1 m 격자
  for (let gx = Math.ceil(minX - pad); gx <= maxX + pad; gx++) html += `<line x1="${gx}" y1="${minY - pad}" x2="${gx}" y2="${maxY + pad}" style="stroke-width:${sw(1)}px"/>`;
  for (let gy = Math.ceil(minY - pad); gy <= maxY + pad; gy++) html += `<line x1="${minX - pad}" y1="${gy}" x2="${maxX + pad}" y2="${gy}" style="stroke-width:${sw(1)}px"/>`;
  html += `</g>`;
  for (const z of opts.zones || []) {
    const cls = z.purpose in { kitchen: 1, living: 1 } ? z.purpose : "other";
    const c = z.polygon_m.reduce((a, p) => [a[0] + p[0] / z.polygon_m.length, a[1] + p[1] / z.polygon_m.length], [0, 0]);
    html += `<polygon class="zone ${cls}" data-zone="${esc(z.zone_id)}" points="${z.polygon_m.map((p) => p.join(",")).join(" ")}" style="stroke-width:${sw(2)}px"/>`;
    html += `<text x="${c[0]}" y="${c[1]}" text-anchor="middle" style="font-size:${sw(13)}px;font-weight:700">${esc(z.name || PURPOSE[z.purpose] || z.purpose)}</text>`;
  }
  html += `<g id="overlay">${opts.overlay || ""}</g>`;
  const hidden = new Set(opts.hidden || []);
  for (const o of room.objects) {
    const [x, , zz] = o.position;
    const deg = (o.yaw_rad * 180) / Math.PI;
    const cls = `obj${hidden.has(o.object_id) ? " gone" : ""}${opts.selectedObj === o.object_id ? " sel" : ""}`;
    html += `<rect class="${cls}" data-obj="${esc(o.object_id)}" x="${x - o.bbox_m.w / 2}" y="${zz - o.bbox_m.d / 2}" width="${o.bbox_m.w}" height="${o.bbox_m.d}" transform="rotate(${deg} ${x} ${zz})" stroke-width="${sw(1)}"/>`;
    if (!hidden.has(o.object_id)) html += `<text x="${x}" y="${zz}" text-anchor="middle" dominant-baseline="middle" style="font-size:${sw(10)}px;pointer-events:none" fill="#6b6f76">${esc(OBJ[o.category] || o.category)}</text>`;
  }
  for (const w of room.walls) {
    const sel = opts.selectedWall === w.wall_id ? " sel" : "";
    html += `<line class="wall${w.measured ? " measured" : ""}${sel}" data-wall="${w.wall_id}" x1="${w.start[0]}" y1="${w.start[1]}" x2="${w.end[0]}" y2="${w.end[1]}" style="stroke-width:${sw(6)}px;cursor:pointer"/>`;
    const mx = (w.start[0] + w.end[0]) / 2, my = (w.start[1] + w.end[1]) / 2;
    const dx = w.end[0] - w.start[0], dy = w.end[1] - w.start[1], L = Math.hypot(dx, dy) || 1;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    let nx = -dy / L, ny = dx / L;
    if ((mx + nx - cx) ** 2 + (my + ny - cy) ** 2 < (mx - cx) ** 2 + (my - cy) ** 2) { nx = -nx; ny = -ny; }
    html += `<text x="${mx + nx * sw(22)}" y="${my + ny * sw(22)}" text-anchor="middle" dominant-baseline="middle" style="font-size:${sw(11)}px">${w.wall_id} ${wallLen(w).toFixed(3)}m</text>`;
  }
  const walls = Object.fromEntries(room.walls.map((w) => [w.wall_id, w]));
  for (const o of room.openings) {
    const w = walls[o.wall_id];
    if (!w) continue;
    const dx = w.end[0] - w.start[0], dy = w.end[1] - w.start[1], L = Math.hypot(dx, dy) || 1;
    const a = o.offset_m / L, b = (o.offset_m + o.width_m) / L;
    html += `<line class="${o.type === "window" ? "window" : "door"}" x1="${w.start[0] + dx * a}" y1="${w.start[1] + dy * a}" x2="${w.start[0] + dx * b}" y2="${w.start[1] + dy * b}" style="stroke-width:${sw(8)}px"/>`;
  }
  for (const p of opts.placements || []) html += placedSvg(p, sw, opts.selectedPl === p.placement_id);
  if (opts.northDeg != null) {  // 나침반: 평면도 오른쪽 위
    const r = sw(18), cx = maxX + pad - sw(26), cy = minY - pad + sw(26);
    html += `<g class="compass" transform="rotate(${opts.northDeg} ${cx} ${cy})"><circle cx="${cx}" cy="${cy}" r="${r}" style="stroke-width:${sw(1)}px"/>
      <path d="M ${cx} ${cy - r * 0.85} L ${cx + r * 0.32} ${cy + r * 0.2} L ${cx} ${cy} L ${cx - r * 0.32} ${cy + r * 0.2} Z"/>
      <text x="${cx}" y="${cy - r - sw(4)}" text-anchor="middle" style="font-size:${sw(11)}px;font-weight:700">N</text></g>`;
  }
  {  // 축척 막대 1 m: 평면도 왼쪽 아래
    const x0 = minX - pad + sw(14), y0 = maxY + pad - sw(14), t = sw(4);
    html += `<g class="scale"><path d="M ${x0} ${y0 - t} V ${y0} H ${x0 + 1} V ${y0 - t}" style="stroke-width:${sw(1.5)}px"/>
      <text x="${x0 + 0.5}" y="${y0 - sw(7)}" text-anchor="middle" style="font-size:${sw(10)}px">1 m</text></g>`;
  }
  html += `<g id="ghost"></g><g id="draft"></g>`;
  svg.innerHTML = html;
  const toWorld = (ev) => {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const snap = (v) => Math.round(v / 0.05) * 0.05;
    return [snap(p.x), snap(p.y)];
  };
  return { toWorld, sw };
}

// 배치 제품 사각형 (yaw = 정면 방향, 폭 축 = yaw - 90°). 정면 쪽 변에 굵은 선
export function placedSvg(p, sw, selected = false, ghost = false) {
  const [w_, , d_] = p.size_m;
  const deg = ((p.yaw_rad - Math.PI / 2) * 180) / Math.PI;
  const [x, y] = p.center_xz;
  const v = p.verdict || "unknown";
  return `<g class="placed v-${v}${selected ? " sel" : ""}${ghost ? " ghost" : ""}" ${p.placement_id ? `data-pl="${esc(p.placement_id)}"` : ""} transform="rotate(${deg} ${x} ${y})">
    <rect x="${x - w_ / 2}" y="${y - d_ / 2}" width="${w_}" height="${d_}" style="fill:${esc(p.hex || "#fff")};stroke-width:${sw(selected ? 3 : 2)}px"/>
    <line x1="${x - w_ / 2}" y1="${y + d_ / 2}" x2="${x + w_ / 2}" y2="${y + d_ / 2}" class="front" style="stroke-width:${sw(4)}px"/></g>`;
}

