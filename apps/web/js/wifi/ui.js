// 와이파이 패널 글·범례·탐침 막대 (DOM 문자열만 만든다, 테스트 가능)
import { ANCHORS, DBM_TOP, DBM_BOTTOM, MATERIALS } from "./materials.js";
import { cssGradient, colorAt, diffColorAt } from "./palette.js";
import { CAUSE_KINDS } from "./propagation.js";

export const CAUSES = [["distance", "거리"], ["wall", "벽"], ["object", "가구·가전"], ["reflection", "반사"], ["diffraction", "회절"], ["interference", "간섭"]];
export const MODES = [["dbm", "세기"], ["mbps", "속도"], ["diff", "5·2.4 차이"]];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const signed = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v))}`;

/** 받는 세기 한 줄 평가 */
export function feel(dbm) {
  return dbm >= -50 ? "8K·게임도 넉넉해요" : dbm >= -60 ? "4K 영상이 잘 나와요" : dbm >= -67 ? "화상통화가 잘 돼요"
    : dbm >= -75 ? "웹서핑은 되지만 화상통화는 불안정해요" : dbm >= -85 ? "자주 끊길 수 있어요" : "거의 안 잡혀요";
}

// 속도 지도는 10·log10(Mbps)로 펴서 그린다 (10 Mbps ~ 1.2 Gbps)
export const mbpsValue = (m) => 10 * Math.log10(Math.max(1, m));
export const RANGES = {
  dbm: { top: DBM_TOP, bottom: DBM_BOTTOM, step: 5, bold: [-50, -67, -75] },
  mbps: { top: mbpsValue(1200), bottom: mbpsValue(10), step: mbpsValue(2) - mbpsValue(1), bold: [mbpsValue(25), mbpsValue(100), mbpsValue(300)] },
  diff: { top: 12, bottom: -12, step: 3, bold: [0] },
};
export const labelText = (mode, v) => (mode === "dbm" ? `${Math.round(v)}` : mode === "mbps" ? `${Math.round(10 ** (v / 10))} Mbps` : "같음");

/** 범례: 끊김 없는 색띠 + 눈금 + 체감 기준 */
export function legendHtml(mode = "dbm") {
  if (mode === "diff") {
    return `<div class="wl"><div class="wl-bar" style="background:${cssGradient(diffColorAt, 12, -12)}"></div>
      <div class="wl-ticks"><span class="edge-l" style="left:0">5 GHz가 더 강해요</span><span style="left:50%">비슷해요</span><span class="edge-r" style="left:100%">2.4 GHz가 더 강해요</span></div></div>`;
  }
  if (mode === "mbps") {
    const r = RANGES.mbps, pos = (m) => (((mbpsValue(m) - r.top) / (r.bottom - r.top)) * 100).toFixed(1);
    return `<div class="wl"><div class="wl-bar" style="background:${cssGradient(colorAt, DBM_TOP, DBM_BOTTOM)}"></div>
      <div class="wl-ticks">${[[1000, "1 Gbps"], [300, "300"], [100, "100"], [25, "25 Mbps"]].map(([m, t], i) => `<span${i ? "" : ' class="edge-l"'} style="left:${pos(m)}%">${t}</span>`).join("")}</div></div>`;
  }
  const pos = (v) => (((v - DBM_TOP) / (DBM_BOTTOM - DBM_TOP)) * 100).toFixed(1);
  return `<div class="wl"><div class="wl-bar" style="background:${cssGradient()}"></div>
    <div class="wl-ticks">${ANCHORS.map(([v, t]) => `<span style="left:${pos(v)}%"><b>${v}</b>${esc(t)}</span>`).join("")}</div></div>`;
}

/** 원인 번호(종류 << 12 | 번호) → 사람 말. sc: prepare 결과, info: wifiScene().walls */
export function causeName(code, sc, info = []) {
  const kind = CAUSE_KINDS[code >> 12], i = code & 0xfff;
  if (kind === "wall") {
    const w = sc.walls[i], meta = info.find((x) => x.id === w?.id);
    return w ? `${meta?.outer ? "바깥 " : ""}${w.ko}${meta?.guessed ? "(추정)" : ""}` : "벽";
  }
  if (kind === "object") return sc.objects[i]?.ko || "가구";
  return { distance: "공유기와 먼 거리", antenna: "공유기 바로 아래·위", enclosure: "공유기를 넣어 둔 함", interference: "전자레인지 잡음" }[kind] || "거리";
}

/** 집 안 칸 통계: 화상통화(-67) 이상 비율과 약한 곳의 주된 원인 */
export function summarize(f, sc, info, inside) {
  let n = 0, good = 0;
  const why = new Map();
  for (let j = 0; j < f.ny; j++) for (let i = 0; i < f.nx; i++) {
    if (!inside([f.origin[0] + (i + 0.5) * f.cell, f.origin[1] + (j + 0.5) * f.cell])) continue;
    const k = j * f.nx + i;
    n++;
    if (f.rssi[k] >= -67) good++;
    else why.set(f.cause[k], (why.get(f.cause[k]) || 0) + 1);
  }
  const top = [...why].sort((a, b) => b[1] - a[1])[0];
  return { share: n ? good / n : 0, weakShare: n ? (n - good) / n : 0, cause: top ? causeName(top[0], sc, info) : null, causeCode: top?.[0] ?? null };
}
export function summaryHtml(s, hover = true) {
  const pct = Math.round(s.share * 100);
  const head = pct >= 98 ? "집 어디서나 화상통화가 잘 돼요" : `집의 ${pct}%에서 화상통화가 잘 돼요`;
  const tail = pct < 98 && s.cause ? ` · 약한 곳은 주로 <b>${esc(s.cause)}</b> 때문이에요` : "";
  return `<p class="sim-line wifi-sum">${head}${tail}${hover ? `<span class="muted">바닥에 마우스를 올리면 그 자리가 왜 그런지 보여요</span>` : ""}</p>`;
}

/** 탐침 막대 (폭포형): 출력 → 원인마다 더하고 빼서 → 받는 세기 */
export function probeHtml(t, { tx = 20, band = "5", width = 80 } = {}) {
  const rows = [["공유기 출력", tx, "tx"]];
  const dist = t.contributions.find((c) => c.kind === "distance");
  const d = Math.hypot(t.paths[0].pts[1][0] - t.paths[0].pts[0][0], t.paths[0].pts[1][2] - t.paths[0].pts[0][2]);
  if (dist) rows.push([`거리 ${d.toFixed(1)} m`, dist.db, "loss"]);
  const merged = new Map(); // 같은 이름은 합친다 (예: 의자 여러 개)
  for (const c of t.contributions) {
    if (c.kind === "distance") continue;
    const name = c.kind === "reflection" ? "반사로 보탬" : c.kind === "diffraction" ? (c.gain ? "문틈으로 돌아 들어옴" : c.name || "문틀 가까이")
      : c.kind === "antenna" ? "공유기 바로 아래·위" : c.kind === "enclosure" ? "함 안에 넣어 둠" : c.name;
    merged.set(name, (merged.get(name) || 0) + c.db);
  }
  for (const [name, db] of merged) if (Math.abs(db) >= 0.5) rows.push([name, db, db > 0 ? "gain" : "loss"]);
  const max = Math.max(30, ...rows.map((r) => Math.abs(r[1])));
  const row = ([name, db, k]) => `<li class="${k}"><span class="n">${esc(name)}</span><span class="bar"><i style="width:${((Math.abs(db) / max) * 100).toFixed(0)}%"></i></span><b>${signed(db)}</b></li>`;
  const noise = (t.interference || []).map((x) => `${esc(x.name)} 잡음 +${Math.round(x.db)} dB`).join(" · ");
  return `<p class="wt-head"><b>${Math.round(t.rssi)} dBm</b> ${esc(feel(t.rssi))}</p>
    <ol class="wt-fall">${rows.map(row).join("")}</ol>
    <p class="wt-foot">${band} GHz ${width} MHz 기준 예상 속도 약 <b>${t.mbps}</b> Mbps${noise ? ` · ${noise}` : ""}</p>`;
}

/** 탐침 3D 배지: 지나간 벽·물체 */
export function probeBadges(t) {
  return t.contributions.filter((c) => (c.kind === "wall" || c.kind === "object") && Math.abs(c.db) >= 1 && c.at)
    .map((c) => ({ at: c.at, text: `${c.name} ${signed(c.db)}dB` }));
}

export const materialChoices = (list) => list.map((k) => [k, MATERIALS[k].ko]);
