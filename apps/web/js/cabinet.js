// 빌트인 주방 맞춤장: 부재 배치(3D가 그대로 쓴다)와 가전 문 열림 3D 근사 검사.
// 규칙은 docs/specs/builtin-kitchen.md. 안쪽 치수 계산·LG 공식 기준 판정은 서버(recommender/cabinet.py, cabinet_fit.py)가 한다.
// 장 좌표(mm): 바닥 가운데가 원점, x = 정면에서 봤을 때 오른쪽, y = 위, z = 정면(앞). 3D 모델과 같은 방향이다.
// 세계 좌표(m): 평면 (x, z), yaw = 정면 방향, 폭 축 = yaw - 90° (slot.js와 같다).

export const STEP_DEG = 3;      // 문을 이만큼씩 열어 보며 걸리는지 본다 (지예: 최대 3도 간격)
export const OPEN_DEG = 90;     // 이만큼까지 열어 본다
export const LEAF_T_MM = 60;    // 가전 문짝 두께 (근사)
const PANEL = 18, DOOR = 18, OVERHANG = 20, GAP = 2, HANDLE_OUT = 30, EPS = 1;
const KICK_RECESS = 50;
export const FRIDGES = new Set(["refrigerator", "kimchi_refrigerator", "freezer"]);
const PAIR_MIN_W = 800;

export const KIND_LABEL = {
  fridge: "냉장고장", dishwasher: "식기세척기 자리", sink: "싱크 하부장", drawer: "서랍형 하부장", wall: "상부장",
  pantry: "키큰 팬트리장", glass_wall: "유리 상부장", counter: "연속 상판", filler: "틈막이판", end_panel: "측면 마감판",
};
const BASE_KINDS = new Set(["sink", "drawer", "dishwasher"]);

const P = (cab, k) => cab.parts?.[k] ?? 0;
const bx = (name, role, box, more = {}) => ({ name, role, box: box.map((v) => Math.round(v * 10) / 10), ...more });

// 좌우 틀: 바깥부터 틈막이판 → 마감판 → 측판. 안쪽 가장자리를 돌려준다
function frame(cab, out, y0, y1, zBack, zFront) {
  const { w } = cab.outer_mm;
  let xl = -w / 2, xr = w / 2;
  const side = (s, sign) => {
    const fill = P(cab, `filler_${s}`), end = P(cab, `end_${s}`), panel = P(cab, `side_${s}`);
    const at = (x0, t) => (sign < 0 ? [x0, x0 + t] : [x0 - t, x0]);
    let x = sign < 0 ? xl : xr;
    if (fill > 0) { const [a, b] = at(x, fill); out.push(bx(`filler_${s}`, "body", [a, y0, zFront - 20, b, y1, zFront])); x += sign < 0 ? fill : -fill; }
    if (end > 0) { const [a, b] = at(x, end); out.push(bx(`end_${s}`, "body", [a, y0, zBack, b, y1, zFront])); x += sign < 0 ? end : -end; }
    if (panel > 0) { const [a, b] = at(x, panel); out.push(bx(`side_${s}`, "body", [a, y0, zBack, b, y1, zFront])); x += sign < 0 ? panel : -panel; }
    return x;
  };
  xl = side("l", -1);
  xr = side("r", 1);
  return [xl, xr];
}

function handle(cab, out, name, x, y, z, vertical) {
  if (cab.finish?.handle === "push") return;
  const L = 160, T = 12;
  out.push(bx(name, "handle", vertical ? [x - T / 2, y - L / 2, z, x + T / 2, y + L / 2, z + HANDLE_OUT]
    : [x - L / 2, y - T / 2, z, x + L / 2, y + T / 2, z + HANDLE_OUT]));
}

// 문짝 n개를 [x0, x1] × [y0, y1]에 나란히. 상부장은 손잡이를 아래쪽에, 키큰장·하부장은 위쪽에
function doors(cab, out, n, x0, x1, y0, y1, zf, { handleLow = false, glass = false } = {}) {
  if (n <= 0) return;
  const wEach = (x1 - x0) / n;
  for (let i = 0; i < n; i++) {
    const a = x0 + i * wEach + GAP / 2, b = x0 + (i + 1) * wEach - GAP / 2;
    const name = `door${i + 1}`;
    if (glass) { // 유리문: 프레임 네 변 + 가운데 유리판 (유리만 비친다)
      const R = 22;
      out.push(bx(`${name}_frame_l`, "frame", [a, y0, zf - DOOR, a + R, y1, zf], { door: true }));
      out.push(bx(`${name}_frame_r`, "frame", [b - R, y0, zf - DOOR, b, y1, zf], { door: true }));
      out.push(bx(`${name}_frame_b`, "frame", [a + R, y0, zf - DOOR, b - R, y0 + R, zf], { door: true }));
      out.push(bx(`${name}_frame_t`, "frame", [a + R, y1 - R, zf - DOOR, b - R, y1, zf], { door: true }));
      out.push(bx(`${name}_glass`, "glass", [a + R, y0 + R, zf - DOOR / 2 - 2, b - R, y1 - R, zf - DOOR / 2 + 2], { door: true }));
    } else {
      out.push(bx(name, "front", [a, y0, zf - DOOR, b, y1, zf], { door: true }));
    }
    // 손잡이는 여는 쪽 끝: 한 짝이면 오른쪽, 두 짝이면 가운데 쪽
    const openRight = n === 1 ? true : i < n / 2;
    const hx = openRight ? b - 40 : a + 40;
    const hy = handleLow ? y0 + 120 : n === 1 && y1 - y0 > 1200 ? y0 + Math.min(1000, (y1 - y0) / 2) : y1 - 120;
    handle(cab, out, `${name}_handle`, hx, hy, zf, true);
  }
}

function shelves(cab, out, n, x0, x1, y0, y1, zb, zf) {
  for (let i = 1; i <= n; i++) {
    const y = y0 + ((y1 - y0) * i) / (n + 1);
    out.push(bx(`shelf${i}`, "shelf", [x0, y - PANEL / 2, zb, x1, y + PANEL / 2, zf]));
  }
}

/** 장 설정(cab) → {parts: [{name, role, box: [x0, y0, z0, x1, y1, z1], door?}], cavity: 가전 자리 상자 | null}.
 *  role: body(몸통·측판·마감판·틈막이·뒷판) · front(문짝·서랍 앞판) · top(상판) · handle(손잡이) · frame(유리문 프레임)
 *        · glass(유리판) · shelf(선반) · kick(걸레받이) · bowl(싱크볼) · faucet(수전) */
export function layout(cab) {
  const { w: W, h: H, d: D } = cab.outer_mm;
  const out = [];
  const zb = -D / 2;
  const kind = cab.kind;
  if (kind === "counter") return { parts: [bx("counter", "top", [-W / 2, 0, zb, W / 2, H, D / 2])], cavity: null };
  if (kind === "filler" || kind === "end_panel") return { parts: [bx(kind, "body", [-W / 2, 0, zb, W / 2, H, D / 2])], cavity: null };
  if (kind === "fridge") {
    const uh = P(cab, "upper_h");
    const [xl, xr] = frame(cab, out, 0, H, zb, D / 2);
    const back = P(cab, "back");
    if (back > 0) out.push(bx("back", "body", [xl, 0, zb, xr, H - uh, zb + back]));
    if (uh > 0) {
      const y0 = H - uh;
      out.push(bx("upper_bottom", "body", [xl, y0, zb, xr, y0 + PANEL, D / 2 - DOOR]));
      out.push(bx("upper_top", "body", [xl, H - PANEL, zb, xr, H, D / 2 - DOOR]));
      out.push(bx("upper_back", "body", [xl, y0 + PANEL, zb, xr, H - PANEL, zb + 9]));
      doors(cab, out, P(cab, "doors") || 2, xl + 1, xr - 1, y0 + GAP, H - GAP, D / 2, { handleLow: true });
      for (const p of out) if (p.name.startsWith("door")) p.name = `upper_${p.name}`;
    }
    return { parts: out, cavity: [xl, 0, zb + back, xr, H - uh, D / 2] };
  }
  if (kind === "dishwasher") {
    const ct = P(cab, "counter");
    const [xl, xr] = frame(cab, out, 0, H - ct, zb, D / 2);
    if (ct > 0) out.push(bx("counter", "top", [-W / 2, H - ct, zb, W / 2, H, D / 2]));
    const back = P(cab, "back");
    if (back > 0) out.push(bx("back", "body", [xl, 0, zb, xr, H - ct, zb + back]));
    if (cab.parts?.kick_across) out.push(bx("kick", "kick", [xl, 0, D / 2 - KICK_RECESS - PANEL, xr, P(cab, "toe_kick"), D / 2 - KICK_RECESS]));
    return { parts: out, cavity: [xl, 0, zb + back, xr, H - ct, D / 2] };
  }
  const base = BASE_KINDS.has(kind);
  const ct = base ? P(cab, "counter") : 0;
  const tk = kind === "wall" || kind === "glass_wall" ? 0 : P(cab, "toe_kick");
  const zf = base ? D / 2 - OVERHANG : D / 2;      // 문짝 앞면
  const top = H - ct;
  const [xl, xr] = frame(cab, out, 0, top, zb, zf - DOOR);
  const back = P(cab, "back");
  out.push(bx("bottom", "body", [xl, tk, zb + back, xr, tk + PANEL, zf - DOOR]));
  if (!base) out.push(bx("top_panel", "body", [xl, top - PANEL, zb + back, xr, top, zf - DOOR]));
  if (back > 0) out.push(bx("back", "body", [xl, tk, zb, xr, top, zb + back]));
  if (tk > 0) out.push(bx("kick", "kick", [xl, 0, zf - (P(cab, "toe_recess") || KICK_RECESS) - PANEL, xr, tk, zf - (P(cab, "toe_recess") || KICK_RECESS)]));
  const fx0 = -W / 2 + P(cab, "filler_l") + P(cab, "end_l") + 1, fx1 = W / 2 - P(cab, "filler_r") - P(cab, "end_r") - 1;
  const fy0 = tk + GAP, fy1 = top - GAP;
  if (kind === "drawer") {
    const n = Math.max(1, P(cab, "drawers") || 3);
    const first = n > 1 ? (fy1 - fy0) * 0.24 : fy1 - fy0, rest = n > 1 ? (fy1 - fy0 - first) / (n - 1) : 0;
    let y = fy1;
    for (let i = 0; i < n; i++) {
      const h = i === 0 ? first : rest;
      out.push(bx(`drawer${i + 1}`, "front", [fx0, y - h + GAP / 2, zf - DOOR, fx1, y - GAP / 2, zf], { door: true }));
      handle(cab, out, `drawer${i + 1}_handle`, (fx0 + fx1) / 2, y - Math.min(60, h / 2), zf, false);
      y -= h;
    }
  } else {
    shelves(cab, out, P(cab, "shelves"), xl, xr, tk + PANEL, top - (base ? 0 : PANEL), zb + back, zf - DOOR - 4);
    doors(cab, out, P(cab, "doors") || 1, fx0, fx1, fy0, fy1, zf, { handleLow: kind === "wall" || kind === "glass_wall", glass: kind === "glass_wall" });
  }
  if (ct > 0) {
    if (kind === "sink" && cab.parts?.bowl) {
      // 싱크볼 자리만 상판을 비우고, 볼은 얇은 판 다섯 장(바닥 + 네 벽)으로
      const bw = Math.min(W - 160, 760), bd = Math.min(D - 160, 440), bz = (zb + D / 2) / 2 + 10, deep = 200;
      const a = -bw / 2, b = bw / 2, c = bz - bd / 2, e = bz + bd / 2;
      out.push(bx("counter_back", "top", [-W / 2, top, zb, W / 2, H, c]));
      out.push(bx("counter_front", "top", [-W / 2, top, e, W / 2, H, D / 2]));
      out.push(bx("counter_l", "top", [-W / 2, top, c, a, H, e]));
      out.push(bx("counter_r", "top", [b, top, c, W / 2, H, e]));
      out.push(bx("bowl_bottom", "bowl", [a, H - deep, c, b, H - deep + 2, e]));
      out.push(bx("bowl_back", "bowl", [a, H - deep, c, b, H, c + 2]));
      out.push(bx("bowl_front", "bowl", [a, H - deep, e - 2, b, H, e]));
      out.push(bx("bowl_l", "bowl", [a, H - deep, c, a + 2, H, e]));
      out.push(bx("bowl_r", "bowl", [b - 2, H - deep, c, b, H, e]));
      const fz = c - 45;
      out.push(bx("faucet_post", "faucet", [-15, H, fz - 15, 15, H + 300, fz + 15]));
      out.push(bx("faucet_spout", "faucet", [-11, H + 270, fz, 11, H + 300, fz + 230]));
    } else {
      out.push(bx("counter", "top", [-W / 2, top, zb, W / 2, H, D / 2]));
    }
  }
  return { parts: out, cavity: null };
}

// ---------- 세계 좌표 ----------
const axes = (yaw) => ({ u: [Math.cos(yaw - Math.PI / 2), Math.sin(yaw - Math.PI / 2)], f: [Math.cos(yaw), Math.sin(yaw)] });

/** 장 부재를 문 열림 검사용 걸림 대상으로 (세계 m). host: 가전이 들어간 그 장이면 true (이름이 짧아진다) */
export function cabObstacles(pl, { host = false } = {}) {
  const { u, f } = axes(pl.yaw_rad);
  const [cx, cz] = pl.center_xz, base = pl.base_m || 0;
  const label = KIND_LABEL[pl.cab.kind] || "장";
  const name = (p) => {
    if (p.role === "handle") return host ? "손잡이" : `옆 ${label} 손잡이`;
    if (p.role === "kick") return "걸레받이";
    if (host) return p.name.startsWith("side") ? "측판" : p.name.startsWith("upper") ? "위 수납장" : p.name.startsWith("filler") ? "틈막이판"
      : p.name.startsWith("end") ? "측면 마감판" : p.role === "top" ? "상판" : "장";
    return p.role === "front" || p.role === "frame" || p.role === "glass" ? `옆 ${label} 문` : `옆 ${label}`;
  };
  return layout(pl.cab).parts.map((p) => {
    const [x0, y0, z0, x1, y1, z1] = p.box;
    const at = (a, b) => [cx + (u[0] * a + f[0] * b) / 1000, cz + (u[1] * a + f[1] * b) / 1000];
    return { id: pl.placement_id, part: p.name, label: name(p), poly: [at(x0, z0), at(x1, z0), at(x1, z1), at(x0, z1)],
      y0: base + y0 / 1000, y1: base + y1 / 1000 };
  });
}

/** 상자 하나(놓은 가구·가전·스캔 가구)를 걸림 대상으로 */
export function boxObstacle(id, label, center, yaw, w, d, y0, y1) {
  const { u, f } = axes(yaw);
  const at = (a, b) => [center[0] + u[0] * a + f[0] * b, center[1] + u[1] * a + f[1] * b];
  return { id, label, poly: [at(-w / 2, -d / 2), at(w / 2, -d / 2), at(w / 2, d / 2), at(-w / 2, d / 2)], y0, y1 };
}

// ---------- 문 열림 ----------
/** 가전 문짝 근사: 넓은 냉장고는 양문(가운데에서 열림), 좁은 것은 한 문(오른쪽 경첩), 식기세척기는 아래 경첩 */
export function doorsOf(app) {
  if (FRIDGES.has(app.category)) {
    if (app.w >= PAIR_MIN_W) return [{ type: "side", hinge: -1, width: app.w / 2 }, { type: "side", hinge: 1, width: app.w / 2 }];
    return [{ type: "side", hinge: 1, width: app.w }];
  }
  if (app.category === "dishwasher") return [{ type: "bottom", bottom: app.bottomMm ?? 150, assumed: app.bottomMm == null }];
  return [];
}

// 문짝 하나의 θ도 모양 (가전 좌표 mm). side: 평면 사각형 [[x, z]…], bottom: 옆에서 본 사각형 [[z, y]…]
export function leaf(app, door, deg) {
  const t = (deg * Math.PI) / 180, zf = app.d / 2, T = LEAF_T_MM;
  if (door.type === "side") {
    const s = door.hinge, P0 = [s * app.w / 2, zf];
    const dir = [-s * Math.cos(t), Math.sin(t)], back = [-s * Math.sin(t), -Math.cos(t)];
    const L = door.width;
    return [P0, [P0[0] + L * dir[0], P0[1] + L * dir[1]], [P0[0] + L * dir[0] + T * back[0], P0[1] + L * dir[1] + T * back[1]], [P0[0] + T * back[0], P0[1] + T * back[1]]];
  }
  const P0 = [zf, door.bottom], L = app.h - door.bottom;
  const dir = [Math.sin(t), Math.cos(t)], back = [-Math.cos(t), Math.sin(t)];
  return [P0, [P0[0] + L * dir[0], P0[1] + L * dir[1]], [P0[0] + L * dir[0] + T * back[0], P0[1] + L * dir[1] + T * back[1]], [P0[0] + T * back[0], P0[1] + T * back[1]]];
}

// 볼록 다각형 둘이 EPS보다 깊게 겹치는지 (분리축)
function hit(a, b) {
  for (const poly of [a, b]) {
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i], q = poly[(i + 1) % poly.length];
      const n = [q[1] - p[1], p[0] - q[0]], len = Math.hypot(n[0], n[1]) || 1;
      let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
      for (const v of a) { const s = (v[0] * n[0] + v[1] * n[1]) / len; a0 = Math.min(a0, s); a1 = Math.max(a1, s); }
      for (const v of b) { const s = (v[0] * n[0] + v[1] * n[1]) / len; b0 = Math.min(b0, s); b1 = Math.max(b1, s); }
      if (Math.min(a1, b1) - Math.max(a0, b0) <= EPS) return false;
    }
  }
  return true;
}

/** 가전 문을 STEP_DEG마다 OPEN_DEG까지 열어 보며 걸리는 것을 찾는다 (3D 근사. LG 공식 기준이 아니다).
 *  app {xz, yaw, base (m), w, h, d (mm), category, bottomMm?} · obstacles [{id, label, poly (세계 m), y0, y1}]
 *  → {clear, hits: [{id, part, label, fromDeg, door}], steps, stepDeg, openDeg, doors} */
export function doorCheck(app, obstacles, { stepDeg = STEP_DEG, openDeg = OPEN_DEG } = {}) {
  const ds = doorsOf(app);
  const { u, f } = axes(app.yaw);
  const loc = obstacles.map((o) => {
    const pts = o.poly.map(([x, z]) => {
      const dx = (x - app.xz[0]) * 1000, dz = (z - app.xz[1]) * 1000;
      return [dx * u[0] + dz * u[1], dx * f[0] + dz * f[1]];
    });
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
    return { o, pts, x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs),
      y0: (o.y0 - (app.base || 0)) * 1000, y1: (o.y1 - (app.base || 0)) * 1000 };
  });
  const angles = [];
  for (let a = stepDeg; a < openDeg - 1e-9; a += stepDeg) angles.push(Math.round(a * 1000) / 1000);
  angles.push(openDeg);
  const hits = new Map();
  ds.forEach((door, di) => {
    for (const deg of angles) {
      const shape = leaf(app, door, deg);
      for (const L of loc) {
        const key = `${L.o.id}|${L.o.part || ""}|${di}`;
        if (hits.has(key)) continue;
        let bad;
        if (door.type === "side") {
          bad = Math.min(app.h, L.y1) - Math.max(0, L.y0) > EPS && hit(shape, L.pts);
        } else {
          bad = Math.min(app.w / 2, L.x1) - Math.max(-app.w / 2, L.x0) > EPS
            && hit(shape, [[L.z0, L.y0], [L.z1, L.y0], [L.z1, L.y1], [L.z0, L.y1]]);
        }
        if (bad) hits.set(key, { id: L.o.id, part: L.o.part || null, label: L.o.label, fromDeg: deg, door: di });
      }
    }
  });
  const list = [...hits.values()].sort((a, b) => a.fromDeg - b.fromDeg);
  return { clear: list.length === 0, hits: list, steps: angles.length, stepDeg, openDeg, doors: ds.length, assumed: ds.some((d) => d.assumed) };
}

/** 그리기용: θ도 문짝의 세계 좌표 꼭짓점 8개 [[x, y, z]…] (아래 4개 → 위 4개) */
export function leafCorners(app, door, deg) {
  const { u, f } = axes(app.yaw);
  const W = (a, b, y) => [app.xz[0] + (u[0] * a + f[0] * b) / 1000, (app.base || 0) + y / 1000, app.xz[1] + (u[1] * a + f[1] * b) / 1000];
  const s = leaf(app, door, deg);
  if (door.type === "side") return [...s.map(([x, z]) => W(x, z, 0)), ...s.map(([x, z]) => W(x, z, app.h))];
  return [...s.map(([z, y]) => W(-app.w / 2, z, y)), ...s.map(([z, y]) => W(app.w / 2, z, y))];
}
