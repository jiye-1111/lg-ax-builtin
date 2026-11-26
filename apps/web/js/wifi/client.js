// 화면 쪽에서 Worker를 부르는 곳. 끄는 동안 쌓인 요청은 마지막 것만 계산한다
import { prepare, field, bestSpots, trace } from "./propagation.js";
import { wifiScene } from "./scene.js";

export function wifiClient() {
  let worker = null, seq = 0, busy = false, queued = null, local = null;
  const waits = new Map();
  try {
    worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
    worker.onmessage = ({ data }) => {
      const w = waits.get(data.id);
      waits.delete(data.id);
      if (data.type === "field") { busy = false; pump(); }
      w?.(data);
    };
    worker.onerror = () => { worker = null; busy = false; for (const [, w] of waits) w(null); waits.clear(); };
  } catch { worker = null; }
  let probeSc = null, sceneMsg = null;
  const pump = () => {
    if (busy || !queued) return;
    const q = queued; queued = null;
    if (!worker) { // Worker를 못 쓰는 브라우저: 같은 식을 화면에서 (조금 느리다)
      local ??= prepare(sceneMsg.built || wifiScene(sceneMsg.room, sceneMsg.ss, (s) => sceneMsg.cats[s] || null).input);
      const f = field(local, q.msg.router, q.msg.opts);
      q.done({ ...f, alt: q.msg.alt ? field(local, { ...q.msg.router, band: q.msg.alt }, q.msg.opts).rssi : null });
      return;
    }
    busy = true;
    waits.set(q.msg.id, q.done);
    worker.postMessage(q.msg);
  };
  return {
    /** 집이 바뀌면 (배치·벽·재질) 다시 보낸다 */
    setScene(room, ss, cats) {
      sceneMsg = { type: "scene", room, ss, cats };
      local = null;
      const s = wifiScene(room, ss, (sku) => cats[sku] || null);
      probeSc = prepare(s.input);
      worker?.postMessage(sceneMsg);
      return s;
    },
    /** 격자 계산. 앞선 요청이 아직 줄에 있으면 그것은 버린다 (마지막 자리만 의미 있다) */
    field(router, opts, alt = null) {
      return new Promise((done) => {
        if (queued) queued.done(null);
        queued = { msg: { type: "field", id: ++seq, router, opts, alt }, done };
        pump();
      });
    },
    best(router, opts) {
      if (!worker) return Promise.resolve(bestSpots(probeSc, router, opts));
      const { inside, ...plain } = opts; // 함수는 Worker로 못 보낸다 (Worker는 같은 집 테두리를 따로 갖고 있다)
      return new Promise((done) => { const id = ++seq; waits.set(id, (d) => done(d?.spots || [])); worker.postMessage({ type: "best", id, router, opts: plain }); });
    },
    /** 커서 탐침: 한 점은 빨라서 화면에서 바로 */
    probe(router, xz, opts) { return probeSc ? trace(probeSc, router, xz, opts) : null; },
    get sc() { return probeSc; },
    dispose() { worker?.terminate(); worker = null; },
  };
}
