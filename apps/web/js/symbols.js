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
export function roomOutline(walls, tol = 0.15) {
  // 서버 worker/outline.py와 같은 규칙: 벽 끝을 모서리로 묶고, 중간에 붙은 벽에서 나누고, 떠 있는 벽을 뗀 뒤 바깥을 한 바퀴 돈다
  const nodes = [];
  const nid = (p) => {
    const i = nodes.findIndex((q) => Math.hypot(p[0] - q[0], p[1] - q[1]) <= tol);
    return i >= 0 ? i : nodes.push([p[0], p[1]]) - 1;
  };
  const raw = walls.map((w) => [nid(w.start), nid(w.end)]);
  const adj = new Map();
  const link = (u, v) => { if (u === v) return; for (const [x, y] of [[u, v], [v, u]]) (adj.get(x) || adj.set(x, new Set()).get(x)).add(y); };
  for (const [a, b] of raw) {
    if (a === b) continue;
    const [ax, ay] = nodes[a], dx = nodes[b][0] - ax, dy = nodes[b][1] - ay, L2 = dx * dx + dy * dy;
    const on = [];
    nodes.forEach(([cx, cy], c) => {
      if (c === a || c === b) return;
      const t = ((cx - ax) * dx + (cy - ay) * dy) / L2;
      if (t > 0 && t < 1 && Math.hypot(ax + t * dx - cx, ay + t * dy - cy) <= tol) on.push([t, c]);
    });
    const chain = [a, ...on.sort((p, q) => p[0] - q[0]).map((x) => x[1]), b];
    chain.slice(1).forEach((v, i) => link(chain[i], v));
  }
  const loose = [...adj].filter(([, nb]) => nb.size < 2).map(([n]) => n);
  while (loose.length) {
    const n = loose.pop();
    for (const m of adj.get(n) || []) { adj.get(m).delete(n); if (adj.get(m).size < 2) loose.push(m); }
    adj.delete(n);
  }
  if (adj.size < 3) return null;
  const start = [...adj.keys()].sort((p, q) => nodes[p][0] - nodes[q][0] || nodes[p][1] - nodes[q][1])[0];
  const turn = (v, back) => [...adj.get(v)].map((w) => {
    const a = (Math.atan2(nodes[w][1] - nodes[v][1], nodes[w][0] - nodes[v][0]) - back) % (2 * Math.PI);
    return [(a + 2 * Math.PI) % (2 * Math.PI) || 2 * Math.PI, w];
  }).sort((p, q) => p[0] - q[0])[0][1];
  const first = turn(start, Math.PI), path = [start];
  let v = start, nxt = first, closed = false;
  for (let i = 0; i < 4 * walls.length + 16 && !closed; i++) {
    const back = Math.atan2(nodes[v][1] - nodes[nxt][1], nodes[v][0] - nodes[nxt][0]);
    [v, nxt] = [nxt, turn(nxt, back)];
    if (v === start && nxt === first) closed = true;
    else path.push(v);
  }
  if (!closed) return null;
  const pts = path.map((i) => nodes[i]);
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
  const out = pts.filter((p, i) => Math.abs(cross(pts[(i - 1 + pts.length) % pts.length], p, pts[(i + 1) % pts.length])) > 1e-6);
  return out.length >= 3 ? out : null;
}
