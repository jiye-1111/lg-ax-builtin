// 와이파이 격자 계산 Worker. 화면은 그대로 돌고, 계산이 끝나면 결과 버퍼만 넘긴다
import { prepare, field, bestSpots } from "./propagation.js";
import { wifiScene } from "./scene.js";

let sc = null, inside = () => true;
self.onmessage = ({ data: m }) => {
  if (m.type === "scene") { // room + scene_state를 받아 여기서 준비한다 (화면 쪽은 한 번 보내기만)
    const s = m.built ? null : wifiScene(m.room, m.ss, (sku) => m.cats[sku] || null);
    sc = prepare(m.built || s.input);
    if (s) inside = s.inside;
    return;
  }
  if (!sc) return;
  if (m.type === "field") {
    const t0 = performance.now();
    const f = field(sc, m.router, m.opts);
    const alt = m.alt ? field(sc, { ...m.router, band: m.alt }, m.opts).rssi : null;
    const bufs = [f.rssi.buffer, f.snr.buffer, f.mbps.buffer, f.cause.buffer, ...(alt ? [alt.buffer] : [])];
    self.postMessage({ type: "field", id: m.id, ...f, alt, ms: performance.now() - t0 }, bufs);
  } else if (m.type === "best") {
    self.postMessage({ type: "best", id: m.id, spots: bestSpots(sc, m.router, { ...m.opts, inside }) });
  }
};
