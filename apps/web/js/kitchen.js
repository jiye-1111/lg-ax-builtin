// 빌트인 주방 화면: 라이브러리 타일, 오른쪽 맞춤장 패널(공식 기준 판정 · 3D 문 열림 근사 · 치수·부재 · 마감).
// 판정 숫자는 서버(cab_check)가 낸 값만 보여 준다. 문 열림 근사는 cabinet.js doorCheck가 계산한다.
import { boxObstacle, cabObstacles, doorCheck, doorsOf, leafCorners, KIND_LABEL, OPEN_DEG, STEP_DEG } from "./cabinet.js";
import { esc } from "./core.js";

export const CAB_PREFIX = "decor:cab_";
export const cabKindOf = (sku) => (typeof sku === "string" && sku.startsWith(CAB_PREFIX) ? sku.slice(CAB_PREFIX.length) : null);
const HOST_KINDS = new Set(["fridge", "dishwasher"]);
const VERDICT_KO = { fit: "적합", conditional: "조건부", no_fit: "불가", unknown: "판정 불가" };
const MARK = { fit: "✓", conditional: "!", no_fit: "✕", unknown: "?" };
const CHECK_KO = { ok: "맞음", blocked: "불가", check: "확인 필요", site: "현장 확인", none: "공식 자료 없음" };
const SRC_KO = { designed: "설계값", measured: "실측값", scanned: "스캔값" };
const mm = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString("ko-KR")}`);

// 정면에서 본 선 그림 (라이브러리 타일)
const ICON = {
  fridge: `<rect x="9" y="4" width="30" height="40" rx="1"/><path d="M13 14h22v28H13zM24 14v28M13 8h22"/>`,
  dishwasher: `<path d="M6 16h36M8 16v26M40 16v26"/><rect x="13" y="20" width="22" height="22" rx="1"/><path d="M17 24h14"/>`,
  sink: `<path d="M6 18h36M8 18v24h32V18M24 18v24"/><path d="M18 18v-3a6 6 0 0 1 12 0"/><path d="M28 31v3M20 31v3"/>`,
  drawer: `<path d="M6 16h36"/><rect x="9" y="18" width="30" height="24" rx="1"/><path d="M9 25h30M9 33h30M21 21.5h6M21 29h6M21 37h6"/>`,
  wall: `<rect x="7" y="10" width="34" height="20" rx="1"/><path d="M24 10v20M20 26v-3M28 26v-3"/>`,
  pantry: `<rect x="14" y="4" width="20" height="40" rx="1"/><path d="M14 40h20M30 20v8"/>`,
  glass_wall: `<rect x="7" y="10" width="34" height="20" rx="1"/><path d="M24 10v20M11 14h9v12h-9zM28 14h9v12h-9zM11 20h9M28 20h9"/>`,
  counter: `<path d="M4 20h40v5H4z"/><path d="M8 25v16M40 25v16"/>`,
  filler: `<path d="M20 6v36M28 6v36M20 6h8M20 42h8"/>`,
  end_panel: `<path d="M18 6h4v36h-4zM22 6l8 4v30l-8 2"/>`,
};
export function kitchenLibHtml(kinds) {
  const tile = (k) => `<button class="dtile cab-tile" data-decor="${CAB_PREFIX}${k.kind}" title="${esc(k.label)} 놓기">
      <span class="dimg"><svg viewBox="0 0 48 48" aria-hidden="true">${ICON[k.kind] || ""}</svg></span><span>${esc(k.label)}</span></button>`;
  const one = kinds.filter((k) => k.stage === 1);
  const sec = (title, list, note = "") => `<section class="dsec"><h3>${title}</h3>${note}<div class="dgrid">${list.map(tile).join("")}</div></section>`;
  const next = kinds.filter((k) => k.stage === 2).map((k) => k.label).join(" · ");
  return sec("가전 맞춤장", one.filter((k) => HOST_KINDS.has(k.kind)), `<p class="hint-sm cab-lead">LG 가전을 고르면 그 가전이 들어갈 빈 공간을 가진 장을 만들어요</p>`)
    + sec("주방 가구", one.filter((k) => ["sink", "drawer", "wall", "glass_wall", "pantry", "counter"].includes(k.kind)))
    + sec("마감 부재", one.filter((k) => ["filler", "end_panel"].includes(k.kind)))
    + (next ? `<p class="hint-sm cab-next">다음 단계: ${esc(next)}</p>` : "");
}

/** 3D 문 열림 근사 검사. 장 안 가전의 문을 3°마다 90°까지 열어 보고 측판·옆 장·손잡이·걸레받이·아일랜드·벽에 걸리는지 본다 */
export function doorReport({ cab, app, product, placements, room, hidden = {} }) {
  if (!cab || !app || !product) return null;
  const a = { xz: app.center_xz, yaw: app.yaw_rad, base: app.base_m || 0, w: app.size_m[0] * 1000, h: app.size_m[1] * 1000, d: app.size_m[2] * 1000,
    category: product.category, bottomMm: cab.cab_check?.door_bottom_mm };
  if (!doorsOf(a).length) return null;
  const obs = [...cabObstacles(cab, { host: true })];
  for (const q of placements) {
    if (q.placement_id === app.placement_id || q.placement_id === cab.placement_id || !q.size_m) continue;
    if (q.sku === "decor:rug" || q.sku === "decor:window") continue;
    if (q.cab) { obs.push(...cabObstacles(q)); continue; }
    const label = q.sku === "decor:island" || q.sku === "decor:islandtable" ? "아일랜드" : q.label || "옆 가구";
    obs.push(boxObstacle(q.placement_id, label, q.center_xz, q.yaw_rad, q.size_m[0], q.size_m[2], q.base_m || 0, (q.base_m || 0) + q.size_m[1]));
  }
  const goneWalls = new Set(hidden.walls || []), goneObj = new Set(hidden.objects || []);
  for (const w of room?.walls || []) {
    if (goneWalls.has(w.wall_id)) continue;
    const dx = w.end[0] - w.start[0], dz = w.end[1] - w.start[1], L = Math.hypot(dx, dz);
    if (L < 1e-3) continue;
    obs.push(boxObstacle(w.wall_id, "벽", [(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2], Math.atan2(dz, dx) + Math.PI / 2, L, w.thickness_m || 0.1, 0, 3));
  }
  for (const o of room?.objects || []) {
    if (goneObj.has(o.object_id)) continue;
    obs.push(boxObstacle(o.object_id, "스캔한 가구", [o.position[0], o.position[2]], o.yaw_rad, o.bbox_m.w, o.bbox_m.d, o.position[1] - o.bbox_m.h / 2, o.position[1] + o.bbox_m.h / 2));
  }
  const res = doorCheck(a, obs);
  const ds = doorsOf(a);
  // 3D 경고: 걸린 문짝은 처음 걸린 각도의 모습을 빨갛게
  const warn = res.hits.map((h) => ({ corners: leafCorners(a, ds[h.door], h.fromDeg), hit: true }));
  return { ...res, warn, show: ds.map((d) => ({ corners: leafCorners(a, d, OPEN_DEG), hit: false })) };
}

// ---------- 오른쪽 패널 ----------
const PART_ROWS = [
  ["side_l", "왼쪽 측판"], ["side_r", "오른쪽 측판"], ["upper_h", "위 수납장 높이"], ["counter", "상판 두께"], ["back", "뒷판 (0 = 없음)"],
  ["toe_kick", "걸레받이 높이"], ["toe_recess", "걸레받이 들임"], ["filler_l", "왼쪽 틈막이판"], ["filler_r", "오른쪽 틈막이판"],
  ["end_l", "왼쪽 측면 마감판"], ["end_r", "오른쪽 측면 마감판"],
];
const COUNT_ROWS = [["shelves", "선반"], ["drawers", "서랍"], ["doors", "문짝"]];
const TOGGLES = [["kick_across", "걸레받이를 식기세척기 앞까지 잇기"], ["bowl", "싱크볼·수전"]];
const FIN_ROWS = [["front", "도어·서랍 앞판", "panel"], ["body", "몸통·측면 마감판", "panel"], ["top", "상판", "top"], ["handle", "손잡이·프레임", "handle"]];
const STONE_KINDS = new Set(["sink", "drawer", "dishwasher", "counter"]);

const swatch = (f, on, part) => `<button class="cab-sw k-${esc(f.kind)}${on ? " on" : ""}" data-fpart="${part}" data-fin="${esc(f.id)}" role="radio" aria-checked="${on}"
  title="${esc(f.label)}" aria-label="${esc(f.label)}" style="--sw:${esc(f.hex || "transparent")}"><i></i></button>`;

function verdictHtml(chk) {
  const v = chk.verdict;
  const rows = chk.axes.map((a) => `<tr class="v-${a.verdict}"><th scope="row">${esc(a.label)}</th><td>${esc(a.need_text)}</td>
      <td>${mm(a.have_mm)}<small>${esc(SRC_KO[a.source] || "")}</small></td>
      <td>${a.short_mm ? `<b>${mm(a.short_mm)}</b>` : a.over_mm ? `<b>+${mm(a.over_mm)}</b>` : a.verdict === "unknown" ? "?" : "–"}</td></tr>`).join("");
  const outline = !chk.axes.length ? `<table class="cab-tbl"><thead><tr><th></th><th>제품 외형</th><th>장 안쪽</th><th></th></tr></thead><tbody>${
    ["w", "h", "d"].map((k) => { const o = chk.outline[k]; return `<tr class="v-${o.fits === false ? "no_fit" : "unknown"}"><th scope="row">${{ w: "폭", h: "높이", d: "깊이" }[k]}</th><td>${mm(o.product_mm)}</td><td>${mm(o.have_mm)}</td><td>${o.fits === false ? "<b>작음</b>" : o.fits ? "들어감" : "?"}</td></tr>`; }).join("")}</tbody></table>` : "";
  const front = chk.front ? `<p class="cab-front">정면: ${chk.front.state === "flush" ? "장 앞면과 <b>맞아요</b>"
    : chk.front.state === "protrudes" ? `장 앞면보다 <b>${mm(chk.front.offset_mm)} mm 돌출</b>돼요` : `장 앞면보다 <b>${mm(-chk.front.offset_mm)} mm 들어가요</b>`}</p>` : "";
  const checks = chk.checks.length ? `<ul class="cab-checks">${chk.checks.map((c) => `<li class="s-${c.status}"><span>${esc(c.label)}<small>${esc(c.detail)}</small></span><b>${CHECK_KO[c.status]}</b></li>`).join("")}</ul>` : "";
  const basis = chk.axes.length ? `<details class="cab-basis"><summary>근거</summary><ul>${chk.axes.map((a) => `<li><b>${esc(a.label)}</b> ${esc(a.basis)}${a.note ? ` · ${esc(a.note)}` : ""}</li>`).join("")}</ul>
      <p><a href="${esc(chk.source_url)}" target="_blank" rel="noopener">${esc(chk.source_title)} ↗</a> <span class="muted">${esc(chk.checked_at || "")} 확인</span></p></details>` : "";
  return `<section class="cab-verdict v-${v}" aria-label="LG 공식 설치 기준 판정">
    <header><span class="mark" aria-hidden="true">${MARK[v]}</span><div><h3>LG 공식 기준 · ${VERDICT_KO[v]}</h3><p>${esc(chk.summary)}</p></div></header>
    ${front}
    ${chk.axes.length ? `<table class="cab-tbl"><thead><tr><th></th><th>필요</th><th>확보</th><th>부족</th></tr></thead><tbody>${rows}</tbody></table>` : outline}
    ${checks}
    <p class="cab-scope">${esc(chk.scope)}. ‘적합’은 검사한 범위 기준이에요.</p>
    ${basis}
  </section>`;
}

function doorHtml(r) {
  if (!r) return "";
  const what = r.hits.map((h) => `<li><span>${esc(h.label)}</span><b>${h.fromDeg}°부터</b></li>`).join("");
  return `<section class="cab-door ${r.clear ? "ok" : "bad"}" aria-label="3D 문 열림 근사 검사">
    <h3>3D 문 열림 근사 검사 <span>${r.clear ? "걸림 없음" : "걸림"}</span></h3>
    <p>${r.clear ? `문을 ${r.openDeg}°까지 ${r.stepDeg}°마다 열어 봤는데 걸리는 것이 없어요` : `문을 ${r.stepDeg}°마다 열어 보면 이것에 걸려요`}</p>
    ${what ? `<ul>${what}</ul>` : ""}
    <small>문짝을 두께 60 mm 판으로 본 3D 근사예요. LG 공식 판정과 따로 봐요${r.assumed ? ". 문 밑 높이는 기준이 없어 150 mm로 봤어요" : ""}</small>
  </section>`;
}

/** 맞춤장 패널. x = 장 배치, app = 안에 넣은 가전 배치, product = 그 가전 카탈로그, kind = 종류 정보,
 *  finishes = 마감 목록, candidates = 넣을 수 있는 가전 [{sku, name, rule}], others = 다른 맞춤장 [{id, label}], report = doorReport 결과 */
export function cabPanelHtml({ x, app, product, kind, finishes, candidates = [], others = [], report = null, pick = [] }) {
  const c = x.cab, host = HOST_KINDS.has(c.kind), existing = c.mode === "existing";
  const parts = PART_ROWS.filter(([k]) => k in c.parts);
  const counts = COUNT_ROWS.filter(([k]) => k in c.parts);
  const toggles = TOGGLES.filter(([k]) => k in c.parts);
  const inside = x.cab_check?.inside_mm;
  const numIn = (name, v, label, opt = "") => `<label class="cab-num"><span>${label}</span><input type="number" inputmode="numeric" min="0" step="1" data-${name} value="${v ?? ""}" ${opt}><i>mm</i></label>`;
  const rule = (s) => candidates.find((q) => q.sku === s)?.rule;
  const appRow = host ? (app ? `<div class="cab-app"><div><b>${esc(product?.name || app.sku)}</b><small>${esc(app.sku)} · ${rule(app.sku) ? "LG 공식 설치 기준 있음" : "공식 기준 없음 (외형만 비교)"}</small></div>
        <button class="ghost small" id="cabOut">빼기</button></div>` : `<p class="cab-empty">넣을 LG 가전을 골라 주세요</p>`) : "";
  const opts = (list) => list.map((q) => `<option value="${esc(q.sku)}" ${app?.sku === q.sku ? "disabled" : ""}>${esc(q.name)} · ${esc(q.sku)}</option>`).join("");
  const picker = host ? `<label class="cab-pick"><span class="sr">가전 고르기</span><select id="cabApp"><option value="">${app ? "다른 가전으로 바꾸기" : "가전 고르기"}</option>
      <optgroup label="LG 공식 설치 기준 있음">${opts(candidates.filter((q) => q.rule))}</optgroup>
      <optgroup label="공식 기준 없음 · 판정 불가">${opts(candidates.filter((q) => !q.rule))}</optgroup></select></label>` : "";
  const finRows = FIN_ROWS.filter(([p]) => p !== "top" || STONE_KINDS.has(c.kind)).filter(([p]) => !(c.kind === "counter" && p !== "top"));
  const fin = finRows.map(([part, label, group]) => `<div class="cab-finrow"><span>${label}</span><div class="cab-sws" role="radiogroup" aria-label="${label}">
      ${(finishes[group] || []).map((f) => swatch(f, c.finish[part] === f.id, part)).join("")}</div></div>`).join("")
    + (c.glass ? `<div class="cab-finrow"><span>유리</span><div class="cab-sws" role="radiogroup" aria-label="유리">${(finishes.glass || []).map((f) => swatch(f, c.glass === f.id, "glass")).join("")}</div></div>` : "");
  const many = others.length ? `<div class="cab-many"><span>같이 바꿀 장</span>${others.map((o) => `<label class="chip"><input type="checkbox" data-also="${esc(o.id)}" ${pick.includes(o.id) ? "checked" : ""}>${esc(o.label)}</label>`).join("")}</div>` : "";
  return `<div class="cab-panel">
    <div class="cab-head"><div><span class="cab-kicker">빌트인 주방 · 맞춤장</span><h2 class="insp-name">${esc(kind?.label || KIND_LABEL[c.kind])}</h2></div>
      <button class="ghost small" id="inspClose" aria-label="선택 풀기">닫기</button></div>
    ${host ? `<div class="seg2 cab-mode" role="group" aria-label="만드는 방법"><button data-mode="new" aria-pressed="${!existing}" class="${existing ? "" : "on"}">새 장 설계</button><button data-mode="existing" aria-pressed="${existing}" class="${existing ? "on" : ""}">기존 장에 넣기</button></div>
      <p class="hint-sm cab-modehint">${existing ? "줄자로 잰 장 안쪽 치수를 그대로 써요. 가전을 바꿔도 장 크기는 그대로예요" : "공식 기준이 있는 가전은 안쪽 권장 치수로 장을 맞춰요. 숫자는 설계값이에요"}</p>
      ${appRow}${picker}` : ""}
    ${x.cab_check ? verdictHtml(x.cab_check) : ""}
    ${doorHtml(report)}
    <details class="cab-sec"${existing ? " open" : ""}><summary>장 치수·부재</summary>
      <div class="cab-grid">${numIn("ow", c.outer_mm.w, "외경 폭")}${numIn("oh", c.outer_mm.h, "외경 높이")}${numIn("od", c.outer_mm.d, "외경 깊이")}</div>
      ${host && existing ? `<p class="cab-sub">장 안쪽 실측 <span class="muted">비워 두면 판정 불가</span></p><div class="cab-grid">${numIn("mw", c.measured_mm?.w, "안쪽 폭")}${numIn("mh", c.measured_mm?.h, "안쪽 높이")}${numIn("md", c.measured_mm?.d, "안쪽 깊이")}</div>` : ""}
      ${host && !existing && inside ? `<p class="cab-inside">가전이 들어가는 안쪽 <b>${mm(inside.w)} × ${mm(inside.h)} × ${mm(inside.d)} mm</b> <span class="muted">설계값</span></p>` : ""}
      ${host && !existing && app && rule(app.sku) ? `<button class="ghost small cab-fitbtn" id="cabSuggest">이 가전 권장 치수로 맞추기</button>` : ""}
      ${parts.length ? `<div class="cab-grid parts">${parts.map(([k, l]) => numIn(`p-${k}`, c.parts[k], l)).join("")}</div>` : ""}
      ${counts.length ? `<div class="cab-grid parts">${counts.map(([k, l]) => `<label class="cab-num"><span>${l}</span><input type="number" min="0" max="8" step="1" data-p-${k} value="${c.parts[k]}"><i>개</i></label>`).join("")}</div>` : ""}
      ${toggles.map(([k, l]) => `<label class="cab-tog"><input type="checkbox" data-t-${k} ${c.parts[k] ? "checked" : ""}><span>${l}</span></label>`).join("")}
      ${"base_mm" in c && c.kind !== "counter" ? `<div class="cab-grid">${numIn("base", c.base_mm, "바닥에서 밑면까지")}</div>` : ""}
    </details>
    <details class="cab-sec" open><summary>색상·마감</summary>${fin}${many}<p class="hint-sm">미리보기 색이에요. LG 가전 색은 제품 색 그대로예요</p></details>
  </div>`;
}

/** 패널 버튼·입력 연결. on: {close, patch(body), appliance(sku|null, resize), finish(part, id), also(ids)} */
export function wireCabPanel(box, x, on) {
  box.querySelector("#inspClose")?.addEventListener("click", on.close);
  box.querySelectorAll(".cab-mode [data-mode]").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.mode === x.cab.mode) return;
    on.patch(b.dataset.mode === "existing"
      ? { mode: "existing", measured_mm: { w: x.cab_check?.inside_mm?.w ?? null, h: x.cab_check?.inside_mm?.h ?? null, d: null } }
      : { mode: "new" });
  }));
  box.querySelector("#cabApp")?.addEventListener("change", (e) => { if (e.target.value) on.appliance(e.target.value, x.cab.mode === "new"); });
  box.querySelector("#cabOut")?.addEventListener("click", () => on.appliance(null, false));
  box.querySelector("#cabSuggest")?.addEventListener("click", () => on.appliance(on.appSku(), true));
  const num = (el) => (el.value === "" ? null : Number(el.value));
  const bind = (sel, make) => box.querySelectorAll(sel).forEach((el) => el.addEventListener("change", () => {
    const v = num(el);
    if (v !== null && (!Number.isFinite(v) || v < 0)) { el.value = ""; return; }
    on.patch(make(el, v));
  }));
  bind("[data-ow],[data-oh],[data-od]", (el, v) => ({ outer_mm: { [el.hasAttribute("data-ow") ? "w" : el.hasAttribute("data-oh") ? "h" : "d"]: v } }));
  bind("[data-mw],[data-mh],[data-md]", (el, v) => ({ measured_mm: { [el.hasAttribute("data-mw") ? "w" : el.hasAttribute("data-mh") ? "h" : "d"]: v } }));
  bind("[data-base]", (_el, v) => ({ base_mm: v }));
  box.querySelectorAll("input[type=number]").forEach((el) => {
    const key = [...el.attributes].map((a) => a.name).find((n) => n.startsWith("data-p-"));
    if (key) el.addEventListener("change", () => { const v = num(el); if (v !== null && v >= 0) on.patch({ parts: { [key.slice(7)]: v } }); });
  });
  box.querySelectorAll("input[type=checkbox]").forEach((el) => {
    const key = [...el.attributes].map((a) => a.name).find((n) => n.startsWith("data-t-"));
    if (key) el.addEventListener("change", () => on.patch({ parts: { [key.slice(7)]: el.checked } }));
  });
  box.querySelectorAll("[data-fin]").forEach((b) => b.addEventListener("click", () => on.finish(b.dataset.fpart, b.dataset.fin)));
  box.querySelectorAll("[data-also]").forEach((el) => el.addEventListener("change", () => on.also([...box.querySelectorAll("[data-also]:checked")].map((q) => q.dataset.also))));
}

export { STEP_DEG };
