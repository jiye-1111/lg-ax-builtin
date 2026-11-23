// 평면도 가구 기호. 가운데가 (0, 0), 폭은 x, 깊이는 y, 앞쪽이 +y (등받이·벽 쪽이 -y). 단위 m.
// 네모 상자 대신 건축 평면도에서 쓰는 모양으로 그려 무엇인지 글자 없이 알아보게 한다.
const r2 = (v) => +v.toFixed(3);
const box = (x, y, w, h, rx = 0, cls = "") => `<rect${cls ? ` class="${cls}"` : ""} x="${r2(x)}" y="${r2(y)}" width="${r2(Math.max(w, 0.01))}" height="${r2(Math.max(h, 0.01))}"${rx ? ` rx="${r2(rx)}"` : ""}/>`;
const line = (x1, y1, x2, y2) => `<line class="ln" x1="${r2(x1)}" y1="${r2(y1)}" x2="${r2(x2)}" y2="${r2(y2)}"/>`;
const ring = (cx, cy, r, cls = "") => `<circle${cls ? ` class="${cls}"` : ""} cx="${r2(cx)}" cy="${r2(cy)}" r="${r2(Math.max(r, 0.01))}"/>`;

const DOOR_M = 0.55;      // 수납장 문 한 짝 폭
const CUSHION_M = 0.75;   // 소파 방석 하나 폭

function sofa(w, d) {
  const arm = Math.min(0.18, w * 0.12), back = d * 0.26, n = Math.max(1, Math.round((w - 2 * arm) / CUSHION_M)), cw = (w - 2 * arm) / n;
  let s = box(-w / 2, -d / 2, w, d, 0.08) + box(-w / 2, -d / 2, w, back, 0.07, "soft");
  s += box(-w / 2, -d / 2 + back * 0.5, arm, d - back * 0.5, 0.06, "soft") + box(w / 2 - arm, -d / 2 + back * 0.5, arm, d - back * 0.5, 0.06, "soft");
  for (let i = 0; i < n; i++) s += box(-w / 2 + arm + cw * i + 0.02, -d / 2 + back + 0.02, cw - 0.04, d - back - 0.06, 0.06);
  return s;
}
function chair(w, d) {
  const back = d * 0.2;
  return box(-w / 2 + 0.03, -d / 2 + back * 0.6, w - 0.06, d - back * 0.6 - 0.02, 0.07) + box(-w / 2, -d / 2, w, back, back / 2, "soft");
}
function table(w, d) {
  const inset = Math.min(0.06, w * 0.08, d * 0.08);
  return box(-w / 2, -d / 2, w, d, 0.05) + box(-w / 2 + inset, -d / 2 + inset, w - 2 * inset, d - 2 * inset, 0.03, "ln");
}
function bed(w, d) {
  const head = Math.min(0.1, d * 0.06), n = w > 1.3 ? 2 : 1, pw = (w - 0.2) / n, fold = -d / 2 + head + d * 0.3;
  let s = box(-w / 2, -d / 2, w, d, 0.05) + box(-w / 2, -d / 2, w, head, 0.03, "soft");
  for (let i = 0; i < n; i++) s += box(-w / 2 + 0.1 + pw * i + 0.03, -d / 2 + head + 0.06, pw - 0.06, d * 0.16, 0.07);
  s += box(-w / 2 + 0.03, fold, w - 0.06, d / 2 - fold - 0.03, 0.05, "soft") + line(-w / 2 + 0.03, fold + d * 0.07, w / 2 - 0.03, fold + d * 0.07);
  return s;
}
function cabinet(w, d, { counter = false, bowl = false } = {}) {
  const n = Math.max(1, Math.round(w / DOOR_M)), front = d / 2 - Math.min(0.04, d * 0.1);
  let s = box(-w / 2, -d / 2, w, d, 0.02) + line(-w / 2, front, w / 2, front);
  for (let i = 1; i < n; i++) s += line(-w / 2 + (w / n) * i, counter ? front : -d / 2, -w / 2 + (w / n) * i, d / 2);
  if (bowl) { const bw = Math.min(0.5, w * 0.5), bd = d * 0.5; s += box(-bw / 2, -bd / 2 - d * 0.04, bw, bd, 0.06, "soft") + ring(0, -d / 2 + d * 0.12, 0.03); }
  return s;
}
function plant(w, d) {
  const r = Math.min(w, d) / 2;
  let s = "";
  for (let i = 0; i < 6; i++) { const a = (Math.PI * 2 * i) / 6; s += ring(Math.cos(a) * r * 0.5, Math.sin(a) * r * 0.5, r * 0.5, "soft"); }
  return s + ring(0, 0, r * 0.28);
}
function lamp(w, d) {
  const r = Math.min(w, d) / 2;
  return ring(0, 0, r, "soft") + ring(0, 0, r * 0.45) + line(-r * 0.2, 0, r * 0.2, 0) + line(0, -r * 0.2, 0, r * 0.2);
}
function rug(w, d) {
  const inset = Math.min(0.12, w * 0.08);
  return box(-w / 2, -d / 2, w, d, 0.04, "soft") + box(-w / 2 + inset, -d / 2 + inset, w - 2 * inset, d - 2 * inset, 0.02, "ln dash");
}
const plain = (w, d) => box(-w / 2, -d / 2, w, d, 0.03);

const DRAW = {
  sofa, chair, table, coffee: table, desk: table, bed, plant, lamp, rug,
  storage: cabinet, wardrobe: cabinet, tallcab: cabinet, tvstand: cabinet, shelf: cabinet, dresser: cabinet,
  basecab: (w, d) => cabinet(w, d, { counter: true }), island: (w, d) => cabinet(w, d, { counter: true }),
  sink: (w, d) => cabinet(w, d, { counter: true, bowl: true }),
};

/** 기호가 따로 있는 종류인지 (없으면 네모 + 이름) */
export const hasSymbol = (kind) => kind in DRAW;

/** 가구 기호 SVG 조각. 모르는 종류는 네모 */
export function furnitureSymbol(kind, w, d) {
  return (DRAW[kind] || plain)(Math.max(w, 0.05), Math.max(d, 0.05));
}

/** 벽을 끝점끼리 이어 방 테두리를 만든다. 한 바퀴로 이어지지 않으면 null (바닥을 잘못 칠하지 않게) */
export function roomOutline(walls, tol = 0.05) {
  if (walls.length < 3) return null;
  const near = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) <= tol;
  const left = walls.slice(1), pts = [walls[0].start, walls[0].end];
  while (left.length) {
    const tip = pts[pts.length - 1];
    const i = left.findIndex((w) => near(w.start, tip) || near(w.end, tip));
    if (i < 0) return null;
    const [w] = left.splice(i, 1);
    pts.push(near(w.start, tip) ? w.end : w.start);
  }
  return near(pts[0], pts[pts.length - 1]) ? pts.slice(0, -1) : null;
}
