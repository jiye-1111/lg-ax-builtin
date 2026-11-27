// 벽면 맞춤가구 편집기: 벽을 고르고 정면도에서 장을 늘어놓는다 (docs/specs/wall-run.md).
// 고칠 때마다 서버 미리보기(/runs/preview)를 받아 3D에 그대로 보여 준다. 저장은 '배치 확정'만, '취소'는 원래 장면으로 돌아간다.
// 자리·사용 폭·문제·판정은 서버가 계산한다. 여기서는 그리고, 고친 값을 모아 보낸다.
import { esc } from "./core.js";

const TIERS = ["base", "wall"];
const TIER_KO = { base: "하부·키큰장", wall: "상부장" };
const LEVEL_MARK = { no: "✕", check: "!", info: "i" };
const VERDICT_KO = { fit: "적합", conditional: "조건부", no_fit: "불가", unknown: "확인 필요" };
const STATUS_KO = { ok: "맞음", check: "확인 필요", site: "현장 확인", blocked: "불가", none: "공식 자료 없음" };
const STYLE_KO = { door: "여닫이", drawer: "서랍", open: "오픈", pullout: "인출", flap: "플랩", homecafe: "홈카페 칸" };
const ROOM_KO = { kitchen: "주방", living: "거실" };
const n0 = (v) => Math.round(v).toLocaleString("ko-KR");
let uidSeq = 0;
const uid = () => `m${++uidSeq}`;

/** 정면도 왼쪽 끝 기준 s(mm) ↔ 세계 좌표. 서버 runs.wall_axes와 같은 규칙 */
export function wallAxes(w, center) {
  const dx = w.end[0] - w.start[0], dz = w.end[1] - w.start[1], L = Math.hypot(dx, dz) || 1e-9;
  const u = [dx / L, dz / L];
  let v = [-u[1], u[0]];
  const mid = [w.start[0] + dx / 2, w.start[1] + dz / 2];
  if (v[0] * (center[0] - mid[0]) + v[1] * (center[1] - mid[1]) < 0) v = [-v[0], -v[1]];
  const r = [v[1], -v[0]];
  const flip = u[0] * r[0] + u[1] * r[1] < 0;
  const origin = flip ? w.end : w.start;
  return { origin, r, v, L, flip, sOf: (p) => ((p[0] - origin[0]) * r[0] + (p[1] - origin[1]) * r[1]) * 1000,
    dist: (p) => Math.abs((p[0] - origin[0]) * v[0] + (p[1] - origin[1]) * v[1]) };
}
export function roomCenter(room) {
  const m = room.walls.map((w) => [(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2]);
  return [m.reduce((a, p) => a + p[0], 0) / m.length, m.reduce((a, p) => a + p[1], 0) / m.length];
}
/** 그 자리에서 가장 가까운 벽 (놓인 가전을 장으로 감쌀 때) */
export function nearestWall(room, xz) {
  const c = roomCenter(room);
  let best = null;
  for (const w of room.walls) {
    const ax = wallAxes(w, c), s = ax.sOf(xz) / 1000;
    if (s < -0.2 || s > ax.L + 0.2) continue;
    const d = ax.dist(xz);
    if (!best || d < best.d) best = { w, d, ax };
  }
  return best;
}

/** 프리셋 → 정면도 모듈(보낼 값). over: 고친 값 */
export function moduleFrom(preset, over = {}) {
  return { uid: uid(), preset: preset.id, gap_mm: 0, ...over };
}

/** 시작 세트 → 줄 */
export function starterRows(starter, byId) {
  const rows = { base: [], wall: [] };
  for (const t of TIERS) for (const x of starter.rows[t] || []) {
    const id = typeof x === "string" ? x : x.preset;
    if (byId[id]) rows[t].push(moduleFrom(byId[id], { gap_mm: typeof x === "string" ? 0 : x.gap || 0 }));
  }
  return rows;
}

// ---------- 정면도 ----------
function elevationSvg(rep, sel, cabs, palette, H) {
  const L = rep.wall.length_mm, pad = 120;
  const fs = Math.round(Math.max(70, L / 75)); // 글자 크기 (정면도 mm 단위). 긴 벽도 읽히게
  const hexOf = (id) => palette.panel?.find((f) => f.id === id)?.hex || "#eee";
  const bad = new Set(rep.issues.filter((i) => i.level === "no").map((i) => i.id));
  const ops = rep.openings.map((o) => {
    const w = o.s1 - o.s0, h = o.y1 - o.y0;
    if (o.type === "window") return `<g class="el-win"><rect x="${o.s0}" y="${-o.y1}" width="${w}" height="${h}"/><path d="M${o.s0 + w / 2} ${-o.y1}v${h}M${o.s0} ${-o.y0 - h / 2}h${w}"/><text x="${o.s0 + w / 2}" y="${-o.y1 - 30}">창</text></g>`;
    return `<g class="el-door"><rect x="${o.s0}" y="${-o.y1}" width="${w}" height="${h}"/><path d="M${o.s0} 0 A ${w} ${w} 0 0 1 ${o.s0 + w} ${-w}"/><text x="${o.s0 + w / 2}" y="${-o.y1 - 30}">${o.type === "door" ? "문" : "통로"}</text></g>`;
  }).join("");
  const mods = rep.modules.map((m) => {
    const c = cabs[m.id];
    if (!c) return "";
    const w = m.s1 - m.s0, h = c.outer_mm.h, y = -(m.y0 + h);
    const isGlass = !!c.glass;
    const open = c.parts?.style === "open";
    const txt = w > (m.label.replace(/ (\d+)$/, "").length * 0.95 + 0.6) * fs ? `<text x="${m.s0 + w / 2}" y="${y + Math.min(h / 2, 260)}">${esc(m.label.replace(/ (\d+)$/, ""))}</text>` : "";
    const cav = m.kind === "fridge" || m.kind === "dishwasher" ? `<rect class="el-cav" x="${m.s0 + 24}" y="${y + (m.kind === "fridge" ? (c.parts.upper_h || 0) : (c.parts.counter || 0))}" width="${w - 48}" height="${h - (m.kind === "fridge" ? (c.parts.upper_h || 0) : (c.parts.counter || 0))}"/>` : "";
    const tvCav = m.kind === "tvwall" ? `<rect class="el-cav" x="${m.s0 + c.parts.side_w}" y="${y + c.parts.upper_h}" width="${w - 2 * c.parts.side_w}" height="${h - c.parts.upper_h - c.parts.media_h}"/>` : "";
    return `<g class="el-mod${m.id === sel ? " on" : ""}${bad.has(m.id) ? " bad" : ""}" data-mid="${esc(m.id)}" tabindex="0" role="button" aria-label="${esc(m.label)}">
      <rect x="${m.s0}" y="${y}" width="${w}" height="${h}" rx="6" style="fill:${isGlass ? "#dfeaf0" : open ? "#f7f4ee" : hexOf(c.finish?.front)}"/>${cav}${tvCav}${txt}</g>`;
  }).join("");
  const free = TIERS.flatMap((t) => (rep.usage[t].free || []).filter(([a, b]) => b - a >= 100).map(([a, b]) => {
    const y = t === "base" ? -60 : -1500;
    return `<g class="el-free"><path d="M${a + 10} ${y}H${b - 10}"/><text x="${(a + b) / 2}" y="${y - 24}">${n0(b - a)}</text></g>`;
  })).join("");
  return `<svg class="el-svg" id="elSvg" viewBox="${-pad} ${-H - pad} ${L + 2 * pad} ${H + 2 * pad + 2.4 * fs}" preserveAspectRatio="xMidYMid meet" aria-label="벽 정면도" style="font-size:${fs}px">
    <rect class="el-wall" x="0" y="${-H}" width="${L}" height="${H}"/>
    ${ops}${mods}${free}
    <path class="el-floor" d="M${-pad} 0H${L + pad}"/>
    <g class="el-dim"><path d="M0 ${0.6 * fs}v${0.8 * fs}M${L} ${0.6 * fs}v${0.8 * fs}M0 ${fs}H${L}"/><text x="${L / 2}" y="${2.1 * fs}">벽 ${n0(L)} mm</text></g>
  </svg>`;
}

// ---------- 편집기 ----------
/**
 * mount: 편집기를 그릴 곳. ctx: {
 *   pid, room, presets, finishes, kinds, api(path, opt), placed(): 지금 놓인 배치(원래 장면),
 *   preview(scene_state), restore(), confirmed(resp), doors(scene_state) → [{id, label, clear, hits}], candidates(kind) → [{sku,name,rule}],
 *   toast(msg, bad), wallPick(on) }
 * start: {run?: 저장된 세트, wall_id?, room?, rows?, start_mm?, note?}
 */
export function openRunEditor(mount, ctx, start = {}) {
  const P = ctx.presets, byId = Object.fromEntries(P.presets.map((p) => [p.id, p]));
  const center = roomCenter(ctx.room);
  const H = Math.max(2300, ...ctx.room.walls.map((w) => (w.measured?.height_m || w.scanned?.height_m || 2.4) * 1000));
  const st = {
    run_id: start.run?.run_id || null,
    wall_id: start.wall_id || start.run?.wall_id || null,
    room: start.room || start.run?.room || null,
    start_mm: { base: 0, wall: 0, ...(start.run?.start_mm || start.start_mm || {}) },
    rows: start.rows || { base: [], wall: [] },
    sel: null, before: false, rep: null, cabs: {}, busy: false, seq: 0, picking: false, palRoom: start.room === "living" ? "living" : "kitchen",
    note: start.note || "",
  };
  if (start.run) for (const t of TIERS) st.rows[t] = start.run.rows[t].map((r) => ({ uid: uid(), id: r.id, gap_mm: r.gap_mm }));
  const step = () => (!st.wall_id ? "wall" : !st.run_id && !TIERS.some((t) => st.rows[t].length) && !st.chose ? "start" : "edit");
  const all = () => TIERS.flatMap((t) => st.rows[t].map((m, i) => ({ m, t, i })));
  const find = (u) => all().find((q) => q.m.uid === u);
  const modOf = (mid) => all().find((q) => q.m.id === mid || q.m._pid === mid);
  const spec = () => ({
    ...(st.run_id ? { run_id: st.run_id } : {}), wall_id: st.wall_id, ...(st.room ? { room: st.room } : {}), start_mm: st.start_mm,
    rows: Object.fromEntries(TIERS.map((t) => [t, st.rows[t].map(({ uid: _u, _pid, ...m }) => m)])),
  });

  // 미리보기: 고칠 때마다 (0.15초 모아서)
  let timer = null;
  const refresh = () => { clearTimeout(timer); timer = setTimeout(run, 150); };
  const run = async () => {
    if (step() !== "edit") { st.rep = null; ctx.restore(); render(); return; }
    const seq = ++st.seq;
    try {
      const r = await ctx.api(`/api/projects/${ctx.pid}/runs/preview`, { method: "POST", body: JSON.stringify(spec()) });
      if (seq !== st.seq) return;
      st.rep = r;
      // 미리보기 id를 모듈에 붙인다 (줄·순서가 같다)
      const ids = r.modules;
      for (const t of TIERS) st.rows[t].forEach((m, i) => { const q = ids.find((x) => x.tier === t && x.idx === i); if (q) m._pid = q.id; });
      st.cabs = Object.fromEntries(r.scene_state.placements.filter((x) => x.cab).map((x) => [x.placement_id, x.cab]));
      ctx.preview(r.scene_state);
      st.doors = ctx.doors(r.scene_state) || [];
    } catch (e) {
      if (seq !== st.seq) return;
      ctx.toast(e.message || "미리보기를 못 했어요", true);
    }
    render();
    mount.dataset.ver = String(seq); // 미리보기를 받아 다시 그린 횟수 (브라우저 점검이 기다린다)
  };

  // ---------- 바꾸기 ----------
  const change = (fn) => { fn(); refresh(); render(); };
  const add = (pid) => {
    const p = byId[pid];
    if (!p) return;
    const tier = ctx.kinds[p.kind]?.band === "wall" ? "wall" : "base";
    const m = moduleFrom(p);
    const cur = st.sel && find(st.sel);
    if (st.replace && cur) { // 교체: 같은 자리, 새 프리셋 (마감은 이어 받는다)
      const keep = { uid: cur.m.uid, gap_mm: cur.m.gap_mm, ...(cur.m.id ? { id: cur.m.id } : {}) };
      const fin = cur.m.finish || (st.cabs[cur.m._pid]?.finish ? { front: st.cabs[cur.m._pid].finish.front, body: st.cabs[cur.m._pid].finish.body } : null);
      change(() => { st.rows[cur.t][cur.i] = { ...keep, preset: p.id, ...(fin ? { finish: fin } : {}) }; st.replace = false; });
      return;
    }
    change(() => {
      const row = st.rows[tier];
      if (cur && cur.t === tier) row.splice(st.before ? cur.i : cur.i + 1, 0, m);
      else row.push(m);
      st.sel = m.uid;
      st.before = false;
      st.chose = true;
      if (!st.room && p.room) st.room = p.room; // 빈 벽에서 시작하면 처음 고른 장의 공간(주방·거실)으로
    });
  };
  const patch = (u, fn) => change(() => { const q = find(u); if (q) fn(q.m, q); });
  const cfgOf = (m) => st.cabs[m._pid] || null;

  // ---------- 그리기 ----------
  const li = (i) => `<li class="lv-${i.level}" data-goto="${esc(i.id || "")}"><b aria-hidden="true">${LEVEL_MARK[i.level]}</b><span>${esc(i.label)}</span></li>`;
  // 막는 문제는 바로, 마감판·틈막이 같은 안내는 접어 둔다 (한눈에 무엇이 안 되는지만)
  const issueHtml = (list, notes = []) => {
    const hard = list.filter((i) => i.level !== "info"), soft = [...list.filter((i) => i.level === "info"), ...notes.map((n) => ({ level: "info", label: n }))];
    const top = hard.slice(0, 3), more = hard.slice(3);
    if (!hard.length && !soft.length) return `<p class="re-ok">겹치거나 막는 곳이 없어요</p>`;
    return `${top.length ? `<ul class="re-issues">${top.map(li).join("")}</ul>` : ""}
      ${more.length || soft.length ? `<details class="re-more"><summary>${more.length ? `문제 ${more.length}개 더` : ""}${more.length && soft.length ? " · " : ""}${soft.length ? `안내 ${soft.length}개` : ""}</summary><ul class="re-issues">${[...more, ...soft].map(li).join("")}</ul></details>` : ""}`;
  };
  const usageText = (rep) => {
    const u = rep.usage, L = rep.wall.length_mm;
    const one = (t) => `${TIER_KO[t]} ${n0(u[t].used_mm)} mm 사용 · ${n0(u[t].left_mm)} mm 남음`;
    return `벽 ${n0(L)} mm 중 ${one("base")}${u.wall.used_mm ? ` / ${one("wall")}` : ""}`;
  };
  const sourceText = (rep) => {
    const src = [...new Set(rep.modules.map((m) => m.dims_src))].join("·") || "프리셋";
    return `<p class="re-src"><span>벽 길이 <b>${esc(rep.wall.source)}</b></span><span>장 크기 <b>${esc(src)}</b></span>${rep.simulation ? `<span class="re-sim">시뮬레이션 · 만들기 전에 현장 실측이 필요해요</span>` : ""}</p>`;
  };
  const resultHtml = (rep) => {
    const fit = rep.fit.length ? rep.fit.map((f) => `<li class="v-${f.verdict}"><span>${esc(f.label)}<small>${esc(f.summary)}</small></span><b>${VERDICT_KO[f.verdict] || f.verdict_ko}</b></li>`).join("")
      : `<li class="v-none"><span>가전을 넣는 장이 없어요</span></li>`;
    const doors = st.doors?.length ? st.doors.map((d) => `<li class="${d.clear ? "v-fit" : "v-no_fit"}"><span>${esc(d.label)}<small>${d.clear ? "끝까지 열어도 걸리는 것이 없어요" : esc(d.hits.map((h) => `${h.label} (${h.fromDeg}°부터)`).join(", "))}</small></span><b>${d.clear ? "열려요" : "걸려요"}</b></li>`).join("")
      : `<li class="v-none"><span>열어 볼 가전 문이 없어요</span></li>`;
    const util = rep.utilities.length ? rep.utilities.map((u) => `<li class="s-${u.status}"><span>${esc(u.label)}<small>${esc(u.detail)}</small></span><b>${STATUS_KO[u.status] || u.status}</b></li>`).join("")
      : `<li class="v-none"><span>전기·물을 쓰는 장이 없어요</span></li>`;
    return `<div class="re-results">
      <section><h4>들어가요?</h4><ul>${fit}</ul></section>
      <section><h4>문·서랍이 열려요?</h4><ul>${doors}</ul></section>
      <section><h4>전기·급배수·방열</h4><ul>${util}</ul></section></div>`;
  };
  const palette = () => {
    const room = st.palRoom;
    const groups = {};
    for (const p of P.presets) if (p.room === room) (groups[p.group] ||= []).push(p);
    return `<div class="re-pal">
      <div class="seg2 re-palroom" role="group" aria-label="가구 종류">${Object.entries(ROOM_KO).map(([k, v]) => `<button data-palroom="${k}" class="${room === k ? "on" : ""}" aria-pressed="${room === k}">${v}</button>`).join("")}</div>
      ${st.replace ? `<p class="re-tip">바꿀 장을 골라 주세요 <button class="linklike" id="reReplaceOff">그만두기</button></p>` : ""}
      ${Object.entries(groups).map(([g, list]) => `<div class="re-pgrp"><span>${esc(g)}</span><div>${list.map((p) => `<button class="re-chip" data-add="${esc(p.id)}" title="${esc(p.label)}${P.sources[p.source]?.label ? ` · ${esc(P.sources[p.source].label)}` : ""}">${esc(p.label)}</button>`).join("")}</div></div>`).join("")}
    </div>`;
  };
  const propsHtml = () => {
    const q = st.sel && find(st.sel);
    if (!q) return `<div class="re-props empty"><p>정면도에서 장을 누르면 크기·문짝·색을 바꿀 수 있어요. 끌면 순서가 바뀌어요.</p></div>`;
    const { m } = q, c = cfgOf(m), pr = byId[m.preset || c?.preset] || null;
    if (!c) return `<div class="re-props"><p>불러오는 중…</p></div>`;
    const k = ctx.kinds[c.kind] || {};
    const label = pr?.label || k.label || c.kind;
    const opts = pr?.options || {};
    const toe = (c.parts.toe_kick || 0) + (c.parts.counter || 0);
    const bodyH = c.outer_mm.h - (k.band === "wall" ? 0 : toe);
    const chips = (name, list, cur, unit = "") => list?.length ? `<div class="re-chips" role="group" aria-label="${name}">${list.map((v) => `<button data-${name}="${v}" class="${Math.round(cur) === v ? "on" : ""}">${n0(v)}${unit}</button>`).join("")}</div>` : "";
    const sw = (part) => `<div class="cab-sws" role="radiogroup" aria-label="${part === "front" ? "도어 색" : "몸통 색"}">${(ctx.finishes.panel || []).map((f) => `<button class="cab-sw k-${esc(f.kind)}${c.finish?.[part] === f.id ? " on" : ""}" data-sw="${part}" data-fin="${esc(f.id)}" title="${esc(f.label)}" aria-label="${esc(f.label)}" style="--sw:${esc(f.hex)}"><i></i></button>`).join("")}</div>`;
    const styles = k.styles?.length ? `<label class="re-sel"><span>문짝</span><select id="reStyle">${k.styles.map((s) => `<option value="${s}" ${c.parts.style === s ? "selected" : ""}>${STYLE_KO[s]}</option>`).join("")}</select></label>` : "";
    const hinge = "hinge" in c.parts && (c.parts.style || "door") === "door" && (c.parts.doors || 1) === 1 ? `<label class="re-sel"><span>여는 쪽</span><select id="reHinge"><option value="r" ${c.parts.hinge === "r" ? "selected" : ""}>오른쪽 경첩</option><option value="l" ${c.parts.hinge === "l" ? "selected" : ""}>왼쪽 경첩</option></select></label>` : "";
    const glass = c.glass ? `<label class="re-sel"><span>유리</span><select id="reGlass">${(ctx.finishes.glass || []).map((g) => `<option value="${esc(g.id)}" ${c.glass === g.id ? "selected" : ""}>${esc(g.label)}</option>`).join("")}</select></label>` : "";
    const hung = q.t === "wall" || "base_mm" in c;
    const app = k.host?.length ? appPicker(m, c, k) : "";
    const num = (id, v, lab) => `<label class="cab-num"><span>${lab}</span><input type="number" inputmode="numeric" min="0" step="10" id="${id}" value="${v ?? ""}"><i>mm</i></label>`;
    return `<div class="re-props">
      <div class="re-ph"><div><span class="cab-kicker">${esc(TIER_KO[q.t])} ${q.i + 1}번째</span><h3>${esc(label)}</h3>
        <small>${pr ? esc(P.sources[pr.source]?.label || "") : "직접 만든 장"}</small></div>
        <div class="re-acts" role="group" aria-label="장 다루기">
          <button class="icon-btn sm" data-act="left" title="왼쪽으로" aria-label="왼쪽으로" ${q.i === 0 ? "disabled" : ""}>‹</button>
          <button class="icon-btn sm" data-act="right" title="오른쪽으로" aria-label="오른쪽으로" ${q.i === st.rows[q.t].length - 1 ? "disabled" : ""}>›</button>
          <button class="ghost small" data-act="before" aria-pressed="${st.before}">${st.before ? "앞에 넣는 중" : "앞에 넣기"}</button>
          <button class="ghost small" data-act="dup">복제</button>
          <button class="ghost small" data-act="replace" aria-pressed="${!!st.replace}">교체</button>
          <button class="ghost small danger" data-act="del">삭제</button></div></div>
      ${app}
      <div class="re-row"><span>폭</span>${chips("w", opts.w, c.outer_mm.w)}${num("reW", c.outer_mm.w, "직접")}</div>
      ${opts.h ? `<div class="re-row"><span>${k.band === "wall" ? "높이" : "몸체 높이"}</span>${chips("bh", opts.h, bodyH)}</div>` : ""}
      <div class="re-grid">${num("reH", c.outer_mm.h, "전체 높이")}${num("reD", c.outer_mm.d, "깊이")}${num("reGap", m.gap_mm, "왼쪽 틈")}${hung ? num("reBase", c.base_mm, "바닥에서 밑면") : ""}</div>
      <div class="re-grid">${styles}${hinge}${glass}</div>
      <div class="re-fin"><span>도어</span>${sw("front")}</div>
      <div class="re-fin"><span>몸통</span>${sw("body")}</div>
      <button class="ghost small" id="reFinAll">이 색을 세트 전체에</button>
    </div>`;
  };
  const appPicker = (m, c, k) => {
    const placed = ctx.placed().filter((x) => !x.cab && !String(x.sku).startsWith("decor:") && k.host.includes(ctx.category(x.sku)));
    const cand = ctx.candidates(c.kind);
    const curId = m.app?.id, curSku = m.app?.sku;
    const inCab = st.rep?.modules.find((q) => q.id === m._pid)?.app;
    const label = inCab ? ctx.nameOf(inCab.sku) : null;
    return `<div class="re-app"><span>넣을 가전</span>
      ${label ? `<b>${esc(label)}</b><small>${inCab.cab_made === false ? "이미 놓은 가전을 연결했어요" : "이 장과 같이 놓아요"}</small>` : `<small>가전을 고르지 않으면 빈 공간 치수로만 보고, 설치 기준은 확인 필요로 나와요</small>`}
      <select id="reApp" aria-label="넣을 가전 고르기"><option value="">${label ? "다른 가전으로 바꾸기" : "가전 고르기"}</option>
        ${placed.length ? `<optgroup label="이미 놓은 가전 연결">${placed.map((x) => `<option value="id:${esc(x.placement_id)}" ${curId === x.placement_id ? "selected" : ""}>${esc(ctx.nameOf(x.sku))}</option>`).join("")}</optgroup>` : ""}
        <optgroup label="LG 공식 설치 기준 있음">${cand.filter((q) => q.rule).map((q) => `<option value="sku:${esc(q.sku)}" ${curSku === q.sku ? "selected" : ""}>${esc(q.name)} · ${esc(q.sku)}</option>`).join("")}</optgroup>
        <optgroup label="공식 기준 없음 · 판정 불가">${cand.filter((q) => !q.rule).map((q) => `<option value="sku:${esc(q.sku)}" ${curSku === q.sku ? "selected" : ""}>${esc(q.name)} · ${esc(q.sku)}</option>`).join("")}</optgroup>
        ${label ? `<option value="none">가전 빼기</option>` : ""}</select></div>`;
  };
  const wallStep = () => {
    const c = center;
    const ops = (id) => (ctx.room.openings || []).filter((o) => o.wall_id === id);
    const walls = ctx.room.walls.map((w, i) => ({ w, i, L: Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]) })).filter((q) => q.L > 0.6)
      .sort((a, b) => b.L - a.L);
    const what = (id) => { const o = ops(id); const win = o.filter((x) => x.type === "window").length, door = o.length - win; return [win ? `창 ${win}` : "", door ? `문 ${door}` : ""].filter(Boolean).join("·") || "막힘 없음"; };
    return `<div class="re-step"><h3>어느 벽에 만들까요?</h3><p>3D에서 벽을 누르거나 아래에서 골라 주세요.</p>
      <div class="re-walls">${walls.map((q) => `<button class="re-chip" data-rewall="${esc(q.w.wall_id)}">벽 ${q.i + 1} <small>${(q.L).toFixed(2)} m · ${what(q.w.wall_id)}</small></button>`).join("")}</div></div>`;
    void c;
  };
  const startStep = () => `<div class="re-step"><h3>어떻게 시작할까요?</h3><p>시작 세트를 고른 뒤에도 장 하나하나를 바꿀 수 있어요.</p>
    <div class="re-starts">${P.starters.map((s) => `<button class="re-start" data-starter="${esc(s.id)}"><b>${esc(s.label)}</b><small>${s.id === "empty" ? "아래 목록에서 장을 하나씩 골라요" : esc([...s.rows.base, ...s.rows.wall].map((x) => byId[typeof x === "string" ? x : x.preset]?.label).filter(Boolean).slice(0, 4).join(" · "))}</small></button>`).join("")}</div></div>`;

  const render = () => {
    const s = step();
    const rep = st.rep;
    mount.hidden = false;
    mount.innerHTML = `<div class="re-head"><div><span class="cab-kicker">벽면 맞춤가구</span><h2>${st.run_id ? "세트 고치기" : "새로 만들기"}${st.wall_id ? ` · 벽 ${ctx.room.walls.findIndex((w) => w.wall_id === st.wall_id) + 1}` : ""}</h2></div>
        <div class="re-headbtn">${st.wall_id && !st.run_id ? `<button class="ghost small" id="reWall">벽 바꾸기</button>` : ""}<button class="ghost small" id="reCancel">취소</button>
        <button class="primary small" id="reOk" ${s !== "edit" || !rep || st.busy ? "disabled" : ""}>배치 확정</button></div></div>
      ${st.note ? `<p class="re-note">${esc(st.note)}</p>` : ""}
      ${s === "wall" ? wallStep() : s === "start" ? startStep() : `
      <div class="re-body">
        <div class="re-main">
          ${rep ? `<p class="re-usage">${usageText(rep)}</p>` : ""}
          <div class="re-el">${rep ? elevationSvg(rep, st.sel && find(st.sel)?.m._pid, st.cabs, ctx.finishes, H) : `<p class="re-wait">불러오는 중…</p>`}</div>
          <div class="re-start-in"><label class="cab-num"><span>하부 시작</span><input type="number" step="10" id="reS0" value="${st.start_mm.base}"><i>mm</i></label>
            <label class="cab-num"><span>상부 시작</span><input type="number" step="10" id="reS1" value="${st.start_mm.wall}"><i>mm</i></label>
            <button class="ghost small" id="reAlign" title="하부장 상판 높이를 다리 높이로 맞춰요. 가전 매입부는 그대로 둬요">상판선 맞추기</button>
            ${st.run_id ? `<button class="ghost small danger" id="reDrop">세트 지우기</button>` : ""}</div>
          ${palette()}
        </div>
        <div class="re-side">
          ${rep ? issueHtml(rep.issues, rep.notes || []) : ""}
          ${propsHtml()}
          ${rep ? sourceText(rep) + resultHtml(rep) : ""}
        </div>
      </div>`}`;
    wire();
  };

  // ---------- 연결 ----------
  const wire = () => {
    const $ = (s) => mount.querySelector(s);
    $("#reCancel")?.addEventListener("click", () => close(false));
    $("#reOk")?.addEventListener("click", confirm);
    $("#reWall")?.addEventListener("click", () => change(() => { st.wall_id = null; st.picking = true; ctx.wallPick(true); }));
    mount.querySelectorAll("[data-rewall]").forEach((b) => b.addEventListener("click", () => pickWall(b.dataset.rewall)));
    mount.querySelectorAll("[data-starter]").forEach((b) => b.addEventListener("click", () => {
      const s = P.starters.find((q) => q.id === b.dataset.starter);
      change(() => {
        const rows = starterRows(s, byId);
        for (const t of TIERS) st.rows[t].push(...rows[t]);
        if (s.room) { st.room = s.room; st.palRoom = s.room; }
        st.chose = true;
      });
    }));
    mount.querySelectorAll("[data-palroom]").forEach((b) => b.addEventListener("click", () => { st.palRoom = b.dataset.palroom; render(); }));
    mount.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => add(b.dataset.add)));
    $("#reReplaceOff")?.addEventListener("click", () => { st.replace = false; render(); });
    const num = (el) => (el.value === "" ? null : Number(el.value));
    $("#reS0")?.addEventListener("change", (e) => change(() => { st.start_mm.base = num(e.target) || 0; }));
    $("#reS1")?.addEventListener("change", (e) => change(() => { st.start_mm.wall = num(e.target) || 0; }));
    $("#reAlign")?.addEventListener("click", alignNow);
    $("#reDrop")?.addEventListener("click", dropRun);
    mount.querySelectorAll("[data-goto]").forEach((li) => li.addEventListener("click", () => { const q = modOf(li.dataset.goto); if (q) { st.sel = q.m.uid; render(); } }));
    // 정면도: 누르면 고르고, 옆으로 끌면 순서를 바꾼다
    const svg = $("#elSvg");
    if (svg) {
      const toMm = (e) => { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; return pt.matrixTransform(svg.getScreenCTM().inverse()).x; };
      svg.querySelectorAll(".el-mod").forEach((g) => {
        g.addEventListener("pointerdown", (e) => {
          const q = modOf(g.dataset.mid);
          if (!q) return;
          const x0 = toMm(e);
          let moved = false;
          try { g.setPointerCapture(e.pointerId); } catch { /* 펜·터치 흉내 등 잡을 수 없는 포인터 */ }
          const mv = (ev) => { const dx = toMm(ev) - x0; if (Math.abs(dx) > 40) moved = true; g.style.transform = moved ? `translate(${dx}px,0)` : ""; g.classList.toggle("drag", moved); };
          const up = (ev) => {
            g.removeEventListener("pointermove", mv); g.removeEventListener("pointerup", up);
            if (!moved) { st.sel = q.m.uid; st.before = false; render(); return; }
            const at = toMm(ev);
            const row = st.rows[q.t], mods = st.rep.modules.filter((x) => x.tier === q.t && x.id !== g.dataset.mid);
            const to = mods.filter((x) => (x.s0 + x.s1) / 2 < at).length;
            change(() => { const [it] = row.splice(q.i, 1); row.splice(to, 0, it); st.sel = it.uid; });
          };
          g.addEventListener("pointermove", mv); g.addEventListener("pointerup", up);
        });
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { const q = modOf(g.dataset.mid); if (q) { st.sel = q.m.uid; render(); } } });
      });
    }
    // 고른 장
    const q = st.sel && find(st.sel);
    if (!q) return;
    const c = cfgOf(q.m);
    mount.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      const a = b.dataset.act, row = st.rows[q.t];
      if (a === "left" && q.i > 0) change(() => { [row[q.i - 1], row[q.i]] = [row[q.i], row[q.i - 1]]; });
      if (a === "right" && q.i < row.length - 1) change(() => { [row[q.i + 1], row[q.i]] = [row[q.i], row[q.i + 1]]; });
      if (a === "before") { st.before = !st.before; render(); }
      if (a === "replace") { st.replace = !st.replace; render(); }
      if (a === "dup") change(() => {
        const { uid: _u, id: _i, _pid, app: _a, ...rest } = q.m;
        const cc = c ? { outer_mm: { ...c.outer_mm }, parts: { ...c.parts, ...(rest.parts || {}) }, finish: { ...c.finish }, ...(c.glass ? { glass: c.glass } : {}), ...(c.base_mm != null ? { base_mm: c.base_mm } : {}) } : {};
        const preset = rest.preset || c?.preset;
        if (preset) delete cc.parts;
        const m2 = { ...rest, ...cc, ...(preset ? { preset } : { kind: c?.kind }), uid: uid(), gap_mm: 0 };
        row.splice(q.i + 1, 0, m2);
        st.sel = m2.uid;
      });
      if (a === "del") change(() => { row.splice(q.i, 1); st.sel = null; });
    }));
    const setOuter = (k, v) => patch(q.m.uid, (m) => { m.outer_mm = { ...(m.outer_mm || {}), [k]: v }; m.dims_by = "user"; });
    mount.querySelectorAll("[data-w]").forEach((b) => b.addEventListener("click", () => setOuter("w", Number(b.dataset.w))));
    mount.querySelectorAll("[data-bh]").forEach((b) => b.addEventListener("click", () => {
      const k = ctx.kinds[c.kind] || {};
      const extra = k.band === "wall" ? 0 : (c.parts.toe_kick || 0) + (c.parts.counter || 0);
      setOuter("h", Number(b.dataset.bh) + extra);
    }));
    const bindNum = (id, fn) => $(id)?.addEventListener("change", (e) => { const v = num(e.target); if (v != null && v >= 0) fn(v); });
    bindNum("#reW", (v) => setOuter("w", v));
    bindNum("#reH", (v) => setOuter("h", v));
    bindNum("#reD", (v) => setOuter("d", v));
    bindNum("#reGap", (v) => patch(q.m.uid, (m) => { m.gap_mm = v; }));
    bindNum("#reBase", (v) => patch(q.m.uid, (m) => { m.base_mm = v; }));
    $("#reStyle")?.addEventListener("change", (e) => patch(q.m.uid, (m) => { m.parts = { ...(m.parts || {}), style: e.target.value }; }));
    $("#reHinge")?.addEventListener("change", (e) => patch(q.m.uid, (m) => { m.parts = { ...(m.parts || {}), hinge: e.target.value }; }));
    $("#reGlass")?.addEventListener("change", (e) => patch(q.m.uid, (m) => { m.glass = e.target.value; }));
    mount.querySelectorAll("[data-sw]").forEach((b) => b.addEventListener("click", () => patch(q.m.uid, (m) => { m.finish = { ...(m.finish || {}), [b.dataset.sw]: b.dataset.fin }; })));
    $("#reFinAll")?.addEventListener("click", () => change(() => {
      const fin = { front: c.finish.front, body: c.finish.body };
      for (const t of TIERS) for (const m of st.rows[t]) m.finish = { ...(m.finish || {}), ...fin };
      ctx.toast("세트 전체에 같은 색을 입혔어요");
    }));
    $("#reApp")?.addEventListener("change", (e) => {
      const v = e.target.value;
      if (!v) return;
      patch(q.m.uid, (m) => {
        if (v === "none") m.app = null;
        else if (v.startsWith("id:")) m.app = { id: v.slice(3) };
        else m.app = { sku: v.slice(4) };
        if (m.app && !m.dims_by) delete m.outer_mm; // 공식 기준이 있는 모델이면 서버가 그 치수로 맞춘다
      });
    });
  };

  const pickWall = (wid) => {
    if (!ctx.room.walls.some((w) => w.wall_id === wid)) return;
    st.picking = false;
    ctx.wallPick(false);
    change(() => { st.wall_id = wid; });
    ctx.lookWall?.(wid);
  };
  const alignNow = async () => {
    const s = spec();
    try {
      const r = await ctx.api(`/api/projects/${ctx.pid}/runs/preview`, { method: "POST", body: JSON.stringify({ ...s, align: true }) });
      // 바뀐 다리 높이·외경을 모듈 값으로 옮긴다
      for (const m of r.modules) {
        const q = all().find((x) => x.t === m.tier && x.i === m.idx);
        const cab = r.scene_state.placements.find((x) => x.placement_id === m.id)?.cab;
        if (!q || !cab || q.t !== "base") continue;
        const old = st.cabs[q.m._pid];
        if (old && old.outer_mm.h !== cab.outer_mm.h) {
          q.m.outer_mm = { ...(q.m.outer_mm || {}), h: cab.outer_mm.h };
          q.m.parts = { ...(q.m.parts || {}), toe_kick: cab.parts.toe_kick };
          q.m.dims_by = "user";
        }
      }
      ctx.toast(r.notes?.length ? r.notes.join(" · ") : "상판 높이가 이미 맞아요");
      refresh();
    } catch (e) { ctx.toast(e.message, true); }
  };
  const confirm = async () => {
    if (st.busy) return;
    st.busy = true; render();
    try {
      const r = await ctx.api(`/api/projects/${ctx.pid}/runs`, { method: "POST", body: JSON.stringify(spec()) });
      close(true, r);
    } catch (e) { st.busy = false; ctx.toast(e.message, true); render(); }
  };
  const dropRun = async () => {
    if (!st.run_id) return;
    try {
      const r = await ctx.api(`/api/projects/${ctx.pid}/runs/${st.run_id}`, { method: "DELETE" });
      close(true, r, "세트를 지웠어요");
    } catch (e) { ctx.toast(e.message, true); }
  };
  let closed = false;
  const close = (ok, resp, msg) => {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    st.seq++;
    ctx.wallPick(false);
    mount.hidden = true;
    mount.innerHTML = "";
    if (ok) ctx.confirmed(resp, msg); else ctx.restore(true);
  };

  if (!st.wall_id) { st.picking = true; ctx.wallPick(true); }
  if (st.rows.base.length || st.rows.wall.length || st.run_id) st.chose = true;
  render();
  refresh();
  return {
    pickWall,
    select: (pid) => { const q = modOf(pid); if (q) { st.sel = q.m.uid; render(); } },
    picking: () => st.picking,
    has: (pid) => !!modOf(pid),
    cancel: () => close(false),
    redraw: () => { if (st.rep) { st.doors = ctx.doors(st.rep.scene_state) || []; render(); } },
  };
}
