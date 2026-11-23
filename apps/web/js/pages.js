// 화면: 내 집 스캔(첫 화면), 방문 스캔 신청, 기사 화면
import { $app, cleanup, esc, mm, api, apiUrl, post, put, toast, guard, localHomes, forgetHome, sampleHome, rememberSample, currentUser, homeThumb } from "./core.js";
import { makeViewer } from "./viewer.js";
import { planView } from "./plan.js";

// 눌러서 바로 쓰는 샘플 집. 가상 예시는 ‘예시’, 실제 스캔은 ‘실제 스캔’으로 적는다.
const SAMPLE_HOMES = [
  { file: "apt_living_kitchen.usdz", name: "거실과 주방이 이어진 집", tag: "예시" },
  { file: "studio_living.usdz", name: "주방 겸 거실 원룸", tag: "예시" },
  { file: "ugscan_2026-11-18.usdz", name: "아이폰으로 스캔한 강의실", tag: "실제 스캔" },
];
const ICON_SCAN = `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M12 7.5 16 9.8v4.4L12 16.5 8 14.2V9.8zM12 12v4.5M8 9.8l4 2.2 4-2.2"/></svg>`;
const ICON_PLAN = `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 11h7V4M11 15v5M15 11h5"/></svg>`;

export async function selfScan() {
  $app.innerHTML = `
    <section class="hero" aria-labelledby="heroH">
      <picture class="hero-bg">
        <source media="(max-width: 760px)" srcset="img/hero-kitchen-m.webp">
        <img src="img/hero-kitchen.webp" alt="창으로 햇빛이 드는 주방에 LG 디오스 오브제컬렉션 냉장고·김치냉장고·식기세척기가 빌트인으로 들어간 3D 렌더" fetchpriority="high">
      </picture>
      <div class="hero-inner">
        <div class="hero-copy">
          <p class="eyebrow"><i aria-hidden="true"></i>LiDAR 셀프 스캔으로 시작하는 가상 리모델링</p>
          <h1 id="heroH">스캔한 우리 집에<br>LG 빌트인을 미리.</h1>
          <p class="lede">아이폰으로 찍은 집이 그대로 3D가 됩니다. 냉장고와 식기세척기를 원하는 자리에 놓아 보고,
            들어가는지, 문이 열리는지, 볕과 와이파이, 다니는 길까지 살기 전에 확인하세요.</p>
        </div>
        <div class="start">
          <section class="start-box" aria-labelledby="upH">
            <h2 id="upH">내 집 올리기</h2>
            <div class="slots">
              ${slotHtml("scan", ICON_SCAN, "스캔 파일", "", "USDZ · UGScan 앱에서 내보낸 파일", ".usdz,.usd,.usda,.usdc")}
              ${slotHtml("plan", ICON_PLAN, "도면", "", "이미지나 PDF · 치수가 적힌 평면도", ".png,.jpg,.jpeg,.webp,.pdf")}
            </div>
            <p class="slots-note" id="slotsNote">${SLOT_NOTE.none}</p>
            <div class="start-foot"><a class="quiet" href="#/r">스캔이 어렵다면 기사 방문 신청</a>
              <button class="primary" id="go" disabled>3D로 만들기</button></div>
          </section>
          <section class="start-box" aria-labelledby="smH">
            <h2 id="smH">샘플 집으로 시작하기</h2>
            <div class="samples">${SAMPLE_HOMES.map((h, i) => `
              <button class="sample" data-sample="${i}"><span class="sample-img"><img src="img/samples/${esc(h.file.replace(/\.usdz$/, ""))}.webp" alt="" loading="lazy" decoding="async" draggable="false"><em>${esc(h.tag)}</em></span>
                <b>${esc(h.name)}</b></button>`).join("")}</div>
          </section>
        </div>
      </div>
    </section>
    <section class="recent" aria-labelledby="recentH">
      <h2 id="recentH">최근에 만든 집</h2>
      <ul class="list" id="projects"><li class="muted">불러오는 중…</li></ul>
    </section>`;

  // ---- 올리기: 스캔 파일(필수)과 도면(선택)을 칸을 나눠 받는다 ----
  const picked = { scan: null, plan: null };
  const go = document.getElementById("go");
  const OK = { scan: /\.(usdz|usd|usda|usdc)$/i, plan: /\.(png|jpe?g|webp|pdf)$/i };
  const setSlot = (kind, f) => {
    if (f && !OK[kind].test(f.name)) { toast(kind === "scan" ? "USDZ 파일을 올려 주세요" : "도면은 이미지나 PDF로 올려 주세요", true); return; }
    picked[kind] = f || null;
    const el = document.querySelector(`[data-slot="${kind}"]`);
    el.classList.toggle("has", !!f);
    el.querySelector(".slot-name").textContent = f ? f.name : "";
    el.querySelector(".slot-file").hidden = !f;
    if (!f) el.querySelector("input").value = "";
    go.disabled = !picked.scan && !picked.plan;
    document.getElementById("slotsNote").textContent = SLOT_NOTE[picked.scan ? (picked.plan ? "both" : "scan") : picked.plan ? "plan" : "none"];
  };
  document.querySelectorAll("[data-slot]").forEach((el) => {
    const kind = el.dataset.slot, input = el.querySelector("input");
    el.onclick = (e) => { if (!e.target.closest(".slot-x")) input.click(); };
    el.onkeydown = (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === el) { e.preventDefault(); input.click(); } };
    input.onclick = (e) => e.stopPropagation();
    input.onchange = () => input.files[0] && setSlot(kind, input.files[0]);
    el.querySelector(".slot-x").onclick = () => setSlot(kind, null);
    el.ondragover = (e) => { e.preventDefault(); el.classList.add("over"); };
    el.ondragleave = () => el.classList.remove("over");
    el.ondrop = (e) => { e.preventDefault(); el.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) setSlot(kind, f); };
  });
  const create = async (blob, filename, name) => {
    const fd = new FormData();
    fd.append("file", blob, filename);
    fd.append("scanned_by", "customer");
    if (name) fd.append("name", name);
    return api("/api/projects", { method: "POST", body: fd });
  };
  const openHome = (p) => { location.hash = `#/c/${p.project_id}?t=${p.share_token}`; };
  go.onclick = guard(async () => {
    if (!picked.scan && !picked.plan) return;
    go.disabled = true;
    try {
      if (!picked.scan) { // 도면만: 도면에서 벽·문·창을 읽어 집을 만든다
        go.textContent = "도면을 읽는 중… 2분쯤 걸려요";
        const fd = new FormData();
        fd.append("file", picked.plan, picked.plan.name);
        const made = await api("/api/projects/from-plan", { method: "POST", body: fd });
        if (made.scan.scale_from === "door_width") toast(ROUGH_SCALE);
        openHome(made);
        return;
      }
      go.textContent = "집을 3D로 만드는 중…";
      const p = await create(picked.scan, picked.scan.name);
      if (picked.plan) {
        go.textContent = "도면 치수로 맞추는 중… 2분쯤 걸려요";
        // 도면에서 탈이 나도 스캔으로 만든 집은 그대로 연다
        const done = await uploadFloorplan(p.project_id, picked.plan).catch((e) => ({ floorplan: { note: e.message } }));
        toast(planResult(done.floorplan), !done.floorplan?.applied);
      }
      openHome(p);
    } catch (e) { go.disabled = false; go.textContent = "3D로 만들기"; throw e; }
  });

  // ---- 샘플 집: 처음 누르면 만들고, 다음부터는 같은 집을 연다 ----
  document.querySelectorAll("[data-sample]").forEach((b) => (b.onclick = guard(async () => {
    const h = SAMPLE_HOMES[+b.dataset.sample], had = sampleHome(h.file);
    b.disabled = true; b.classList.add("busy");
    try {
      if (had) {
        const p = await api(`/api/projects/${had.pid}`).catch(() => null);
        if (p) { openHome(p); return; }
      }
      const blob = await (await fetch(apiUrl(`/api/samples/${h.file}`), { cache: "no-cache" })).blob(); // 샘플을 고친 뒤에 예전 파일이 뜨지 않게
      const p = await create(blob, h.file, h.name);
      rememberSample(h.file, { pid: p.project_id, token: p.share_token });
      openHome(p);
    } finally { b.disabled = false; b.classList.remove("busy"); }
  })));

  // ---- 최근에 만든 집: 내 계정의 집과 이 브라우저에서 만든 집만 ----
  const box = document.getElementById("projects");
  const tokens = Object.fromEntries(localHomes().map((h) => [h.pid, h.token]));
  const [mine, local] = await Promise.all([
    currentUser() ? api("/api/me/projects").catch(() => []) : [],
    Promise.all(localHomes().map((h) => api(`/api/projects/${h.pid}`).catch(() => { forgetHome(h.pid); return null; }))),
  ]);
  const seen = new Set();
  const homes = [...local.filter(Boolean), ...mine.slice().reverse()].filter((p) => !seen.has(p.project_id) && seen.add(p.project_id)).slice(0, 8);
  const render = () => {
    box.innerHTML = homes.length ? homes.map((p) => `
      <li class="proj"><a href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">
          <span class="sample-img">${homeThumb(p.project_id) ? `<img src="${homeThumb(p.project_id)}" alt="" draggable="false">` : ICON_SCAN}</span>
          <b>${esc(p.name || "우리 집")}</b></a>
        <button class="proj-del" data-del="${esc(p.project_id)}" aria-label="${esc(p.name || "우리 집")} 지우기" title="지우기"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></li>`).join("")
      : `<li class="muted">아직 없어요. 스캔 파일을 올리거나 샘플 집을 눌러 보세요.</li>`;
    box.querySelectorAll("[data-del]").forEach((b) => (b.onclick = guard(async () => {
      if (!b.classList.contains("ask")) { // 한 번 더 눌러야 지운다
        b.classList.add("ask"); b.textContent = "지울까요?";
        setTimeout(() => { if (b.isConnected) render(); }, 4000);
        return;
      }
      const pid = b.dataset.del, t = tokens[pid] || homes.find((p) => p.project_id === pid)?.share_token || "";
      await api(`/api/projects/${pid}?t=${encodeURIComponent(t)}`, { method: "DELETE" });
      forgetHome(pid);
      homes.splice(homes.findIndex((p) => p.project_id === pid), 1);
      render();
      toast("집을 지웠어요");
    })));
  };
  render();
}

// 무엇을 올렸는지에 따라 무슨 일이 일어나는지 한 줄로
const SLOT_NOTE = {
  none: "둘 중 하나만 있어도 돼요. 같이 올리면 스캔한 벽 길이를 도면 치수로 맞춰요.",
  scan: "스캔으로 집을 만들어요. 도면도 올리면 벽 길이를 도면 치수로 맞춰요.",
  plan: "도면에서 벽과 문, 창을 읽어 집을 만들어요. 가구는 비어 있어요.",
  both: "스캔으로 집을 만들고, 벽 길이를 도면 치수로 맞춰요.",
};

const ROUGH_SCALE = "도면에 치수가 없어서 방문 폭을 90cm로 보고 크기를 어림했어요";

// 도면을 올린 뒤 무슨 일이 있었는지 한 문장
export function planResult(fp) {
  if (!fp) return "도면을 첨부했어요";
  if (fp.applied) return fp.applied.walls.length ? `벽 ${fp.applied.walls.length}곳을 도면 치수로 맞췄어요` : "도면과 스캔한 벽 길이가 이미 같아요";
  return fp.note ? `도면은 붙여 뒀어요. ${fp.note}` : "도면을 첨부했어요";
}

function slotHtml(kind, icon, title, need, hint, accept) {
  return `<div class="slot" data-slot="${kind}" role="button" tabindex="0" aria-label="${title} 올리기">
    ${icon}<span class="slot-t"><b>${title}</b>${need ? `<em>${need}</em>` : ""}</span>
    <span class="slot-hint">${hint}</span>
    <span class="slot-file" hidden><span class="slot-name"></span><button class="slot-x" type="button" aria-label="${title} 빼기" title="빼기">×</button></span>
    <input type="file" id="${kind === "scan" ? "file" : "fp"}" accept="${accept}" hidden></div>`;
}

// ---------- 화면: 방문 스캔 신청 (선택) ----------
export async function home() {
  $app.innerHTML = `
    <h1>기사 방문 스캔 신청</h1>
    <p class="sub">아이폰 LiDAR가 없으면 서비스센터 기사가 방문해 스캔해 드립니다. 스캔이 끝나면 같은 가상 리모델링 화면 링크를 보내 드려요.</p>
    <div class="grid2">
      <form class="panel" id="req">
        <h2>상담 신청 <span class="badge src">시연용 목업</span></h2>
        <label>이름</label><input name="name" required maxlength="50" value="시연 고객">
        <label>연락처</label><input name="contact" required maxlength="50" value="010-0000-0000">
        <label>주소</label><input name="address" required maxlength="200" value="시연용 주소">
        <label>희망 방문 일시</label><input name="preferred_at" type="datetime-local">
        <div class="row" style="margin-top:14px"><button>신청하기</button></div>
        <p id="reqDone" class="muted"></p>
      </form>
      <div class="panel">
        <h2>진행 중인 프로젝트</h2>
        <ul class="list" id="projects"><li class="muted">불러오는 중…</li></ul>
      </div>
    </div>`;
  document.getElementById("req").onsubmit = guard(async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    if (f.preferred_at) f.preferred_at = f.preferred_at + ":00+09:00"; else delete f.preferred_at;
    const r = await post("/api/requests", f);
    document.getElementById("reqDone").innerHTML = `요청 번호 <b>${esc(r.request_id)}</b>가 접수되었습니다. 기사 방문 후 결과 링크를 보내 드립니다. <a href="#/t">기사 화면에서 스캔 등록 →</a>`;
  });
  let ps;
  try { ps = await api("/api/projects"); }
  catch (e) { document.getElementById("projects").innerHTML = `<li class="muted">목록을 못 불러왔어요: ${esc(e.message)} (서버 명령창의 오류를 확인하세요)</li>`; return; }
  document.getElementById("projects").innerHTML = ps.length ? ps.slice().reverse().map((p) => `
    <li><b>${esc(p.project_id)}</b><span class="muted">${esc(p.status)} · ${esc(p.style?.prompt || "스타일 미정")}</span><span class="spacer"></span>
      <a class="btn ghost small" href="#/t/${esc(p.project_id)}">기사</a><a class="btn small" href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">고객 결과</a></li>`).join("")
    : `<li class="muted">아직 없습니다. 기사 화면에서 스캔을 등록하세요.</li>`;
}

// ---------- 공용: 설치 전 확인 목록 ----------
const IC_STATUS = { ok: ["fit", "확인됨"], check: ["conditional", "확인 필요"], blocked: ["no_fit", "안 들어감"], site: ["src", "현장 확인"] };
export async function installCheck(el, pid) {
  let d;
  try { d = await api(`/api/projects/${pid}/install-check`); }
  catch (e) { el.innerHTML = `<p class="muted">목록을 못 불러왔어요: ${esc(e.message)}</p>`; return null; }
  const s = d.summary;
  if (!s.products) { el.innerHTML = `<p class="muted ic-empty">아직 놓은 제품이 없어요. 제품을 놓으면 설치 전에 볼 것을 여기에 정리해 드려요.</p>`; return d; }
  const sum = [`제품 ${s.products}개`, s.blocked ? `안 들어감 ${s.blocked}` : "", s.check ? `확인 필요 ${s.check}` : "", !s.blocked && !s.check ? "모두 들어가요" : "",
    s.walls_to_measure.length ? `줄자로 잴 벽 ${s.walls_to_measure.join(", ")}` : ""].filter(Boolean).join(" · ");
  el.innerHTML = `<p class="ic-sum">${esc(sum)}</p><ul class="ic-list">${d.items.map((it) => `
    <li class="ic-item"><div class="ic-head"><b>${esc(it.name)}</b><span class="badge ${IC_STATUS[it.status][0]}">${it.status === "ok" ? "들어가요" : IC_STATUS[it.status][1]}</span></div>
      <p class="muted ic-dims">${esc(it.sku)} · ${mm(it.dims_mm.w)} × ${mm(it.dims_mm.h)} × ${mm(it.dims_mm.d)} mm${it.wall_id ? ` · 벽 ${esc(it.wall_id)}` : ""}</p>
      <ul class="ic-checks">${it.checks.map((c) => `<li><span class="badge ${IC_STATUS[c.status][0]}">${IC_STATUS[c.status][1]}</span><span>${esc(c.label)}${c.detail ? ` <em class="muted">${esc(c.detail)}</em>` : ""}</span></li>`).join("")}</ul>
      ${it.source_url ? `<a class="src-link" href="${esc(it.source_url)}" target="_blank" rel="noopener">LGE.COM에서 가격 보고 구매하기 ↗</a>` : ""}</li>`).join("")}</ul>
    <p class="hint-sm">‘현장 확인’은 스캔으로 알 수 없어서 방문했을 때 보는 항목이에요.</p>`;
  return d;
}

// 놓아 본 제품 그대로 방문 설치 상담 신청 (고객 화면 "놓은 제품" 탭)
export function installRequestBox(el, pid, project, onDone) {
  if (project.install_request_id) {
    el.innerHTML = `<p class="ok-line">방문 설치 상담을 신청했어요. 신청 번호 <b>${esc(project.install_request_id)}</b></p>
      <p class="hint-sm">기사가 놓은 제품과 설치 전 확인 목록을 미리 보고 연락드려요.</p>`;
    return;
  }
  el.innerHTML = `<button class="primary" id="irOpen">이대로 방문 설치 상담 신청</button>
    <form id="irForm" hidden>
      <label>이름</label><input name="name" required maxlength="50" autocomplete="name">
      <label>연락처</label><input name="contact" required maxlength="50" inputmode="tel" autocomplete="tel">
      <label>주소</label><input name="address" required maxlength="200" autocomplete="street-address">
      <label>희망 방문 일시 <span class="muted">(선택)</span></label><input name="preferred_at" type="datetime-local">
      <p class="hint-sm">놓은 제품과 설치 전 확인 목록이 기사에게 함께 전달돼요.</p>
      <div class="row" style="margin-top:10px"><button class="primary">신청하기</button><button type="button" class="ghost" id="irCancel">닫기</button></div>
    </form>`;
  const form = el.querySelector("#irForm"), open = el.querySelector("#irOpen");
  const show = (on) => { form.hidden = !on; open.hidden = on; if (on) form.querySelector("input").focus(); };
  open.onclick = () => show(true);
  el.querySelector("#irCancel").onclick = () => show(false);
  form.onsubmit = guard(async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    if (f.preferred_at) f.preferred_at += ":00+09:00"; else delete f.preferred_at;
    const r = await post(`/api/projects/${pid}/install-request`, f);
    toast(`신청했어요 (${r.request_id})`);
    form.hidden = true;
    onDone();
  });
}

// ---------- 공용: 벽 실측 표 · 도면 ----------
export const BY = { technician: "기사", customer: "고객", floorplan: "도면" };

export function wallTable(tbody, pid, room, { by, sel, onChange }) {
  tbody.innerHTML = room.walls.map((w) => `
    <tr data-row="${w.wall_id}" ${sel === w.wall_id ? 'style="background:var(--lg-soft)"' : ""}>
      <td><b>${w.wall_id}</b>${w.measured?.by ? ` <span class="badge src">${w.measured.by === "floorplan" ? "도면 치수" : `${BY[w.measured.by] || esc(w.measured.by)} 실측`}</span>` : ""}</td>
      <td class="mono">${w.scanned.length_m.toFixed(3)}</td><td class="mono">${w.scanned.height_m.toFixed(3)}</td>
      <td><input class="mono" name="length_m" type="number" step="0.001" min="0.05" max="30" value="${w.measured?.length_m ?? ""}"></td>
      <td><input class="mono" name="height_m" type="number" step="0.001" min="0.05" max="30" value="${w.measured?.height_m ?? ""}"></td>
      <td><input class="mono" name="depth_m" type="number" step="0.001" min="0.05" max="30" value="${w.measured?.depth_m ?? ""}"></td>
      <td class="row"><button class="small" data-save="${w.wall_id}">저장</button>${w.measured ? `<button class="small ghost" data-clear="${w.wall_id}">초기화</button>` : ""}</td></tr>`).join("");
  tbody.querySelectorAll("[data-save]").forEach((b) => (b.onclick = guard(async () => {
    const body = { by };
    b.closest("tr").querySelectorAll("input").forEach((i) => { if (i.value !== "") body[i.name] = parseFloat(i.value); });
    if (Object.keys(body).length === 1) { toast("값을 하나 이상 넣어 주세요", true); return; }
    await put(`/api/projects/${pid}/walls/${b.dataset.save}/measured`, body);
    toast(`${b.dataset.save} 실측값 저장`);
    onChange();
  })));
  tbody.querySelectorAll("[data-clear]").forEach((b) => (b.onclick = guard(async () => {
    await api(`/api/projects/${pid}/walls/${b.dataset.clear}/measured`, { method: "DELETE" });
    onChange();
  })));
}

export const WALL_HEAD = `<thead><tr><th>벽</th><th>스캔 길이</th><th>스캔 높이</th><th>실측 길이 (m)</th><th>실측 높이 (m)</th><th>벽 앞 깊이 (m)</th><th></th></tr></thead>`;

export async function uploadFloorplan(pid, f) {
  const fd = new FormData();
  fd.append("file", f, f.name);
  return api(`/api/projects/${pid}/floorplan`, { method: "POST", body: fd });
}

export function floorplanBox(el, pid, project, onChange) {
  const fp = project.floorplan;
  const url = apiUrl(`/api/projects/${pid}/files/floorplan?v=${encodeURIComponent(fp?.uploaded_at || "")}`);
  el.innerHTML = fp ? `
      <div class="row"><b>${esc(fp.name)}</b><span class="spacer"></span>
        <a class="btn ghost small" href="${url}" target="_blank" rel="noopener">크게 보기</a><button class="small ghost" id="fpDel">삭제</button></div>
      ${project.scan?.source === "floorplan_image" ? `<p class="hint-sm">이 도면을 읽어서 만든 집이에요.${project.scan.scale_from === "door_width" ? ` ${ROUGH_SCALE}.` : ""}</p>` : fp.applied || fp.note ? `<p class="hint-sm">${esc(planResult(fp))}</p>` : ""}
      ${fp.content_type.startsWith("image/") ? `<img class="floorplan" src="${url}" alt="도면">` : `<p class="muted">PDF 도면이 첨부되어 있습니다.</p>`}`
    : `<label class="drop" style="display:block;cursor:pointer">도면 이미지·PDF 올리기<input type="file" id="fpFile" accept=".png,.jpg,.jpeg,.webp,.pdf" hidden></label>`;
  const input = el.querySelector("#fpFile");
  if (input) input.onchange = guard(async () => { if (input.files[0]) {
    el.querySelector(".drop").firstChild.textContent = "도면을 읽는 중… 2분쯤 걸려요";
    const done = await uploadFloorplan(pid, input.files[0]);
    toast(planResult(done.floorplan), !!done.floorplan?.note); onChange();
  } });
  const del = el.querySelector("#fpDel");
  if (del) del.onclick = guard(async () => { await api(`/api/projects/${pid}/floorplan`, { method: "DELETE" }); onChange(); });
}

// ---------- 화면: 기사 ----------
export async function technicianHome() {
  const reqs = await api("/api/requests");
  $app.innerHTML = `
    <h1>기사 화면 · 스캔 등록</h1>
    <p class="sub">UGScan RoomPlan 모드로 내보낸 USDZ 파일을 올리면 3D 공간과 벽 치수가 만들어집니다.</p>
    <div class="panel" style="max-width:640px">
      <label>상담 요청</label>
      <select id="rid"><option value="">(요청 없이 등록)</option>${reqs.map((r) => `<option value="${esc(r.request_id)}">${esc(r.request_id)} · ${esc(r.customer.name)} · ${esc(r.status)}</option>`).join("")}</select>
      <label>스캔 주체</label>
      <select id="by"><option value="technician">서비스센터 기사</option><option value="customer">고객 셀프 스캔 (L1)</option></select>
      <label>USDZ 파일</label>
      <div class="drop" id="drop">파일을 끌어다 놓거나 <u>선택</u>하세요<input type="file" id="file" accept=".usdz,.usd,.usda,.usdc" hidden></div>
      <label>도면 (선택) — 같이 올리면 스캔한 벽 길이를 도면 치수로 맞춥니다</label>
      <input type="file" id="fp" accept=".png,.jpg,.jpeg,.webp,.pdf">
      <div class="row" style="margin-top:12px">
        <a class="muted" href="${apiUrl("/api/samples/synthetic_room.usdz")}">합성 샘플 USDZ 받기</a>
        <span class="spacer"></span>
        <button class="ghost" id="useSample">합성 샘플로 등록</button>
      </div>
    </div>`;
  const drop = document.getElementById("drop"), file = document.getElementById("file");
  const send = guard(async (blob, name) => {
    drop.textContent = "변환 중… (USDZ → room.json → 3D)";
    const fd = new FormData();
    fd.append("file", blob, name);
    fd.append("request_id", document.getElementById("rid").value);
    fd.append("scanned_by", document.getElementById("by").value);
    try {
      const p = await api("/api/projects", { method: "POST", body: fd });
      const fp = document.getElementById("fp").files[0];
      if (fp) await uploadFloorplan(p.project_id, fp);
      toast(`${p.project_id} 생성 완료`);
      location.hash = `#/t/${p.project_id}`;
    } catch (e) { drop.textContent = "다시 시도하세요"; throw e; }
  });
  drop.onclick = () => file.click();
  document.getElementById("pick")?.addEventListener("click", () => file.click());
  file.onchange = () => file.files[0] && send(file.files[0], file.files[0].name);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) send(f, f.name); };
  document.getElementById("useSample").onclick = guard(async () => {
    const b = await (await fetch(apiUrl("/api/samples/synthetic_room.usdz"))).blob();
    send(b, "synthetic_room.usdz");
  });
  // 고객이 놓아 본 제품으로 넣은 방문 설치 신청: 눌러서 그 집의 설치 전 확인으로 간다
  const installs = reqs.filter((r) => r.kind === "install").reverse();
  if (installs.length) $app.insertAdjacentHTML("beforeend", `
    <div class="panel" style="max-width:640px;margin-top:16px"><h2>방문 설치 신청</h2>
      <ul class="list">${installs.map((r) => `<li><a class="proj" href="#/t/${esc(r.project_id)}"><b>${esc(r.request_id)} · ${esc(r.customer.name)}</b>
        <span class="muted">제품 ${r.summary.products}개${r.summary.blocked ? ` · 안 들어감 ${r.summary.blocked}` : ""}${r.summary.check ? ` · 확인 필요 ${r.summary.check}` : ""}${r.preferred_at ? ` · 희망 ${esc(r.preferred_at.slice(0, 16).replace("T", " "))}` : ""}</span></a></li>`).join("")}</ul></div>`);
}

export async function technician(pid) {
  $app.innerHTML = `
    <div class="row"><div><h1>기사 화면 · ${esc(pid)}</h1><p class="sub" id="sub"></p></div><span class="spacer"></span>
      <button class="ghost" id="copy">고객 링크 복사</button><a class="btn" id="open">고객 화면 열기</a></div>
    <div class="grid2">
      <div class="panel"><h2>평면도</h2><svg class="plan" id="plan"></svg>
        <p class="muted" style="font-size:12px;margin:6px 0 0">초록 벽 = 실측 입력됨. 벽을 누르면 아래 표에서 선택됩니다.</p></div>
      <div class="panel"><h2>3D</h2><div class="viewer" id="viewer"><span class="hud" id="hud"></span></div></div>
    </div>
    <div class="panel" style="margin-top:16px"><h2>설치 전 확인</h2><div id="icBox"></div></div>
    <div class="panel" style="margin-top:16px">
      <h2>벽 치수 · 실측 보정 <span class="badge src">선택</span></h2>
      <div class="notice">스캔값만으로도 판정합니다 (스캔 오차 여유 30 mm). 줄자로 잰 값이 있으면 넣어 주세요. 여유 5 mm로 더 촘촘하게 판정하고, 원래 스캔값은 보존됩니다.</div>
      <table>${WALL_HEAD}<tbody id="walls"></tbody></table>
    </div>
    <div class="panel" style="margin-top:16px"><h2>도면 <span class="badge src">선택</span></h2><div id="fpBox"></div></div>`;
  const viewer = makeViewer(document.getElementById("viewer"));
  cleanup.push(() => viewer.dispose());
  let sel = null;
  const load = async () => {
    const [p, room] = await Promise.all([api(`/api/projects/${pid}`), api(`/api/projects/${pid}/room`)]);
    document.getElementById("sub").textContent = `${p.scan.scanned_by === "customer" ? "고객 셀프 스캔" : "기사 스캔"} · 벽 ${room.walls.length} · 문·창 ${room.openings.length} · 가구 ${room.objects.length} · 3D ${p.scene.engine === "blender" ? "Blender" : "치수 박스 미리보기"}`;
    document.getElementById("open").href = `#/c/${pid}?t=${p.share_token}`;
    document.getElementById("copy").onclick = () => navigator.clipboard.writeText(p.customer_url).then(() => toast("고객 링크를 복사했습니다"));
    const svg = document.getElementById("plan");
    planView(svg, room, { selectedWall: sel });
    svg.onclick = (e) => { const w = e.target.dataset?.wall; if (w) { sel = w; load(); document.querySelector(`[data-row="${w}"] input`)?.focus(); } };
    wallTable(document.getElementById("walls"), pid, room, { by: "technician", sel, onChange: load });
    floorplanBox(document.getElementById("fpBox"), pid, p, load);
    installCheck(document.getElementById("icBox"), pid);
    viewer.load(apiUrl(`/api/projects/${pid}/files/scene.glb`));
    document.getElementById("hud").textContent = "드래그 회전 · 휠 확대";
  };
  await guard(load)();
}
