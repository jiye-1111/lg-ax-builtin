// 화면: 내 집 스캔(첫 화면), 방문 스캔 신청, 기사 화면
import { $app, cleanup, esc, api, post, toast, guard } from "./core.js";
import { makeViewer } from "./viewer.js";
import { planView } from "./plan.js";

export async function selfScan() {
  $app.innerHTML = `
    <section class="hero">
      <div class="hero-copy">
        <h1>스캔한 우리 집에<br>LG 빌트인을 놓아 보세요</h1>
        <p class="lede">아이폰 LiDAR로 찍은 집이 그대로 3D 평면이 됩니다. 냉장고·식기세척기를 원하는 자리에 놓으면
          들어가는지, 문이 열리는지 바로 판정하고, 볕 드는 시간과 와이파이, 다니는 길까지 함께 보여 줍니다.</p>
        <ol class="steps">
          <li><b>스캔</b><span>UGScan 앱 RoomPlan 모드로 방을 천천히 한 바퀴 찍어요.</span></li>
          <li><b>올리기</b><span>USDZ로 내보낸 파일을 파일 칸에 올려요. 도면은 있으면 함께.</span></li>
          <li><b>놓아 보기</b><span>제품을 고르고 평면을 눌러 자리를 잡아요.</span></li>
        </ol>
      </div>
      <div class="hero-stage">
        ${heroPlan()}
        <div class="upload">
          <div class="drop big" id="drop" role="button" tabindex="0" aria-label="USDZ 파일 선택">
            <b>USDZ 파일을 끌어다 놓거나 눌러서 선택</b><span class="muted">UGScan · RoomPlan 내보내기</span>
            <input type="file" id="file" accept=".usdz,.usd,.usda,.usdc" hidden></div>
          <label class="fp-pick"><span>도면 함께 올리기 <em>선택</em></span><input type="file" id="fp" accept=".png,.jpg,.jpeg,.webp,.pdf"></label>
          <div class="row upload-foot"><button class="primary" id="sample">샘플 집으로 체험하기</button>
            <span class="spacer"></span><a class="quiet" href="#/r">스캔이 어렵다면 기사 방문 신청</a></div>
        </div>
      </div>
    </section>
    <section class="recent" aria-labelledby="recentH">
      <h2 id="recentH">최근에 만든 집</h2>
      <ul class="list" id="projects"><li class="muted">불러오는 중…</li></ul>
    </section>`;
  const drop = document.getElementById("drop"), file = document.getElementById("file");
  const send = guard(async (blob, name) => {
    drop.innerHTML = "<b>집을 3D로 만드는 중…</b><br><span class='muted'>벽·문·창·가구를 읽고 있어요</span>";
    const fd = new FormData();
    fd.append("file", blob, name);
    fd.append("scanned_by", "customer");
    try {
      const p = await api("/api/projects", { method: "POST", body: fd });
      const fp = document.getElementById("fp").files[0];
      if (fp) await uploadFloorplan(p.project_id, fp);
      location.hash = `#/c/${p.project_id}?t=${p.share_token}`;
    } catch (e) { drop.innerHTML = "<b>다시 시도해 주세요</b><br><span class='muted'>USDZ 파일인지 확인해 주세요</span>"; throw e; }
  });
  drop.onclick = () => file.click();
  drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } };
  file.onchange = () => file.files[0] && send(file.files[0], file.files[0].name);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) send(f, f.name); };
  document.getElementById("sample").onclick = guard(async () => {
    const b = await (await fetch("/api/samples/ugscan_2026-11-18.usdz")).blob();
    send(b, "ugscan_2026-11-18.usdz");
  });
  const ps = await api("/api/projects");
  document.getElementById("projects").innerHTML = ps.length ? ps.slice().reverse().slice(0, 6).map((p) => `
    <li><a class="proj" href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">
      <b>${esc(p.project_id)}</b>
      <span class="muted">${p.scan.scanned_by === "customer" ? "셀프 스캔" : "기사 스캔"}</span>
      <span class="muted">제품 ${p.scene_state.placements.length}개</span>
      <span class="go">열기</span></a></li>`).join("")
    : `<li class="muted">아직 없어요. 샘플 집으로 먼저 체험해 보세요.</li>`;
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
  const ps = await api("/api/projects");
  document.getElementById("projects").innerHTML = ps.length ? ps.slice().reverse().map((p) => `
    <li><b>${esc(p.project_id)}</b><span class="muted">${esc(p.status)} · ${esc(p.style?.prompt || "스타일 미정")}</span><span class="spacer"></span>
      <a class="btn ghost small" href="#/t/${esc(p.project_id)}">기사</a><a class="btn small" href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">고객 결과</a></li>`).join("")
    : `<li class="muted">아직 없습니다. 기사 화면에서 스캔을 등록하세요.</li>`;
}

// ---------- 공용: 벽 실측 표 · 도면 ----------
export const BY = { technician: "기사", customer: "고객" };

export function wallTable(tbody, pid, room, { by, sel, onChange }) {
  tbody.innerHTML = room.walls.map((w) => `
    <tr data-row="${w.wall_id}" ${sel === w.wall_id ? 'style="background:var(--lg-soft)"' : ""}>
      <td><b>${w.wall_id}</b>${w.measured?.by ? ` <span class="badge src">${BY[w.measured.by] || esc(w.measured.by)} 실측</span>` : ""}</td>
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
  const url = `/api/projects/${pid}/files/floorplan?v=${encodeURIComponent(fp?.uploaded_at || "")}`;
  el.innerHTML = fp ? `
      <div class="row"><b>${esc(fp.name)}</b><span class="spacer"></span>
        <a class="btn ghost small" href="${url}" target="_blank" rel="noopener">크게 보기</a><button class="small ghost" id="fpDel">삭제</button></div>
      ${fp.content_type.startsWith("image/") ? `<img class="floorplan" src="${url}" alt="도면">` : `<p class="muted">PDF 도면이 첨부되어 있습니다.</p>`}`
    : `<label class="drop" style="display:block;cursor:pointer">도면 이미지·PDF 선택 (선택 사항)<input type="file" id="fpFile" accept=".png,.jpg,.jpeg,.webp,.pdf" hidden></label>`;
  const input = el.querySelector("#fpFile");
  if (input) input.onchange = guard(async () => { if (input.files[0]) { await uploadFloorplan(pid, input.files[0]); toast("도면을 첨부했습니다"); onChange(); } });
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
      <label>도면 (선택) — 있으면 함께 첨부, 판정에는 쓰지 않고 참고용으로 보여 줍니다</label>
      <input type="file" id="fp" accept=".png,.jpg,.jpeg,.webp,.pdf">
      <div class="row" style="margin-top:12px">
        <a class="muted" href="/api/samples/synthetic_room.usdz">합성 샘플 USDZ 받기</a>
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
  file.onchange = () => file.files[0] && send(file.files[0], file.files[0].name);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) send(f, f.name); };
  document.getElementById("useSample").onclick = guard(async () => {
    const b = await (await fetch("/api/samples/synthetic_room.usdz")).blob();
    send(b, "synthetic_room.usdz");
  });
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
    viewer.load(`/api/projects/${pid}/files/scene.glb`);
    document.getElementById("hud").textContent = "드래그 회전 · 휠 확대";
  };
  await guard(load)();
}

// 첫 화면 그림: 스캔 평면 위에 제품을 놓는 장면 (치수선 포함)
function heroPlan() {
  return `<svg class="hero-plan" viewBox="0 0 520 380" role="img" aria-label="스캔한 평면에 냉장고를 놓은 예시">
    <defs><pattern id="hg" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="var(--grid)" stroke-width="1"/></pattern></defs>
    <rect width="520" height="380" fill="url(#hg)"/>
    <path class="hp-wall" d="M60 60 H460 V250 H300 V330 H60 Z"/>
    <path class="hp-window" d="M150 60 H270"/><path class="hp-door" d="M300 290 V330"/>
    <path class="hp-swing" d="M300 290 A40 40 0 0 1 340 330"/>
    <rect class="hp-obj" x="330" y="150" width="90" height="60" rx="3"/>
    <rect class="hp-fit" x="72" y="72" width="70" height="66" rx="3"/>
    <path class="hp-front" d="M72 138 H142"/>
    <rect class="hp-ghost" x="152" y="72" width="60" height="62" rx="3"/>
    <path class="hp-dim" d="M72 50 H142 M72 44 V56 M142 44 V56"/>
    <text class="hp-label" x="107" y="40" text-anchor="middle">제품 폭</text>
    <text class="hp-tag" x="80" y="160">적합</text>
  </svg>`;
}
