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
  base: "하부장", tall: "키큰장", glass_tall: "유리 키큰장", low: "낮은 수납장", low_wall: "벽걸이 하부장", corner: "코너장",
  island_storage: "수납형 아일랜드", tvwall: "TV월", oven_tall: "오븐·전자레인지 키큰장", cooktop_base: "인덕션 하부장", hood_cab: "후드 상부장",
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
  if (NEW_KINDS.has(kind)) return layoutMore(cab);
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

// ---------- 벽면 맞춤가구 모듈 (하부장·키큰장·상부장·낮은장·코너·아일랜드·TV월·가전 매입부) ----------
const NEW_KINDS = new Set(["base", "wall", "tall", "glass_tall", "low", "low_wall", "corner", "island_storage", "tvwall", "oven_tall",
  "cooktop_base", "hood_cab"]);
const COUNTER_KINDS = new Set(["base", "cooktop_base", "corner"]);
const HANG_KINDS = new Set(["wall", "hood_cab", "low_wall"]);

// 손잡이: 문 앞면(z)에서 앞으로 나온다. dir = -1이면 뒤쪽 면(아일랜드 뒤 수납)
function grip(cab, out, name, x, y, z, vertical, dir = 1) {
  if (cab.finish?.handle === "push") return;
  const L = 160, T = 12, z0 = dir > 0 ? z : z - HANDLE_OUT, z1 = dir > 0 ? z + HANDLE_OUT : z;
  out.push(bx(name, "handle", vertical ? [x - T / 2, y - L / 2, z0, x + T / 2, y + L / 2, z1] : [x - L / 2, y - T / 2, z0, x + L / 2, y + T / 2, z1]));
}

// 몸통 상자: 좌우 측판(장 틀이 이미 있으면 생략)·바닥·천판·뒷판
function carcass(out, pre, x0, x1, y0, y1, zb, zf, { back = 9, sides = true, top = true } = {}) {
  if (sides) {
    out.push(bx(`${pre}side_l`, "body", [x0, y0, zb, x0 + PANEL, y1, zf]));
    out.push(bx(`${pre}side_r`, "body", [x1 - PANEL, y0, zb, x1, y1, zf]));
  }
  const a = sides ? x0 + PANEL : x0, b = sides ? x1 - PANEL : x1;
  out.push(bx(`${pre}bottom`, "body", [a, y0, zb + back, b, y0 + PANEL, zf]));
  if (top) out.push(bx(`${pre}top_panel`, "body", [a, y1 - PANEL, zb + back, b, y1, zf]));
  if (back > 0) out.push(bx(`${pre}back`, "body", [a, y0, zb, b, y1, zb + back]));
  return [a, b];
}

// 앞면 구성: door(여닫이) · drawer(서랍) · open(문 없음) · pullout(인출 한 판) · flap(위로 여는 한 판)
function fronts(cab, out, style, x0, x1, y0, y1, zf, { pre = "", n = 1, drawers = 3, handleLow = false, glass = false, dir = 1 } = {}) {
  const zA = dir > 0 ? zf - DOOR : zf, zB = dir > 0 ? zf : zf + DOOR, zH = dir > 0 ? zf : zf + DOOR;
  if (style === "open") return;
  if (style === "drawer") {
    const k = Math.max(1, drawers);
    const first = k > 1 ? (y1 - y0) * (k >= 3 ? 0.24 : 0.4) : y1 - y0, rest = k > 1 ? (y1 - y0 - first) / (k - 1) : 0;
    let y = y1;
    for (let i = 0; i < k; i++) {
      const h = i === 0 ? first : rest;
      out.push(bx(`${pre}drawer${i + 1}`, "front", [x0, y - h + GAP / 2, zA, x1, y - GAP / 2, zB], { door: true, open: "drawer", dir }));
      grip(cab, out, `${pre}drawer${i + 1}_handle`, (x0 + x1) / 2, y - Math.min(60, h / 2), zH, false, dir);
      y -= h;
    }
    return;
  }
  if (style === "pullout" || style === "flap") {
    out.push(bx(`${pre}door1`, "front", [x0 + GAP / 2, y0, zA, x1 - GAP / 2, y1, zB], { door: true, open: style, dir }));
    grip(cab, out, `${pre}door1_handle`, (x0 + x1) / 2, style === "flap" ? y0 + 50 : y1 - 60, zH, false, dir);
    return;
  }
  const k = Math.max(1, n), wEach = (x1 - x0) / k, hinge = cab.parts?.hinge;
  for (let i = 0; i < k; i++) {
    const a = x0 + i * wEach + GAP / 2, b = x0 + (i + 1) * wEach - GAP / 2, name = `${pre}door${i + 1}`;
    // 한 짝: 경첩 쪽(hinge) 반대편에 손잡이. 두 짝 이상: 가운데 쪽
    const side = k === 1 ? (hinge === "l" ? "l" : "r") : i < k / 2 ? "l" : "r";
    const meta = { door: true, open: "door", hinge: side, dir };
    if (glass) {
      const R = 22;
      out.push(bx(`${name}_frame_l`, "frame", [a, y0, zA, a + R, y1, zB], meta));
      out.push(bx(`${name}_frame_r`, "frame", [b - R, y0, zA, b, y1, zB], meta));
      out.push(bx(`${name}_frame_b`, "frame", [a + R, y0, zA, b - R, y0 + R, zB], meta));
      out.push(bx(`${name}_frame_t`, "frame", [a + R, y1 - R, zA, b - R, y1, zB], meta));
      out.push(bx(`${name}_glass`, "glass", [a + R, y0 + R, (zA + zB) / 2 - 2, b - R, y1 - R, (zA + zB) / 2 + 2], meta));
    } else {
      out.push(bx(name, "front", [a, y0, zA, b, y1, zB], meta));
    }
    const hx = side === "l" ? b - 40 : a + 40;
    const hy = handleLow ? y0 + 120 : y1 - y0 > 1200 ? y0 + Math.min(1000, (y1 - y0) / 2) : y1 - 120;
    grip(cab, out, `${name}_handle`, hx, hy, zH, true, dir);
  }
}

function shelfRow(out, pre, n, x0, x1, y0, y1, zb, zf) {
  for (let i = 1; i <= n; i++) {
    const y = y0 + ((y1 - y0) * i) / (n + 1);
    out.push(bx(`${pre}shelf${i}`, "shelf", [x0, y - PANEL / 2, zb, x1, y + PANEL / 2, zf]));
  }
}

const doorCount = (cab, w) => (P(cab, "doors") > 0 ? P(cab, "doors") : w > 650 ? 2 : 1);

function mirrorX(parts) {
  for (const p of parts) {
    const [x0, y0, z0, x1, y1, z1] = p.box;
    p.box = [-x1, y0, z0, -x0, y1, z1];
    if (p.hinge) p.hinge = p.hinge === "l" ? "r" : "l";
  }
  return parts;
}

function layoutMore(cab) {
  const { w: W, h: H, d: D } = cab.outer_mm;
  const kind = cab.kind, out = [], zb = -D / 2;
  const style = cab.parts?.style || (kind === "low_wall" ? "drawer" : "door");
  const back = P(cab, "back");
  if (kind === "corner") {
    // ㄱ자: 이 벽(A)을 따라 폭 W, 꺾인 쪽(B)은 앞으로 leg_b. 겹치지 않게 A는 B 몸통 앞에서 끝난다 (오른쪽 꺾임 기준으로 그린 뒤 왼쪽이면 뒤집는다)
    const LB = Math.max(P(cab, "leg_b"), D + 100), ct = P(cab, "counter"), tk = P(cab, "toe_kick"), top = H - ct;
    const zf = D / 2 - OVERHANG, xB = W / 2 - D, zEnd = zb + LB, zEndF = zEnd - OVERHANG;
    carcass(out, "a_", -W / 2, xB, tk, top, zb, zf - DOOR, { back, top: false });
    carcass(out, "b_", xB, W / 2, tk, top, zb, zEndF, { back, top: false });
    if (tk > 0) {
      const r = P(cab, "toe_recess") || KICK_RECESS;
      out.push(bx("a_kick", "kick", [-W / 2, 0, zf - r - PANEL, xB + D - r, tk, zf - r]));
      out.push(bx("b_kick", "kick", [xB + r, 0, zf - r, xB + r + PANEL, tk, zEndF - r]));
    }
    if (ct > 0) {
      out.push(bx("counter", "top", [-W / 2, top, zb, xB, H, D / 2]));
      out.push(bx("counter_b", "top", [xB, top, zb, W / 2, H, zEnd]));
    }
    const fy0 = tk + GAP, fy1 = top - GAP;
    if (cab.parts?.door_leg === "b") {
      // 꺾인 쪽 문: 왼쪽(-x)을 보는 면
      out.push(bx("door1", "front", [xB - DOOR, fy0, D / 2 + GAP, xB, fy1, zEndF], { door: true, open: "door", face: "x-", hinge: "r" }));
      if (cab.finish?.handle !== "push") out.push(bx("door1_handle", "handle", [xB - DOOR - HANDLE_OUT, fy1 - 200, zEndF - 52, xB - DOOR, fy1 - 40, zEndF - 40]));
    } else {
      fronts(cab, out, "door", -W / 2 + 1, xB - 1, fy0, fy1, zf, { n: doorCount(cab, W - D) });
    }
    shelfRow(out, "a_", P(cab, "shelves"), -W / 2 + PANEL, xB - PANEL, tk + PANEL, top, zb + back, zf - DOOR - 4);
    return { parts: cab.parts?.corner === "l" ? mirrorX(out) : out, cavity: null, legB: { mm: LB, side: cab.parts?.corner === "l" ? "l" : "r" } };
  }
  if (kind === "island_storage") {
    const ct = P(cab, "counter"), tk = P(cab, "toe_kick"), oh = P(cab, "overhang"), top = H - ct, st = cab.parts?.storage || "front";
    const zf0 = st === "back" ? zb + OVERHANG : st === "both" ? zb + OVERHANG : zb + oh;
    const zf1 = st === "front" ? D / 2 - OVERHANG : st === "both" ? D / 2 - OVERHANG : D / 2 - oh;
    const wall = cab.parts?.attach_wall;
    const x0 = -W / 2 + (wall ? 20 : 0), x1 = W / 2;
    carcass(out, "", x0, x1, tk, top, zf0 + DOOR, zf1 - DOOR, { back: 0, top: false });
    if (tk > 0) out.push(bx("kick", "kick", [x0 + 50, 0, zf0 + 50, x1 - 50, tk, zf1 - 50]));
    if (wall) out.push(bx("end_l", "body", [-W / 2, 0, zb, -W / 2 + 20, H, D / 2])); // 벽에 붙는 쪽 마감판 (반도형)
    if (ct > 0) out.push(bx("counter", "top", [wall ? -W / 2 + 20 : -W / 2, top, zb, W / 2, H, D / 2]));
    const cols = Math.max(1, Math.round((x1 - x0) / 600)), cw = (x1 - x0 - 2 * PANEL) / cols;
    for (let i = 0; i < cols; i++) {
      const a = x0 + PANEL + i * cw, b = a + cw;
      if (st !== "back") fronts(cab, out, "drawer", a + 1, b - 1, tk + GAP, top - GAP, zf1, { pre: `f${i + 1}_`, drawers: P(cab, "drawers") || 3 });
      if (st !== "front") fronts(cab, out, "drawer", a + 1, b - 1, tk + GAP, top - GAP, zf0, { pre: `b${i + 1}_`, drawers: P(cab, "drawers") || 3, dir: -1 });
    }
    return { parts: out, cavity: null, seat: st === "both" ? null : st === "front" ? "back" : "front" };
  }
  if (kind === "tvwall") {
    // 가운데 TV 칸은 비우고, 좌우 키큰 수납·아래 미디어장·위 수납장
    const sw = P(cab, "side_w"), mh = P(cab, "media_h"), uh = P(cab, "upper_h"), zf = D / 2;
    const cx0 = -W / 2 + sw, cx1 = W / 2 - sw;
    for (const [pre, a, b] of [["l_", -W / 2, cx0], ["r_", cx1, W / 2]]) {
      if (b - a < 2 * PANEL + 10) continue;
      const [ia, ib] = carcass(out, pre, a, b, 0, H, zb, zf - DOOR, { back });
      shelfRow(out, pre, P(cab, "shelves"), ia, ib, PANEL, H - PANEL, zb + back, zf - DOOR - 4);
      fronts({ ...cab, parts: { ...cab.parts, hinge: pre === "l_" ? "r" : "l" } }, out, "door", a + 1, b - 1, GAP, H - GAP, zf, { pre, n: b - a > 650 ? 2 : 1 });
    }
    if (mh > 0) {
      carcass(out, "m_", cx0, cx1, 0, mh, zb, zf - DOOR, { back });
      fronts(cab, out, "drawer", cx0 + 1, cx1 - 1, GAP, mh - GAP, zf, { pre: "m_", drawers: 1 });
    }
    if (uh > 0) {
      carcass(out, "u_", cx0, cx1, H - uh, H, zb, zf - DOOR, { back });
      fronts(cab, out, "door", cx0 + 1, cx1 - 1, H - uh + GAP, H - GAP, zf, { pre: "u_", n: Math.max(2, Math.round((cx1 - cx0) / 600)), handleLow: true });
    }
    if (back > 0) out.push(bx("tv_back", "body", [cx0, mh, zb, cx1, H - uh, zb + back]));
    if (cab.parts?.cable) out.push(bx("cable", "cable", [-40, mh, zb + back, 40, H - uh, zb + back + 25]));
    return { parts: out, cavity: [cx0, mh, zb + back, cx1, H - uh, D / 2], vent: P(cab, "vent") };
  }
  const counter = COUNTER_KINDS.has(kind), hung = HANG_KINDS.has(kind);
  const ct = counter ? P(cab, "counter") : 0, tk = hung ? 0 : P(cab, "toe_kick");
  const zf = counter ? D / 2 - OVERHANG : D / 2, top = H - ct;
  const [xl, xr] = frame(cab, out, 0, top, zb, zf - DOOR);
  out.push(bx("bottom", "body", [xl, tk, zb + back, xr, tk + PANEL, zf - DOOR]));
  if (!counter) out.push(bx("top_panel", "body", [xl, top - PANEL, zb + back, xr, top, zf - DOOR]));
  if (back > 0) out.push(bx("back", "body", [xl, tk, zb, xr, top, zb + back]));
  if (tk > 0) { const r = P(cab, "toe_recess") || KICK_RECESS; out.push(bx("kick", "kick", [xl, 0, zf - r - PANEL, xr, tk, zf - r])); }
  const fx0 = -W / 2 + P(cab, "filler_l") + P(cab, "end_l") + 1, fx1 = W / 2 - P(cab, "filler_r") - P(cab, "end_r") - 1;
  const fy0 = tk + GAP, fy1 = top - GAP, inZ = zf - DOOR - 4;
  const glass = kind === "glass_tall";
  let cavity = null;
  if (kind === "oven_tall" || (kind === "tall" && style === "homecafe")) {
    // 가운데 칸: 오븐장은 가전 자리(뒷판 없음), 홈카페장은 열린 칸. 아래·위는 문이나 서랍
    const ny = Math.max(tk + PANEL, P(cab, "niche_y")), nh = Math.min(P(cab, "niche_h"), top - PANEL - ny);
    out.push(bx("niche_bottom", "body", [xl, ny - PANEL, zb + back, xr, ny, zf - DOOR]));
    out.push(bx("niche_top", "body", [xl, ny + nh, zb + back, xr, ny + nh + PANEL, zf - DOOR]));
    if (kind === "oven_tall") fronts(cab, out, "drawer", fx0, fx1, fy0, ny - PANEL - GAP, zf, { pre: "low_", drawers: P(cab, "drawers") || 2 });
    else {
      fronts(cab, out, "door", fx0, fx1, fy0, ny - PANEL - GAP, zf, { pre: "low_", n: doorCount(cab, W) });
      shelfRow(out, "low_", 1, xl, xr, tk + PANEL, ny - PANEL, zb + back, inZ);
    }
    if (top - PANEL - (ny + nh + PANEL) > 60) {
      fronts(cab, out, "door", fx0, fx1, ny + nh + PANEL + GAP, fy1, zf, { pre: "up_", n: doorCount(cab, W), handleLow: true });
      shelfRow(out, "up_", 1, xl, xr, ny + nh + PANEL, top - PANEL, zb + back, inZ);
    }
    if (kind === "oven_tall") cavity = [xl, ny, zb + back, xr, ny + nh, zf];
  } else if (kind === "cooktop_base") {
    fronts(cab, out, "drawer", fx0, fx1, fy0, fy1, zf, { drawers: P(cab, "drawers") || 2 });
  } else {
    const st = kind === "glass_tall" || kind === "hood_cab" ? "door" : style;
    const handleLow = kind === "wall" || kind === "hood_cab";
    if (st !== "drawer") {
      const nS = kind === "hood_cab" ? 0 : P(cab, "shelves");
      shelfRow(out, "", nS, xl, xr, tk + PANEL, top - PANEL, zb + back, inZ);
    }
    fronts(cab, out, st, fx0, fx1, fy0, fy1, zf, { n: doorCount(cab, fx1 - fx0), drawers: P(cab, "drawers") || 3, handleLow, glass });
  }
  if (ct > 0) {
    const cw = P(cab, "cutout_w"), cd = P(cab, "cutout_d");
    if (kind === "cooktop_base" && cw > 0 && cd > 0 && cw < W - 40 && cd < D - 40) {
      // 공식 타공 치수를 넣은 경우만 상판에 구멍
      const a = -cw / 2, b = cw / 2, c = (zb + D / 2) / 2 - cd / 2 + 20, e = c + cd;
      out.push(bx("counter_back", "top", [-W / 2, top, zb, W / 2, H, c]));
      out.push(bx("counter_front", "top", [-W / 2, top, e, W / 2, H, D / 2]));
      out.push(bx("counter_l", "top", [-W / 2, top, c, a, H, e]));
      out.push(bx("counter_r", "top", [b, top, c, W / 2, H, e]));
      cavity = [a, top, c, b, H, e];
    } else out.push(bx("counter", "top", [-W / 2, top, zb, W / 2, H, D / 2]));
  }
  return { parts: out, cavity };
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
