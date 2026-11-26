// 와이파이 히트맵 색: 강한 곳 진한 청록 → 노랑 → LG 와인(#A50034). 빨강-초록 조합은 쓰지 않는다.
import { DBM_TOP, DBM_BOTTOM } from "./materials.js";

// 강한 쪽부터 차례로 (간격은 아래에서 고르게 편다)
export const STOPS = ["#083f4d", "#0f7576", "#3fae98", "#bfe0a0", "#f6d86a", "#ef9d4f", "#d24f45", "#a50034"];
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const RGB = STOPS.map((h, i) => [i, hex(h)]);

// 색 사이를 눈에 보이는 차이(CIELAB ΔE)가 고르게 나눠지도록 길이로 다시 편다 → 1 dB마다 같은 만큼 변한다
const mix = (c0, c1, t) => c0.map((a, k) => toSrgb(toLin(a) * (1 - t) + toLin(c1[k]) * t));
const rawAt = (s) => { // s: 0..1 (첫 색 → 끝 색)
  const x = Math.min(RGB.length - 1 - 1e-9, Math.max(0, s * (RGB.length - 1))), i = Math.floor(x);
  return mix(RGB[i][1], RGB[i + 1][1], x - i);
};
const LUT_N = 600, LUT = [];
{
  let acc = 0, prev = null;
  const arc = [];
  for (let k = 0; k <= LUT_N; k++) { const c = rawAt(k / LUT_N), L = lab(c); if (prev) acc += Math.hypot(L[0] - prev[0], L[1] - prev[1], L[2] - prev[2]); arc.push(acc); prev = L; }
  for (let k = 0; k <= LUT_N; k++) { // 고른 길이 k/LUT_N에 해당하는 원래 위치
    const want = (acc * k) / LUT_N;
    let j = 1;
    while (j < LUT_N && arc[j] < want) j++;
    const t = (want - arc[j - 1]) / (arc[j] - arc[j - 1] || 1);
    LUT.push(rawAt((j - 1 + t) / LUT_N));
  }
}

/** dBm → sRGB [0..1]. 범위 밖은 끝 색 */
export function colorAt(v) {
  const s = Math.min(1, Math.max(0, (DBM_TOP - v) / (DBM_TOP - DBM_BOTTOM))) * LUT_N, i = Math.min(LUT_N - 1, Math.floor(s));
  return mix(LUT[i], LUT[i + 1], s - i);
}

// 5 GHz − 2.4 GHz 차이 지도: 파랑(5 GHz가 낫다) ↔ 흰색 ↔ 주황(2.4 GHz가 낫다)
const DIV = [[12, "#2b5d9c"], [4, "#8fb3d9"], [0, "#f4f1ea"], [-4, "#f2b27a"], [-12, "#b5541c"]].map(([v, h]) => [v, hex(h)]);
export function diffColorAt(d) {
  if (d >= DIV[0][0]) return DIV[0][1].slice();
  if (d <= DIV[DIV.length - 1][0]) return DIV[DIV.length - 1][1].slice();
  for (let i = 1; i < DIV.length; i++) {
    if (d >= DIV[i][0]) { const t = (DIV[i - 1][0] - d) / (DIV[i - 1][0] - DIV[i][0]); return DIV[i - 1][1].map((a, k) => toSrgb(toLin(a) * (1 - t) + toLin(DIV[i][1][k]) * t)); }
  }
  return DIV[DIV.length - 1][1].slice();
}

/** 가로 256칸 색띠 (셰이더 텍스처·범례용). RGBA 8bit */
export function rampBytes(fn = colorAt, from = DBM_TOP, to = DBM_BOTTOM, n = 256) {
  const out = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    const c = fn(from + ((to - from) * i) / (n - 1));
    out.set([Math.round(c[0] * 255), Math.round(c[1] * 255), Math.round(c[2] * 255), 255], i * 4);
  }
  return out;
}
export const cssGradient = (fn = colorAt, from = DBM_TOP, to = DBM_BOTTOM) =>
  `linear-gradient(90deg, ${Array.from({ length: 9 }, (_, i) => { const c = fn(from + ((to - from) * i) / 8); return `rgb(${c.map((x) => Math.round(x * 255)).join(",")}) ${(i * 12.5).toFixed(1)}%`; }).join(", ")})`;

// 등고선: 5 dB마다 얇게, 체감 기준 세 곳은 굵게
export const BOLD = [-50, -67, -75];
export const contourKind = (v) => (BOLD.includes(v) ? "bold" : Number.isInteger(v) && v % 5 === 0 ? "thin" : null);

function lab(rgb) {
  const l = rgb.map(toLin);
  const X = (0.4124 * l[0] + 0.3576 * l[1] + 0.1805 * l[2]) / 0.95047, Y = 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2], Z = (0.0193 * l[0] + 0.1192 * l[1] + 0.9505 * l[2]) / 1.08883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
function toLin(c) { return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }
function toSrgb(c) { c = Math.min(1, Math.max(0, c)); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055; }
// 색약 시뮬레이션 (Machado 2009, 심도 1.0)
const CVD = {
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
};
export function simulateCvd(rgb, kind) {
  const m = CVD[kind], l = rgb.map(toLin);
  return m.map((r) => toSrgb(r[0] * l[0] + r[1] * l[1] + r[2] * l[2]));
}
