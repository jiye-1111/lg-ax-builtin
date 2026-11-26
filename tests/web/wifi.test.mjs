// 와이파이 전파 계산 (apps/web/js/wifi). 완료 기준을 시나리오별로 고정한다.
import test from "node:test";
import assert from "node:assert/strict";
import { prepare, trace, field, bestSpots, CAUSE_KINDS } from "../../apps/web/js/wifi/propagation.js";
import { wallLoss, materialOf, objectRf } from "../../apps/web/js/wifi/materials.js";
import { colorAt, simulateCvd, contourKind } from "../../apps/web/js/wifi/palette.js";

const ONLY_DIRECT = { reflection: false, diffraction: false };
const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg ?? ""} ${a} ≈ ${b} ± ${tol}`);
const R = (xz, band = "5", extra = {}) => ({ xz, h: 1.0, band, ...extra });
const wall = (id, a, b, material = "concrete", t = 0.15, h = 2.4) => ({ id, a, b, material, t, h });

// 바깥벽 없는 빈 바닥에 칸막이 하나 (x = 4)
const partition = (extra = {}) => prepare({ walls: [wall("p", [4, -3], [4, 3], extra.material, extra.t)], openings: extra.openings || [], objects: extra.objects || [] });

test("주파수: 같은 조건이면 5 GHz가 2.4 GHz보다 어디서나 약하고, 1 m에서 약 6.4 dB 차이", () => {
  const sc = prepare({ walls: [], openings: [], objects: [] });
  const one24 = trace(sc, R([0, 0], "2.4"), [1, 0], { rxH: 1, causes: ONLY_DIRECT });
  const one5 = trace(sc, R([0, 0], "5"), [1, 0], { rxH: 1, causes: ONLY_DIRECT });
  near(one24.rssi - one5.rssi, 6.4, 0.3, "1 m 차이");
  near(20 - one24.rssi, 40.2, 0.5, "2.4 GHz 1 m 손실");
  const one6 = trace(sc, R([0, 0], "6"), [1, 0], { rxH: 1, causes: ONLY_DIRECT });
  near(20 - one6.rssi, 48.2, 0.5, "6 GHz 1 m 손실");
  const sc2 = partition();
  for (const p of [[1, 0], [3, 2], [6, 0], [7.5, -2.5], [0.2, 0.1]]) {
    const a = trace(sc2, R([2, 0], "2.4"), p, { rxH: 1 }).rssi, b = trace(sc2, R([2, 0], "5"), p, { rxH: 1 }).rssi;
    assert.ok(b < a, `${p}: 5 GHz ${b} < 2.4 GHz ${a}`);
  }
});

test("거리는 3D로 잰다: 공유기 높이가 다르면 더 멀다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [] });
  const flat = trace(sc, R([0, 0], "5", { h: 1 }), [2, 0], { rxH: 1, causes: ONLY_DIRECT });
  const high = trace(sc, R([0, 0], "5", { h: 2 }), [2, 0], { rxH: 0, causes: ONLY_DIRECT, antenna: false });
  near(flat.rssi - high.rssi, 20 * Math.log10(Math.hypot(2, 2) / 2), 0.05);
});

test("콘크리트 150 mm 벽 하나는 5 GHz에서 약 22 dB, 300 mm면 약 44 dB", () => {
  const free = trace(prepare({ walls: [], openings: [], objects: [] }), R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT }).rssi;
  const w150 = trace(partition(), R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT }).rssi;
  const w300 = trace(partition({ t: 0.3 }), R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT }).rssi;
  near(free - w150, 22, 0.01);
  near(free - w300, 44, 0.01);
  assert.equal(wallLoss("concrete", "5", 1.0), 60, "벽 하나 상한");
});

test("비스듬히 지나면 더 잃되 +10 dB까지만", () => {
  const sc = partition();
  const straight = trace(sc, R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT });
  const slant = trace(sc, R([2.5, -1]), [5.5, 1], { rxH: 1, causes: ONLY_DIRECT });
  const wallDb = (t) => -t.contributions.filter((c) => c.kind === "wall").reduce((s, c) => s + c.db, 0);
  near(wallDb(straight), 22, 0.01);
  near(wallDb(slant), 22 / Math.cos(Math.atan2(2, 3)), 0.05, "34° 비스듬히");
  const graze = trace(sc, R([3.9, -2.9]), [4.1, 2.9], { rxH: 1, causes: ONLY_DIRECT });
  near(wallDb(graze), 32, 0.01, "75° 넘으면 22 + 10");
});

test("개구부를 지나는 길은 벽 손실이 0이고, 창이면 유리 손실만", () => {
  const door = { id: "d", wall: "p", kind: "door", u0: 2.5, u1: 3.5, z0: 0, z1: 2.1 };
  const win = { id: "w", wall: "p", kind: "window", u0: 4.5, u1: 5.5, z0: 0.9, z1: 2.1 };
  const sc = partition({ openings: [door, win] });
  const free = prepare({ walls: [], openings: [], objects: [] });
  const viaDoor = trace(sc, R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT });
  near(viaDoor.rssi, trace(free, R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT }).rssi, 0.01, "문");
  const viaWin = trace(sc, R([2, 2]), [6, 2], { rxH: 1.2, causes: ONLY_DIRECT });
  const walls = viaWin.contributions.filter((c) => c.kind === "wall");
  assert.equal(walls.length, 1);
  near(-walls[0].db, materialOf("double_glass").loss[1], 0.3, "창은 복층 유리");
  // 창 아래(허리 높이 밑)로 지나가면 벽이다
  const under = trace(sc, R([2, 2], "5", { h: 0.3 }), [6, 2], { rxH: 0.3, causes: ONLY_DIRECT });
  near(-under.contributions.filter((c) => c.kind === "wall")[0].db, 22, 0.01, "창 아래는 콘크리트");
  // 문 뒤쪽은 신호가 새어 나간다: 문 정면이 옆 벽 뒤보다 훨씬 세다
  const behindDoor = trace(sc, R([2, 0]), [6, 0], { rxH: 1 }).rssi, behindWall = trace(sc, R([2, -2]), [6, -2], { rxH: 1 }).rssi;
  assert.ok(behindDoor > behindWall + 12, `${behindDoor} vs ${behindWall}`);
});

test("벽 높이보다 위로 지나가는 길은 막지 않는다 (낮은 가벽)", () => {
  const sc = prepare({ walls: [wall("low", [4, -3], [4, 3], "drywall", 0.1, 1.2)], openings: [], objects: [] });
  const over = trace(sc, R([2, 0], "5", { h: 2.0 }), [6, 0], { rxH: 1.8, causes: ONLY_DIRECT });
  assert.equal(over.contributions.filter((c) => c.kind === "wall").length, 0);
});

const fridge = { id: "f1", kind: "refrigerator", c: [4, 0], ang: Math.PI / 2, w: 0.9, d: 0.9, y0: 0, y1: 1.8 };
const cab = { id: "c1", kind: "cabinet", c: [4, 0], ang: Math.PI / 2, w: 2.4, d: 0.6, y0: 0, y1: 0.9 };

test("냉장고 뒤쪽에 그림자가 생긴다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [fridge] });
  const behind = trace(sc, R([2, 0]), [6, 0], { rxH: 1, causes: ONLY_DIRECT });
  const side = trace(sc, R([2, 0]), [6, 2], { rxH: 1, causes: ONLY_DIRECT });
  const obj = behind.contributions.find((c) => c.kind === "object");
  assert.ok(obj && obj.refId === "f1");
  near(obj.db, -20, 0.5, "5 GHz 냉장고");
  assert.ok(!side.contributions.some((c) => c.kind === "object"), "옆으로 비켜 가면 안 가린다");
  assert.deepEqual(objectRf("refrigerator").loss.slice(0, 2), [15, 20]);
  assert.equal(objectRf("water_purifier"), null, "정의 안 된 물건은 0");
});

test("공유기가 바닥에 있으면 하부장이 가리고, 1.8 m로 올리면 그림자가 사라진다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [cab] });
  const objDb = (h) => -trace(sc, R([2, 0], "5", { h }), [6, 0], { rxH: 1, causes: ONLY_DIRECT }).contributions.filter((c) => c.kind === "object").reduce((s, c) => s + c.db, 0);
  assert.ok(objDb(0.2) > 4, `바닥: ${objDb(0.2)}`);
  assert.ok(objDb(1.8) < 1, `1.8 m: ${objDb(1.8)}`);
});

test("안테나는 도넛 모양: 바로 아래는 같은 거리 옆보다 약하다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [] });
  const below = trace(sc, R([0, 0], "5", { h: 2.2 }), [0, 0], { rxH: 0.2, causes: ONLY_DIRECT });
  const side = trace(sc, R([0, 0], "5", { h: 1.0 }), [2, 0], { rxH: 1.0, causes: ONLY_DIRECT });
  assert.ok(below.rssi < side.rssi - 10, `${below.rssi} vs ${side.rssi}`);
  const ant = below.contributions.find((c) => c.kind === "antenna");
  near(ant.db, -20, 0.01, "최소 -20 dB");
});

test("금속 함 안에 넣으면 15 dB, 장식장 안이면 5 dB 약하다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [] });
  const base = trace(sc, R([0, 0]), [3, 0], { rxH: 1 }).rssi;
  near(base - trace(sc, R([0, 0], "5", { enclosure: "metal" }), [3, 0], { rxH: 1 }).rssi, 15, 0.01);
  near(base - trace(sc, R([0, 0], "5", { enclosure: "cabinet" }), [3, 0], { rxH: 1 }).rssi, 5, 0.01);
});

test("원인별 값을 더하면 받는 세기가 된다 (탐침 막대가 맞는다)", () => {
  const sc = prepare({ walls: [wall("a", [0, -1], [8, -1]), wall("p", [4, -1], [4, 3])], openings: [{ id: "d", wall: "p", kind: "door", u0: 2, u1: 3, z0: 0, z1: 2.1 }], objects: [fridge] });
  for (const p of [[6, 0], [6, 2.5], [1, 2]]) {
    const t = trace(sc, R([2, 0.5], "5", { tx: 20 }), p, { rxH: 1 });
    near(20 + t.contributions.reduce((s, c) => s + c.db, 0), t.rssi, 0.01, `${p}`);
    for (const c of t.contributions) assert.ok(CAUSE_KINDS.includes(c.kind), c.kind);
  }
});

test("반사: 콘크리트 벽 가까이에서는 반사가 신호를 보탠다", () => {
  const sc = prepare({ walls: [wall("a", [-5, 1], [10, 1])], openings: [], objects: [] });
  const withR = trace(sc, R([0, 0]), [4, 0], { rxH: 1 }), noR = trace(sc, R([0, 0]), [4, 0], { rxH: 1, causes: { reflection: false } });
  assert.ok(withR.rssi > noR.rssi + 0.5, `${withR.rssi} vs ${noR.rssi}`);
  const g = withR.contributions.find((c) => c.kind === "reflection");
  assert.ok(g && g.db > 0);
  assert.ok(withR.paths.some((p) => p.kind === "reflection" && p.pts.length === 3), "반사 경로를 그릴 점");
});

// 문 모서리(x=4 벽, z=0.5에서 문이 끝난다) 뒤 그림자를 가로지르는 선: 문 정면(z=0)에서 벽 뒤(z=2.5)로
const doorScene = () => prepare({ walls: [wall("p", [4, -4], [4, 4], "concrete", 0.15)], openings: [{ id: "d", wall: "p", kind: "door", u0: 3.0, u1: 4.5, z0: 0, z1: 2.1 }], objects: [] });
const profile = (band, causes = {}) => {
  const sc = doorScene(), free = prepare({ walls: [], openings: [], objects: [] }), out = [];
  for (let z = 0; z <= 2.5001; z += 0.02) {
    const p = [7, z];
    out.push([z, trace(free, R([1, 0], band), p, { rxH: 1, causes: ONLY_DIRECT }).rssi - trace(sc, R([1, 0], band), p, { rxH: 1, causes: { reflection: false, ...causes } }).rssi]);
  }
  return out; // [z, 문이 없을 때보다 잃은 dB]
};

test("회절: 문 모서리 뒤 그림자 경계에 계단이 없다", () => {
  for (const band of ["2.4", "5"]) {
    const pr = profile(band);
    let jump = 0;
    for (let i = 1; i < pr.length; i++) jump = Math.max(jump, Math.abs(pr[i][1] - pr[i - 1][1]));
    assert.ok(jump < 1.5, `${band} GHz 2 cm마다 최대 ${jump.toFixed(2)} dB`);
  }
});

test("회절: 2.4 GHz는 5 GHz보다 그림자 경계가 넓고 부드럽다", () => {
  const width = (pr) => { const a = pr.find(([, l]) => l > 3)?.[0], b = pr.find(([, l]) => l > 12)?.[0]; return b - a; };
  const w24 = width(profile("2.4")), w5 = width(profile("5"));
  assert.ok(w24 > w5 * 1.3, `2.4: ${w24.toFixed(2)} m, 5: ${w5.toFixed(2)} m`);
  // 그림자 안 같은 자리에서 2.4 GHz가 덜 잃는다
  const at = (pr, z) => pr.reduce((b, x) => (Math.abs(x[0] - z) < Math.abs(b[0] - z) ? x : b))[1];
  assert.ok(at(profile("2.4"), 1.6) < at(profile("5"), 1.6));
  // 회절을 끄면 그림자가 다시 날카로워진다
  const sharp = profile("5", { diffraction: false });
  let jump = 0;
  for (let i = 1; i < sharp.length; i++) jump = Math.max(jump, Math.abs(sharp[i][1] - sharp[i - 1][1]));
  assert.ok(jump > 10, `회절 끔: ${jump}`);
});

test("전자레인지를 켜면 2.4 GHz SNR·속도만 떨어지고 세기는 그대로", () => {
  const sc = prepare({ walls: [], openings: [], objects: [{ id: "mw", kind: "microwave", c: [15, 1], ang: 0, w: 0.5, d: 0.4, y0: 0.9, y1: 1.2 }] });
  for (const band of ["2.4", "5"]) {
    const off = trace(sc, R([0, 0], band), [15, 0], { rxH: 1, interference: { microwaveOn: false } });
    const on = trace(sc, R([0, 0], band), [15, 0], { rxH: 1, interference: { microwaveOn: true } });
    near(on.rssi, off.rssi, 1e-9, "세기");
    if (band === "2.4") { assert.ok(on.snr < off.snr - 10, `SNR ${on.snr} vs ${off.snr}`); assert.ok(on.mbps < off.mbps); }
    else { near(on.snr, off.snr, 1e-9); assert.equal(on.mbps, off.mbps); }
  }
});

test("노이즈 바닥: 20 MHz ≈ -94 dBm, 80 MHz ≈ -88 dBm, 혼잡하면 오른다", () => {
  const sc = prepare({ walls: [], openings: [], objects: [] });
  near(trace(sc, R([0, 0], "5", { width: 20 }), [3, 0], { rxH: 1 }).noise, -94, 0.1);
  near(trace(sc, R([0, 0], "5", { width: 80 }), [3, 0], { rxH: 1 }).noise, -88, 0.1);
  const busy = trace(sc, R([0, 0], "2.4", { width: 20 }), [3, 0], { rxH: 1, interference: { congestion: 10 } });
  near(busy.noise, -84, 0.1);
  assert.ok(trace(sc, R([0, 0], "5"), [2, 0], { rxH: 1 }).mbps > trace(sc, R([0, 0], "5"), [30, 0], { rxH: 1 }).mbps);
});

test("격자: 계단 없이 이어지고, 원인 ID와 SNR도 같이 나온다", () => {
  const sc = prepare({ walls: [wall("o1", [0, 0], [10, 0], "reinforced_concrete", 0.2), wall("o2", [10, 0], [10, 8], "reinforced_concrete", 0.2), wall("o3", [10, 8], [0, 8], "reinforced_concrete", 0.2), wall("o4", [0, 8], [0, 0], "reinforced_concrete", 0.2), wall("p", [5, 0], [5, 8], "concrete", 0.15)],
    openings: [{ id: "d", wall: "p", kind: "door", u0: 3.5, u1: 4.4, z0: 0, z1: 2.1 }], objects: [{ ...fridge, c: [3, 6] }] });
  const f = field(sc, R([2, 4]), { rxH: 1, cell: 0.1, bounds: [0, 0, 10, 8] });
  assert.equal(f.nx, 100); assert.equal(f.ny, 80);
  assert.ok(f.rssi instanceof Float32Array && f.snr instanceof Float32Array && f.cause instanceof Uint16Array);
  assert.equal(f.rssi.length, 8000);
  // 문 안쪽 줄(z=4)을 따라 옆 칸과 차이가 크게 튀지 않는다
  const j = 40;
  let jump = 0;
  for (let i = 1; i < 100; i++) jump = Math.max(jump, Math.abs(f.rssi[j * 100 + i] - f.rssi[j * 100 + i - 1]));
  assert.ok(jump < 6, `한 칸 최대 ${jump}`);
  // 칸막이 너머 문에서 먼 곳은 원인이 벽
  const c = f.cause[10 * 100 + 80];
  assert.equal(CAUSE_KINDS[c >> 12], "wall");
});

test("성능: 10×8 m를 0.3 m는 16 ms, 0.1 m는 150 ms 안에", () => {
  const walls = [wall("o1", [0, 0], [10, 0], "reinforced_concrete", 0.2), wall("o2", [10, 0], [10, 8], "reinforced_concrete", 0.2), wall("o3", [10, 8], [0, 8], "reinforced_concrete", 0.2), wall("o4", [0, 8], [0, 0], "reinforced_concrete", 0.2)];
  for (let k = 0; k < 8; k++) walls.push(wall(`i${k}`, [1 + k, 2 + (k % 3)], [1.6 + k, 5], "drywall", 0.1));
  const openings = [{ id: "d1", wall: "i1", kind: "door", u0: 0.5, u1: 1.4, z0: 0, z1: 2.1 }, { id: "w1", wall: "o1", kind: "window", u0: 3, u1: 5, z0: 0.9, z1: 2.1 }];
  const objects = Array.from({ length: 20 }, (_, i) => ({ id: `o${i}`, kind: i % 2 ? "sofa" : "refrigerator", c: [0.5 + (i % 10), 1 + Math.floor(i / 10) * 5], ang: 0, w: 0.8, d: 0.6, y0: 0, y1: 1 }));
  const sc = prepare({ walls, openings, objects });
  for (let i = 0; i < 4; i++) { field(sc, R([4, 4]), { rxH: 1, cell: 0.3, preview: true, bounds: [0, 0, 10, 8] }); field(sc, R([4, 4]), { rxH: 1, cell: 0.1, bounds: [0, 0, 10, 8] }); } // 데우기 (끌기 시작하면 이미 데워져 있다)
  // 끄는 동안은 미리보기(0.3 m, 약한 길은 과감히 건너뜀), 멈추면 0.1 m
  const time = (cell, preview) => { // 다섯 번 재서 가운데 값 (가끔 끼는 GC는 뺀다)
    const ts = [];
    for (let i = 0; i < 5; i++) { const t0 = performance.now(); field(sc, R([4 + i * 0.1, 4]), { rxH: 1, cell, preview, bounds: [0, 0, 10, 8] }); ts.push(performance.now() - t0); }
    return ts.sort((a, b) => a - b)[2];
  };
  const fast = time(0.3, true), fine = time(0.1, false);
  assert.ok(fast < 16, `0.3 m: ${fast.toFixed(1)} ms`);
  assert.ok(fine < 150, `0.1 m: ${fine.toFixed(1)} ms`);
});

test("좋은 공유기 자리 3곳: -67 dBm 이상 면적이 넓은 순서", () => {
  const sc = prepare({ walls: [wall("o1", [0, 0], [10, 0]), wall("o2", [10, 0], [10, 6]), wall("o3", [10, 6], [0, 6]), wall("o4", [0, 6], [0, 0]), wall("p", [5, 0], [5, 6], "reinforced_concrete", 0.2)], openings: [], objects: [] });
  const spots = bestSpots(sc, R([1, 1]), { rxH: 1, bounds: [0, 0, 10, 6], inside: () => true });
  assert.equal(spots.length, 3);
  assert.ok(spots[0].share >= spots[1].share && spots[1].share >= spots[2].share);
  assert.ok(spots[0].share > 0 && spots[0].share <= 1);
  for (let i = 0; i < 3; i++) for (let k = i + 1; k < 3; k++) assert.ok(Math.hypot(spots[i].xz[0] - spots[k].xz[0], spots[i].xz[1] - spots[k].xz[1]) >= 1, "서로 떨어진 자리");
});

test("색: 끊김 없이 이어지고, 제1·제2색약으로 봐도 강약 순서가 구분된다", () => {
  const lab = (rgb) => { // sRGB 0..1 → CIELAB
    const lin = rgb.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    const X = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047, Y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2], Z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883;
    const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
  };
  const dE = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  for (const kind of [null, "protan", "deutan"]) {
    const s = [];
    for (let v = -30; v >= -90; v -= 1) s.push(lab(kind ? simulateCvd(colorAt(v), kind) : colorAt(v)));
    for (let i = 1; i < s.length; i++) assert.ok(dE(s[i], s[i - 1]) < 6, `${kind} 1 dB마다 부드럽게`);
    for (let i = 0; i < s.length; i++) for (let k = i + 10; k < s.length; k++) assert.ok(dE(s[i], s[k]) > 12, `${kind}: ${-30 - i} vs ${-30 - k} dBm 구분`);
  }
  assert.equal(contourKind(-67), "bold"); assert.equal(contourKind(-50), "bold"); assert.equal(contourKind(-75), "bold");
  assert.equal(contourKind(-55), "thin"); assert.equal(contourKind(-57), null);
});

test("집 → 계산 입력: 바깥벽은 철근콘크리트, 안쪽은 콘크리트, 고른 재질이 이기고, 단 문은 벽 구멍이 된다", async () => {
  const { wifiScene } = await import("../../apps/web/js/wifi/scene.js");
  const W = (id, s, e) => ({ wall_id: id, start: s, end: e, thickness_m: 0.1, scanned: { length_m: 1, height_m: 2.4 } });
  const room = { walls: [W("w1", [0, 0], [8, 0]), W("w2", [8, 0], [8, 5]), W("w3", [8, 5], [0, 5]), W("w4", [0, 5], [0, 0]), W("w5", [4, 0], [4, 5])],
    openings: [{ opening_id: "o1", type: "window", wall_id: "w1", offset_m: 1, width_m: 1.5, height_m: 1.2, sill_m: 0.9 }, { opening_id: "o2", type: "opening", wall_id: "w5", offset_m: 1, width_m: 1, height_m: 2.1, sill_m: 0 }],
    objects: [{ object_id: "s1", category: "sofa", bbox_m: { w: 2, h: 0.8, d: 0.9 }, position: [2, 0.4, 4], yaw_rad: 0 }, { object_id: "s2", category: "table", bbox_m: { w: 1, h: 0.7, d: 1 }, position: [6, 0.35, 4], yaw_rad: 0 }] };
  const ss = { wall_materials: { w2: "brick" }, hidden_objects: ["s2"],
    placements: [{ placement_id: "p1", sku: "R1", center_xz: [6, 1], yaw_rad: Math.PI / 2, size_m: [0.9, 1.8, 0.9] }, { placement_id: "p2", sku: "decor:door", center_xz: [4, 3.5], yaw_rad: 0, size_m: [0.9, 2.1, 0.14] }],
    router: { center_xz: [2, 2], band: "5", height_m: 0.75 } };
  const sc = wifiScene(room, ss, (sku) => (sku === "R1" ? "refrigerator" : null));
  const mat = Object.fromEntries(sc.walls.map((w) => [w.id, w.material]));
  assert.deepEqual(mat, { w1: "reinforced_concrete", w2: "brick", w3: "reinforced_concrete", w4: "reinforced_concrete", w5: "concrete" });
  assert.equal(sc.input.openings.find((o) => o.id === "o2").kind, "open");
  const door = sc.input.openings.find((o) => o.id === "p2");
  assert.ok(door && door.wall === "w5" && Math.abs(door.u0 - 3.05) < 1e-6 && door.kind === "door", JSON.stringify(door));
  assert.deepEqual(sc.input.objects.map((o) => o.kind).sort(), ["refrigerator", "sofa"]);
  near(sc.router.h, 0.9, 1e-9, "올려 둔 가구 위 + 안테나");
  assert.ok(sc.inside([2, 2]) && !sc.inside([9, 2]));
});
