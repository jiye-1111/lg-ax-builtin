// 빌트인 공간 설계 — 시연용 웹 (빌드 없음). 화면: 상담 요청(#/), 기사(#/t/:pid), 고객(#/c/:pid)
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $app = document.getElementById("app");
const LABEL = { fit: "적합", conditional: "조건부", no_fit: "불가", unknown: "판정 불가" };
const PURPOSE = { kitchen: "주방", living: "거실", bedroom: "침실", utility: "다용도실", other: "기타" };
const CATEGORY = {
  refrigerator: "냉장고", kimchi_refrigerator: "김치냉장고", dishwasher: "식기세척기", oven: "오븐",
  cooktop: "쿡탑", water_purifier: "정수기", air_conditioner: "에어컨", styler: "의류관리기", washer: "세탁기",
};
const DIM = { width: "폭", height: "높이", depth: "깊이" };
const OBJ = { chair: "의자", table: "테이블", storage: "수납장", sofa: "소파", bed: "침대", refrigerator: "냉장고", stove: "레인지",
  sink: "싱크", washer_dryer: "세탁기", oven: "오븐", dishwasher: "식기세척기", television: "TV", toilet: "변기", bathtub: "욕조", fireplace: "벽난로", stairs: "계단" };
const VCOLOR = { fit: "var(--fit)", conditional: "var(--cond)", no_fit: "var(--nofit)", unknown: "var(--unk)" };
const NOTE = { clearance_unknown: "이격 정보 없음", scan_based: "스캔값 사용(실측 필요)", no_wall_in_zone: "영역에 벽 없음" };

// ---------- 공통 ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const mm = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString()}`);
async function api(path, opt = {}) {
  const r = await fetch(path, {
    ...opt,
    headers: opt.body && !(opt.body instanceof FormData) ? { "content-type": "application/json", ...(opt.headers || {}) } : opt.headers,
  });
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText);
  return data;
}
const post = (p, b) => api(p, { method: "POST", body: JSON.stringify(b) });
const put = (p, b) => api(p, { method: "PUT", body: JSON.stringify(b) });
let toastT;
function toast(msg, err = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "on" + (err ? " err" : "");
  clearTimeout(toastT);
  toastT = setTimeout(() => (t.className = ""), 2800);
}
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };

// ---------- 라우터 ----------
let cleanup = [];
function route() {
  cleanup.forEach((f) => f());
  cleanup = [];
  const [path] = location.hash.slice(1).split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "t") return parts[1] ? technician(parts[1]) : technicianHome();
  if (parts[0] === "c" && parts[1]) return customer(parts[1]);
  if (parts[0] === "r") return home();
  return selfScan();
}
window.addEventListener("hashchange", route);

// ---------- 3D 뷰어 ----------
function makeViewer(el) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#eceae5");
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8b2a8, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(-4, 8, 6);
  scene.add(sun);
  const cam = new THREE.PerspectiveCamera(45, 1, 0.05, 200);
  const ctl = new OrbitControls(cam, renderer.domElement);
  ctl.enableDamping = true;
  let model = null, framed = false, alive = true, walls = [], center = new THREE.Vector3();
  const tmp = new THREE.Vector3(), toCam = new THREE.Vector3();
  // 카메라 쪽 벽은 반투명으로 (돌하우스 컷어웨이)
  const cutaway = () => {
    toCam.copy(cam.position).sub(center).setY(0).normalize();
    for (const w of walls) {
      w.getWorldPosition(tmp);
      const front = tmp.sub(center).setY(0).normalize().dot(toCam) > 0.35;
      w.material.opacity = front ? 0.12 : 1;
      w.material.transparent = front;
      w.material.depthWrite = !front;
    }
  };
  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    renderer.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(el);
  resize();
  (function loop() {
    if (!alive) return;
    ctl.update();
    cutaway();
    renderer.render(scene, cam);
    requestAnimationFrame(loop);
  })();
  const loader = new GLTFLoader();
  return {
    load(url) {
      loader.load(url + (url.includes("?") ? "&" : "?") + "v=" + Date.now(), (g) => {
        if (model) scene.remove(model);
        model = g.scene;
        walls = [];
        model.traverse((o) => {
          if (o.isMesh) o.material = o.material.clone();
          const kind = o.userData?.kind ?? o.parent?.userData?.kind;
          if (o.isMesh && (kind === "wall" || kind === "door" || kind === "window")) walls.push(o);
        });
        scene.add(model);
        new THREE.Box3().setFromObject(model).getCenter(center);
        if (!framed) {
          const box = new THREE.Box3().setFromObject(model);
          const c = box.getCenter(new THREE.Vector3());
          const s = box.getSize(new THREE.Vector3()).length();
          cam.position.set(c.x - s * 0.35, c.y + s * 1.05, c.z + s * 0.55);
          ctl.target.copy(c);
          framed = true;
        }
      }, undefined, () => toast("3D 파일을 불러오지 못했습니다", true));
    },
    dispose() { alive = false; ro.disconnect(); renderer.dispose(); el.innerHTML = ""; },
  };
}

// ---------- 평면도 (SVG) ----------
function planView(svg, room, opts = {}) {
  const pts = room.walls.flatMap((w) => [w.start, w.end]);
  const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
  const pad = 0.5;
  svg.setAttribute("viewBox", `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`);
  const k = (maxX - minX + 2 * pad) / 600; // 화면 1px ≈ k m
  const sw = (px) => px * k;
  const wallLen = (w) => (w.measured?.length_m ?? w.scanned.length_m);
  let html = "";
  for (const z of opts.zones || []) {
    const cls = z.purpose in { kitchen: 1, living: 1 } ? z.purpose : "other";
    const c = z.polygon_m.reduce((a, p) => [a[0] + p[0] / z.polygon_m.length, a[1] + p[1] / z.polygon_m.length], [0, 0]);
    html += `<polygon class="zone ${cls}" data-zone="${esc(z.zone_id)}" points="${z.polygon_m.map((p) => p.join(",")).join(" ")}" style="stroke-width:${sw(2)}px"/>`;
    html += `<text x="${c[0]}" y="${c[1]}" text-anchor="middle" style="font-size:${sw(13)}px;font-weight:700">${esc(z.name || PURPOSE[z.purpose] || z.purpose)}</text>`;
  }
  html += `<g id="overlay">${opts.overlay || ""}</g>`;
  const hidden = new Set(opts.hidden || []);
  for (const o of room.objects) {
    const [x, , zz] = o.position;
    const deg = (o.yaw_rad * 180) / Math.PI;
    const cls = `obj${hidden.has(o.object_id) ? " gone" : ""}${opts.selectedObj === o.object_id ? " sel" : ""}`;
    html += `<rect class="${cls}" data-obj="${esc(o.object_id)}" x="${x - o.bbox_m.w / 2}" y="${zz - o.bbox_m.d / 2}" width="${o.bbox_m.w}" height="${o.bbox_m.d}" transform="rotate(${deg} ${x} ${zz})" stroke-width="${sw(1)}"/>`;
    if (!hidden.has(o.object_id)) html += `<text x="${x}" y="${zz}" text-anchor="middle" dominant-baseline="middle" style="font-size:${sw(10)}px;pointer-events:none" fill="#6b6f76">${esc(OBJ[o.category] || o.category)}</text>`;
  }
  for (const w of room.walls) {
    const sel = opts.selectedWall === w.wall_id ? " sel" : "";
    html += `<line class="wall${w.measured ? " measured" : ""}${sel}" data-wall="${w.wall_id}" x1="${w.start[0]}" y1="${w.start[1]}" x2="${w.end[0]}" y2="${w.end[1]}" style="stroke-width:${sw(6)}px;cursor:pointer"/>`;
    const mx = (w.start[0] + w.end[0]) / 2, my = (w.start[1] + w.end[1]) / 2;
    const dx = w.end[0] - w.start[0], dy = w.end[1] - w.start[1], L = Math.hypot(dx, dy) || 1;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    let nx = -dy / L, ny = dx / L;
    if ((mx + nx - cx) ** 2 + (my + ny - cy) ** 2 < (mx - cx) ** 2 + (my - cy) ** 2) { nx = -nx; ny = -ny; }
    html += `<text x="${mx + nx * sw(22)}" y="${my + ny * sw(22)}" text-anchor="middle" dominant-baseline="middle" style="font-size:${sw(11)}px">${w.wall_id} ${wallLen(w).toFixed(3)}m</text>`;
  }
  const walls = Object.fromEntries(room.walls.map((w) => [w.wall_id, w]));
  for (const o of room.openings) {
    const w = walls[o.wall_id];
    if (!w) continue;
    const dx = w.end[0] - w.start[0], dy = w.end[1] - w.start[1], L = Math.hypot(dx, dy) || 1;
    const a = o.offset_m / L, b = (o.offset_m + o.width_m) / L;
    html += `<line class="${o.type === "window" ? "window" : "door"}" x1="${w.start[0] + dx * a}" y1="${w.start[1] + dy * a}" x2="${w.start[0] + dx * b}" y2="${w.start[1] + dy * b}" style="stroke-width:${sw(8)}px"/>`;
  }
  for (const p of opts.placements || []) html += placedSvg(p, sw, opts.selectedPl === p.placement_id);
  if (opts.northDeg != null) {  // 나침반: 평면도 오른쪽 위
    const r = sw(18), cx = maxX + pad - sw(26), cy = minY - pad + sw(26);
    html += `<g class="compass" transform="rotate(${opts.northDeg} ${cx} ${cy})"><circle cx="${cx}" cy="${cy}" r="${r}" style="stroke-width:${sw(1)}px"/>
      <path d="M ${cx} ${cy - r * 0.85} L ${cx + r * 0.32} ${cy + r * 0.2} L ${cx} ${cy} L ${cx - r * 0.32} ${cy + r * 0.2} Z"/>
      <text x="${cx}" y="${cy - r - sw(4)}" text-anchor="middle" style="font-size:${sw(11)}px;font-weight:700">N</text></g>`;
  }
  html += `<g id="ghost"></g><g id="draft"></g>`;
  svg.innerHTML = html;
  const toWorld = (ev) => {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const snap = (v) => Math.round(v / 0.05) * 0.05;
    return [snap(p.x), snap(p.y)];
  };
  return { toWorld, sw };
}

// 배치 제품 사각형 (yaw = 정면 방향, 폭 축 = yaw - 90°). 정면 쪽 변에 굵은 선
function placedSvg(p, sw, selected = false, ghost = false) {
  const [w_, , d_] = p.size_m;
  const deg = ((p.yaw_rad - Math.PI / 2) * 180) / Math.PI;
  const [x, y] = p.center_xz;
  const v = p.verdict || "unknown";
  return `<g class="placed v-${v}${selected ? " sel" : ""}${ghost ? " ghost" : ""}" ${p.placement_id ? `data-pl="${esc(p.placement_id)}"` : ""} transform="rotate(${deg} ${x} ${y})">
    <rect x="${x - w_ / 2}" y="${y - d_ / 2}" width="${w_}" height="${d_}" style="fill:${esc(p.hex || "#fff")};stroke-width:${sw(selected ? 3 : 2)}px"/>
    <line x1="${x - w_ / 2}" y1="${y + d_ / 2}" x2="${x + w_ / 2}" y2="${y + d_ / 2}" class="front" style="stroke-width:${sw(4)}px"/></g>`;
}

// ---------- 화면: 내 집 스캔 (기본) ----------
async function selfScan() {
  $app.innerHTML = `
    <section class="hero">
      <div>
        <h1>우리 집을 스캔하고,<br>LG 제품을 미리 놓아 보세요</h1>
        <p class="sub">아이폰 LiDAR로 찍은 집을 3D로 띄워 냉장고·식기세척기 같은 빌트인 가전을 원하는 자리에 놓아 봅니다.
          들어가는지, 문은 열리는지, 색은 어울리는지 바로 확인할 수 있어요.</p>
        <ol class="steps">
          <li><b>UGScan</b> 앱에서 <b>RoomPlan</b> 모드로 방을 천천히 한 바퀴 찍습니다.</li>
          <li>내보내기 → <b>USDZ</b>로 저장합니다.</li>
          <li>아래에 파일을 올리면 끝. 도면은 있으면 함께 넣어도 됩니다.</li>
        </ol>
      </div>
      <div class="panel upload">
        <div class="drop big" id="drop"><b>USDZ 파일을 끌어다 놓거나 눌러서 선택</b><br><span class="muted">UGScan · RoomPlan 내보내기</span>
          <input type="file" id="file" accept=".usdz,.usd,.usda,.usdc" hidden></div>
        <label>도면 (선택) — 참고용으로 함께 보여 줍니다</label>
        <input type="file" id="fp" accept=".png,.jpg,.jpeg,.webp,.pdf">
        <div class="row" style="margin-top:14px"><button class="ghost" id="sample">샘플 집으로 체험하기</button>
          <span class="spacer"></span><a class="muted" href="#/r">기사 방문 스캔 신청 →</a></div>
      </div>
    </section>
    <div class="panel" style="margin-top:20px"><h2>최근 프로젝트</h2><ul class="list" id="projects"><li class="muted">불러오는 중…</li></ul></div>`;
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
  file.onchange = () => file.files[0] && send(file.files[0], file.files[0].name);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) send(f, f.name); };
  document.getElementById("sample").onclick = guard(async () => {
    const b = await (await fetch("/api/samples/ugscan_2026-11-18.usdz")).blob();
    send(b, "ugscan_2026-11-18.usdz");
  });
  const ps = await api("/api/projects");
  document.getElementById("projects").innerHTML = ps.length ? ps.slice().reverse().slice(0, 8).map((p) => `
    <li><b>${esc(p.project_id)}</b><span class="muted">${p.scan.scanned_by === "customer" ? "셀프 스캔" : "기사 스캔"} · 놓은 제품 ${p.scene_state.placements.length}개</span><span class="spacer"></span>
      <a class="btn small" href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">열기</a></li>`).join("")
    : `<li class="muted">아직 없습니다.</li>`;
}

// ---------- 화면: 방문 스캔 신청 (선택) ----------
async function home() {
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
const BY = { technician: "기사", customer: "고객" };

function wallTable(tbody, pid, room, { by, sel, onChange }) {
  tbody.innerHTML = room.walls.map((w) => `
    <tr data-row="${w.wall_id}" ${sel === w.wall_id ? 'style="background:var(--accent-soft)"' : ""}>
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

const WALL_HEAD = `<thead><tr><th>벽</th><th>스캔 길이</th><th>스캔 높이</th><th>실측 길이 (m)</th><th>실측 높이 (m)</th><th>벽 앞 깊이 (m)</th><th></th></tr></thead>`;

async function uploadFloorplan(pid, f) {
  const fd = new FormData();
  fd.append("file", f, f.name);
  return api(`/api/projects/${pid}/floorplan`, { method: "POST", body: fd });
}

function floorplanBox(el, pid, project, onChange) {
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
async function technicianHome() {
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

async function technician(pid) {
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

// ---------- 화면: 고객 (가상 리모델링) ----------
async function customer(pid) {
  $app.innerHTML = `
    <div class="row"><div><h1>우리 집 가상 리모델링</h1><p class="sub" id="sub">불러오는 중…</p></div></div>
    <div class="remodel">
      <div class="panel lib">
        <h2>1. LG 제품 고르기</h2>
        <div class="chips" id="cats"></div>
        <input id="q" placeholder="제품 이름·모델명 검색" style="margin-top:8px">
        <ul class="list" id="lib" style="margin-top:6px"></ul>
        <p class="muted" style="font-size:12px;margin:8px 0 0">제품을 누른 뒤 평면도를 누르거나, 평면도로 끌어다 놓으세요. 벽 가까이 놓으면 등이 벽에 붙습니다.</p>
      </div>
      <div>
        <div class="panel">
          <div class="row"><h2 style="margin:0">2. 우리 집에 놓아 보기</h2><span class="spacer"></span>
            <div class="tabs" style="margin:0"><button data-mode="move" class="on">놓기·옮기기</button><button data-mode="rect">영역 □</button><button data-mode="poly">영역 ⬠</button></div></div>
          <svg class="plan big" id="plan" style="margin-top:10px"></svg>
          <p class="muted" style="font-size:12px;margin:6px 0 0" id="hint"></p>
          <div class="simbar"><b>살아 보기</b>
            <div class="tabs" style="margin:0"><button data-sim="" class="on">끄기</button><button data-sim="daylight">☀ 채광</button><button data-sim="wifi">📶 와이파이</button><button data-sim="flow">🚶 동선</button></div></div>
          <div id="simctl"></div>
        </div>
        <div class="panel" style="margin-top:16px"><div class="row"><h2 style="margin:0">3. 3D로 보기</h2><span class="spacer"></span><button class="ghost small" id="render">렌더 이미지</button></div>
          <div class="viewer" id="viewer" style="margin-top:10px"><span class="hud" id="hud"></span></div>
          <img id="renderImg" alt="렌더 결과" style="display:none;width:100%;margin-top:10px;border-radius:10px"></div>
      </div>
      <div>
        <div class="panel" id="insp"></div>
        <div class="panel" style="margin-top:16px"><h2>놓은 제품</h2><ul class="list" id="pls"></ul></div>
        <div class="panel" style="margin-top:16px"><h2>4. 색·재질</h2><div id="style"></div><div id="mats" style="margin-top:10px"></div></div>
        <details class="panel" style="margin-top:16px">
          <summary><b>영역별 추천</b> <span class="muted">영역을 그리면 들어가는 제품을 골라 줍니다</span></summary>
          <ul class="list" id="zones" style="margin-top:8px"></ul>
          <select id="zoneSel" style="margin-top:8px"></select>
          <div id="recs" class="cards" style="margin-top:10px"></div>
        </details>
      </div>
    </div>
    <details class="panel" id="extra" style="margin-top:16px">
      <summary><b>도면 · 실측값 넣기</b> <span class="badge src">선택</span> <span class="muted">스캔만으로도 됩니다. 도면이나 줄자로 잰 값이 있으면 더 정확해져요.</span></summary>
      <div class="grid2" style="margin-top:12px">
        <div><h3>도면</h3><div id="fpBox"></div></div>
        <div><h3>벽 실측값</h3><p class="muted" style="font-size:12px;margin:0 0 6px">평면도의 벽 번호를 보고, 잰 값만 넣으면 됩니다 (m).</p>
          <div style="overflow-x:auto"><table>${WALL_HEAD}<tbody id="walls"></tbody></table></div></div>
      </div>
    </details>`;
  const viewer = makeViewer(document.getElementById("viewer"));
  cleanup.push(() => viewer.dispose());
  const svg = document.getElementById("plan");
  let mode = "move", draft = [], dragging = null, version = -1, zoneSel = null, project, room, zones, pv;
  let armed = null, selPl = null, selObj = null, drag = null, cat = "", catalog = [];
  let sim = "", overlay = "", simState = { date: new Date().toISOString().slice(0, 10), time: "12:00" }, regions = null;
  const prodOf = (sku) => catalog.find((p) => p.sku === sku);
  const HINT = {
    move: "제품을 끌어서 옮기세요. 선택 후 R 키 또는 오른쪽 버튼으로 돌릴 수 있습니다. 기존 가구를 누르면 치울 수 있어요.",
    rect: "평면도에서 드래그해 영역을 그리세요 (5cm 단위).",
    poly: "꼭짓점을 차례로 누르고, 첫 점을 다시 누르거나 더블클릭하면 완성됩니다.",
  };
  const setHint = () => {
    document.getElementById("hint").innerHTML = armed ? `<b>${esc(prodOf(armed)?.name || armed)}</b> 놓을 자리를 누르세요 · <a href="#" id="unarm">취소</a>` : HINT[mode];
    const u = document.getElementById("unarm");
    if (u) u.onclick = (e) => { e.preventDefault(); armed = null; ghost(null); setHint(); renderLib(); };
  };

  // ---- 제품 서랍 ----
  catalog = await api("/api/catalog");
  const cats = [...new Set(catalog.map((p) => p.category))];
  const renderCats = () => {
    document.getElementById("cats").innerHTML = [["", "전체"], ...cats.map((c) => [c, CATEGORY[c] || c])]
      .map(([k, v]) => `<button class="chip ${cat === k ? "on" : ""}" data-cat="${esc(k)}">${esc(v)}</button>`).join("");
    document.querySelectorAll("[data-cat]").forEach((b) => (b.onclick = () => { cat = b.dataset.cat; renderCats(); renderLib(); }));
  };
  const renderLib = () => {
    const q = document.getElementById("q").value.trim().toLowerCase();
    const items = catalog.filter((p) => (!cat || p.category === cat) && (!q || p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q)))
      .sort((a, b) => a.demo_only - b.demo_only);
    document.getElementById("lib").innerHTML = items.map((p) => {
      const d = p.product_dims_mm, sized = d.w && d.h && d.d;
      return `<li class="prod ${armed === p.sku ? "armed" : ""} ${sized ? "" : "nosize"}" draggable="${sized ? "true" : "false"}" data-sku="${esc(p.sku)}">
        <i class="dot" style="background:${esc(p.cmf_options[0]?.hex_approx || "#fff")}"></i>
        <div style="flex:1;min-width:0"><div class="name">${esc(p.name)}</div>
          <div class="cat">${esc(CATEGORY[p.category] || p.category)} · ${sized ? `${mm(d.w)}×${mm(d.h)}×${mm(d.d)} mm` : "치수 정보 없음"}</div>
          ${p.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}</div></li>`;
    }).join("") || `<li class="muted">해당 제품이 없습니다.</li>`;
    document.querySelectorAll("#lib [data-sku]").forEach((li) => {
      li.onclick = () => {
        if (li.classList.contains("nosize")) { toast("치수 정보가 없어 놓을 수 없는 제품입니다", true); return; }
        armed = armed === li.dataset.sku ? null : li.dataset.sku; mode = "move"; syncMode(); setHint(); renderLib();
      };
      li.ondragstart = (e) => e.dataTransfer.setData("text/sku", li.dataset.sku);
    });
  };
  document.getElementById("q").oninput = renderLib;
  renderCats(); renderLib();

  // ---- 미리 보기(저장 없이 판정) ----
  const ghost = (res) => {
    const g = document.getElementById("ghost");
    if (!g) return;
    g.innerHTML = res ? placedSvg({ center_xz: res.pose.center_xz, yaw_rad: res.pose.yaw_rad, size_m: res.size_m, verdict: res.verdict }, pv.sw, false, true) : "";
  };
  let busy = false, queued = null, lastPreview = null;
  const preview = async (args) => {
    if (busy) { queued = args; return; }
    busy = true;
    try {
      lastPreview = await post(`/api/projects/${pid}/pose-check`, args);
      if (lastPreview.size_m && (armed || drag)) ghost(lastPreview);
    } catch { /* 미리 보기 실패는 무시 */ }
    busy = false;
    if (queued) { const a = queued; queued = null; preview(a); }
  };

  const placeAt = guard(async (sku, p) => {
    const r = await post(`/api/projects/${pid}/placements`, { sku, center_xz: p, yaw_rad: Math.PI / 2 });
    selPl = r.placement.placement_id; selObj = null; armed = null;
    toast(`${prodOf(sku)?.name || sku}: ${LABEL[r.placement.verdict]}`);
    setHint(); renderLib();
    await refresh(true);
  });
  const patch = guard(async (plid, body) => {
    await api(`/api/projects/${pid}/placements/${plid}`, { method: "PATCH", body: JSON.stringify(body) });
    await refresh(true);
  });

  // ---- 평면도 조작 ----
  const syncMode = () => document.querySelectorAll("[data-mode]").forEach((x) => x.classList.toggle("on", x.dataset.mode === mode));
  document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => {
    mode = b.dataset.mode; draft = []; armed = null; ghost(null);
    syncMode(); setHint(); renderLib(); drawDraft();
  }));
  const drawDraft = () => {
    const g = document.getElementById("draft");
    if (!g || !pv) return;
    let pts = draft;
    if (mode === "rect" && dragging) { const [a, b] = dragging; pts = [a, [b[0], a[1]], b, [a[0], b[1]]]; }
    g.innerHTML = pts.length ? `<polygon class="draft" points="${pts.map((p) => p.join(",")).join(" ")}" stroke-width="${pv.sw(1.5)}"/>` + pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="${pv.sw(4)}" fill="#a50034"/>`).join("") : "";
  };
  const createZone = guard(async (poly) => {
    const purpose = "kitchen";
    const n = zones.filter((z) => z.purpose === purpose).length;
    const z = await post(`/api/projects/${pid}/zones`, { purpose, polygon_m: poly, name: PURPOSE[purpose] + (n ? ` ${n + 1}` : "") });
    zoneSel = z.zone_id; draft = [];
    toast(`${z.name} 영역을 만들었습니다. 오른쪽 '영역별 추천'에서 확인하세요`);
    await refresh(true);
  });
  svg.onpointerdown = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (mode === "move") {
      if (armedMark) {
        const name = armedMark; armedMark = null;
        guard(async () => { project = await put(`/api/projects/${pid}/marks/${name}`, { center_xz: p }); if (sim === "flow") await flowCtl(); })();
        return;
      }
      if (armedRouter) {
        armedRouter = false;
        guard(async () => { project = await put(`/api/projects/${pid}/router`, { center_xz: p, band }); if (sim === "wifi") await wifiCtl(); })();
        return;
      }
      if (armed) { placeAt(armed, p); return; }
      const g = e.target.closest("[data-pl]");
      if (g) {
        const x = project.scene_state.placements.find((q) => q.placement_id === g.dataset.pl);
        drag = { plid: x.placement_id, sku: x.sku, start: p, orig: x.center_xz, yaw: x.yaw_rad, moved: false };
        selPl = x.placement_id; selObj = null;
        svg.setPointerCapture(e.pointerId);
        renderInspector();
        return;
      }
      const o = e.target.closest("[data-obj]");
      selObj = o ? o.dataset.obj : null;
      selPl = null;
      draw(); renderInspector();
      return;
    }
    if (mode === "rect") { dragging = [p, p]; svg.setPointerCapture(e.pointerId); }
    else {
      if (draft.length >= 3 && Math.hypot(p[0] - draft[0][0], p[1] - draft[0][1]) < 0.15) { createZone(draft); return; }
      draft.push(p);
    }
    drawDraft();
  };
  svg.onpointermove = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (drag) {
      const c = [drag.orig[0] + p[0] - drag.start[0], drag.orig[1] + p[1] - drag.start[1]];
      if (Math.hypot(p[0] - drag.start[0], p[1] - drag.start[1]) > 0.04) drag.moved = true;
      if (drag.moved) {
        svg.querySelector(`[data-pl="${drag.plid}"]`)?.classList.add("dragging");
        preview({ sku: drag.sku, center_xz: c, yaw_rad: drag.yaw, placement_id: drag.plid });
      }
      return;
    }
    if (armed && mode === "move") { preview({ sku: armed, center_xz: p, yaw_rad: Math.PI / 2 }); return; }
    if (dragging) { dragging[1] = p; drawDraft(); }
  };
  svg.onpointerup = (e) => {
    if (drag) {
      const d = drag; drag = null; ghost(null);
      if (d.moved) {
        const p = pv.toWorld(e);
        patch(d.plid, { center_xz: [d.orig[0] + p[0] - d.start[0], d.orig[1] + p[1] - d.start[1]], yaw_rad: d.yaw });
      } else draw();
      return;
    }
    if (!dragging) return;
    const [a, b] = dragging; dragging = null;
    if (Math.abs(a[0] - b[0]) < 0.3 || Math.abs(a[1] - b[1]) < 0.3) { drawDraft(); return; }
    const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    createZone([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
  };
  svg.onpointerleave = () => { if (armed) ghost(null); };
  svg.ondblclick = () => { if (mode === "poly" && draft.length >= 3) createZone(draft); };
  svg.ondragover = (e) => e.preventDefault();
  svg.ondrop = (e) => { e.preventDefault(); const sku = e.dataTransfer.getData("text/sku"); if (sku && pv) placeAt(sku, pv.toWorld(e)); };
  const rotate = (deg) => {
    const x = project.scene_state.placements.find((q) => q.placement_id === selPl);
    if (x) patch(x.placement_id, { yaw_rad: x.yaw_rad + (deg * Math.PI) / 180, snap: false });
  };
  const onKey = (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (e.key === "Escape") { armed = null; ghost(null); setHint(); renderLib(); }
    if (!selPl) return;
    if (e.key === "r" || e.key === "R") rotate(e.shiftKey ? -15 : 15);
    if (e.key === "Delete" || e.key === "Backspace") guard(async () => { await api(`/api/projects/${pid}/placements/${selPl}`, { method: "DELETE" }); selPl = null; await refresh(true); })();
  };
  document.addEventListener("keydown", onKey);
  cleanup.push(() => document.removeEventListener("keydown", onKey));

  // ---- 오른쪽 패널 ----
  const renderInspector = () => {
    const box = document.getElementById("insp");
    const x = selPl && project.scene_state.placements.find((q) => q.placement_id === selPl);
    if (x) {
      const p = prodOf(x.sku) || { name: x.sku, cmf_options: [] };
      const reasons = (x.reasons || []).map((r) => `<li><span class="badge ${r.verdict}">${LABEL[r.verdict]}</span> ${esc(r.label)}${r.ref ? ` <span class="muted">(${esc(r.ref)})</span>` : ""}</li>`).join("");
      box.innerHTML = `
        <div class="row"><h2 style="margin:0;flex:1">${esc(p.name)}</h2><span class="badge ${x.verdict}">${LABEL[x.verdict]}</span></div>
        <p class="muted" style="margin:4px 0 8px;font-size:12px">${esc(x.sku)}${x.wall_id ? ` · 벽 ${esc(x.wall_id)}에 붙임` : ""}${p.demo_only ? ` · <span class="badge demo">가상 데이터</span>` : ""}</p>
        ${reasons ? `<ul class="reasons">${reasons}</ul>` : `<p style="margin:0 0 8px;color:var(--fit)">걸리는 것 없이 들어갑니다.</p>`}
        <div class="row" style="margin-top:8px"><button class="small ghost" id="rl">⟲ 15°</button><button class="small ghost" id="rr">⟳ 15°</button>
          <button class="small ghost" id="snap">벽에 붙이기</button><span class="spacer"></span><button class="small ghost" id="del">빼기</button></div>
        ${p.cmf_options.length ? `<label>색상 (LGE.COM 옵션)</label><div class="swatches">${p.cmf_options.map((o) => `<button class="swatch ${o.color === x.color ? "on" : ""}" data-color="${esc(o.color)}"><i style="background:${esc(o.hex_approx || "#fff")}"></i>${esc(o.color)}</button>`).join("")}</div>` : ""}
        ${p.source_url ? `<p style="margin:10px 0 0"><a class="muted" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기 ↗</a></p>` : ""}`;
      box.querySelector("#rl").onclick = () => rotate(-15);
      box.querySelector("#rr").onclick = () => rotate(15);
      box.querySelector("#snap").onclick = () => patch(x.placement_id, { center_xz: x.center_xz, yaw_rad: x.yaw_rad, snap: true });
      box.querySelector("#del").onclick = guard(async () => { await api(`/api/projects/${pid}/placements/${x.placement_id}`, { method: "DELETE" }); selPl = null; await refresh(true); });
      box.querySelectorAll("[data-color]").forEach((b) => (b.onclick = () => patch(x.placement_id, { color: b.dataset.color })));
      return;
    }
    const o = selObj && room.objects.find((q) => q.object_id === selObj);
    if (o) {
      const gone = (project.scene_state.hidden_objects || []).includes(o.object_id);
      box.innerHTML = `<h2>기존 가구 · ${esc(OBJ[o.category] || o.category)}</h2>
        <p class="muted" style="margin:0 0 8px">${esc(o.object_id)} · ${o.bbox_m.w.toFixed(2)} × ${o.bbox_m.d.toFixed(2)} m, 높이 ${o.bbox_m.h.toFixed(2)} m</p>
        <button class="small" id="hide">${gone ? "되돌리기" : "치우기"}</button>
        <p class="muted" style="font-size:12px;margin:8px 0 0">치운 가구는 판정과 3D에서 빠집니다. 원래 스캔은 그대로 남아요.</p>`;
      box.querySelector("#hide").onclick = guard(async () => {
        await put(`/api/projects/${pid}/objects/${o.object_id}/hidden`, { hidden: !gone });
        await refresh(true);
      });
      return;
    }
    box.innerHTML = `<h2>선택한 제품</h2><p class="muted" style="margin:0">평면도에서 제품이나 기존 가구를 누르면 여기에 판정과 조작 버튼이 나옵니다.</p>`;
  };
  const renderPlacements = () => {
    const pls = project.scene_state.placements;
    document.getElementById("pls").innerHTML = pls.length ? pls.map((x) => `
      <li data-sel="${esc(x.placement_id || "")}" style="cursor:pointer${x.placement_id === selPl ? ";background:var(--accent-soft)" : ""}">
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i><span style="flex:1">${esc(prodOf(x.sku)?.name || x.sku)}</span><span class="badge ${x.verdict}">${LABEL[x.verdict]}</span></li>`).join("")
      : `<li class="muted">아직 없습니다. 왼쪽에서 제품을 골라 보세요.</li>`;
    document.querySelectorAll("#pls [data-sel]").forEach((li) => (li.onclick = () => { selPl = li.dataset.sel || null; selObj = null; draw(); renderInspector(); renderPlacements(); }));
    const gone = project.scene_state.hidden_objects || [];
    if (gone.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">치운 기존 가구 ${gone.length}개 <span class="spacer"></span><button class="small ghost" id="restore">모두 되돌리기</button></li>`);
    const rb = document.getElementById("restore");
    if (rb) rb.onclick = guard(async () => { for (const id of gone) await put(`/api/projects/${pid}/objects/${id}/hidden`, { hidden: false }); await refresh(true); });
  };
  const SWATCH = { wall: ["#F2EFEA", "#E8E4DC", "#D9D4CB", "#C9CFD3", "#3E4247"], floor: ["#C8A27A", "#A67C52", "#E3D5C1", "#8D8D8A", "#5B4636"] };
  const renderMats = () => {
    const m = project.scene_state.materials || {};
    document.getElementById("mats").innerHTML = Object.entries({ wall: "벽", floor: "바닥" }).map(([t, label]) => `
      <div class="row" style="margin-top:6px"><span style="width:36px" class="muted">${label}</span>
        ${SWATCH[t].map((h) => `<button class="sw ${m[t] === h ? "on" : ""}" data-mat="${t}" data-hex="${h}" style="background:${h}" title="${h}"></button>`).join("")}</div>`).join("");
    document.querySelectorAll("[data-mat]").forEach((b) => (b.onclick = guard(async () => {
      await post(`/api/projects/${pid}/materials`, { target: b.dataset.mat, hex_color: b.dataset.hex });
      await refresh(true);
    })));
  };

  document.getElementById("render").onclick = guard(async (e) => {
    e.target.disabled = true; e.target.textContent = "렌더 중…";
    try {
      await post(`/api/projects/${pid}/render`, {});
      const img = document.getElementById("renderImg");
      img.src = `/api/projects/${pid}/files/render.png?v=${Date.now()}`;
      img.style.display = "block";
    } finally { e.target.disabled = false; e.target.textContent = "렌더 이미지"; }
  });
  document.getElementById("zoneSel").onchange = (e) => { zoneSel = e.target.value; renderRecs(); };

  const renderStyle = () => {
    const s = project.style;
    document.getElementById("style").innerHTML = s.prompt || s.palette.length ? `
      <p style="margin:0 0 8px">“${esc(s.prompt || "")}”</p>
      <div class="row"><div class="palette">${s.palette.map((h) => `<i style="background:${esc(h)}" title="${esc(h)}"></i>`).join("")}</div>
      <span class="muted">${s.materials.map(esc).join(" · ")}</span></div>`
      : `<p class="muted" style="margin:0;font-size:12px">Claude 또는 Codex에서 <b>“화이트 우드 톤으로 바꿔 줘”</b>처럼 말하면 스타일이 저장되고 추천에 반영됩니다.</p>`;
  };
  const renderZones = () => {
    document.getElementById("zones").innerHTML = zones.length ? zones.map((z) => `
      <li><b>${esc(z.name || z.purpose)}</b><span class="muted">${esc(z.zone_id)} · 벽 ${esc((z.wall_ids.length ? z.wall_ids : z.auto_wall_ids || []).join(", ") || "없음")}</span>
        <span class="spacer"></span><button class="small ghost" data-del="${esc(z.zone_id)}">삭제</button></li>`).join("")
      : `<li class="muted">평면도 위 '영역 □'으로 영역을 그리세요.</li>`;
    document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = guard(async () => {
      await api(`/api/projects/${pid}/zones/${b.dataset.del}`, { method: "DELETE" });
      if (zoneSel === b.dataset.del) zoneSel = null;
      refresh(true);
    })));
    const zs = document.getElementById("zoneSel");
    if (!zoneSel || !zones.find((z) => z.zone_id === zoneSel)) zoneSel = zones[0]?.zone_id || null;
    zs.style.display = zones.length ? "" : "none";
    zs.innerHTML = zones.map((z) => `<option value="${esc(z.zone_id)}" ${z.zone_id === zoneSel ? "selected" : ""}>${esc(z.name || z.purpose)}</option>`).join("");
  };
  const renderRecs = guard(async () => {
    const box = document.getElementById("recs");
    if (!zoneSel) { box.innerHTML = ""; return; }
    const r = await api(`/api/projects/${pid}/zones/${zoneSel}/recommendations`);
    const placed = new Set(project.scene_state.placements.filter((p) => p.zone_id === zoneSel).map((p) => p.sku));
    box.innerHTML = r.items.length ? r.items.map((it) => card(it, placed.has(it.product.sku))).join("")
      : `<p class="empty">이 용도에 맞는 카탈로그 제품이 없습니다.</p>`;
    box.querySelectorAll("[data-place]").forEach((b) => (b.onclick = guard(async () => {
      const [sku, color] = [b.dataset.place, b.dataset.color || undefined];
      if (b.dataset.on === "1") await api(`/api/projects/${pid}/placements/${zoneSel}/${encodeURIComponent(sku)}`, { method: "DELETE" });
      else await post(`/api/projects/${pid}/placements`, { zone_id: zoneSel, sku, color });
      await refresh(true);
    })));
  });
  const card = (it, isPlaced) => {
    const p = it.product, f = it.fit;
    const dims = Object.entries(f.dims || {}).map(([k, d]) => `
      <tr><td>${DIM[k]}</td><td class="mono">${mm(d.available_mm)}</td><td class="mono">${mm(d.required_mm)}</td>
      <td class="mono">${d.slack_mm == null ? "–" : (d.slack_mm >= 0 ? "+" : "") + mm(d.slack_mm)}</td>
      <td><span class="badge ${d.verdict}">${LABEL[d.verdict]}</span></td><td class="muted">${d.source === "measured" ? "실측" : "스캔"}</td></tr>`).join("");
    const top = it.cmf[0];
    const canPlace = f.placement && f.verdict !== "no_fit";
    return `<div class="card">
      <div class="head"><div style="flex:1"><div class="name">${esc(p.name)}</div>
        <div class="cat">${esc(CATEGORY[p.category] || p.category)} · ${esc(p.sku)}</div></div>
        <span class="badge ${f.verdict}">${LABEL[f.verdict]}</span></div>
      <div class="row" style="margin-top:6px">${p.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}
        ${f.wall_id ? `<span class="badge src">벽 ${esc(f.wall_id)}</span>` : ""}${(f.notes || []).map((n) => `<span class="badge src">${esc(NOTE[n] || n)}</span>`).join("")}</div>
      ${dims ? `<table class="dims"><thead><tr><th></th><th>가용 mm</th><th>필요 mm</th><th>여유</th><th></th><th></th></tr></thead><tbody>${dims}</tbody></table>` : ""}
      ${top && top.reasons.length ? `<div class="reason">추천 색: <b>${esc(top.color)}</b> · ${esc(top.reasons.join(" · "))}</div>` : ""}
      <div class="row" style="margin-top:10px">
        ${canPlace ? `<button class="small ${isPlaced ? "ghost" : ""}" data-place="${esc(p.sku)}" data-on="${isPlaced ? 1 : 0}" data-color="${esc(top?.color || "")}">${isPlaced ? "배치 취소" : "여기에 놓기"}</button>` : ""}
        <span class="spacer"></span>
        ${p.source_url ? `<a class="muted" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM ↗</a>` : ""}
      </div></div>`;
  };

  const draw = () => {
    pv = planView(svg, room, { zones, placements: project.scene_state.placements, hidden: project.scene_state.hidden_objects,
      selectedPl: selPl, selectedObj: selObj, overlay, northDeg: sim === "daylight" ? project.site?.north_deg ?? 0 : null });
    drawDraft();
  };
  const setOverlay = (html) => { overlay = html; const g = document.getElementById("overlay"); if (g) g.innerHTML = html; };

  // ---- 살아 보기: 채광 ----
  const heat = (grid, color, maxV) => {
    const out = [];
    const [x0, y0] = grid.origin, c = grid.cell_m;
    grid.values.forEach((row, j) => row.forEach((v, i) => {
      if (v == null || v <= 0) return;
      out.push(`<rect x="${x0 + i * c}" y="${y0 + j * c}" width="${c}" height="${c}" fill="${color}" fill-opacity="${Math.min(0.75, 0.12 + (0.63 * v) / maxV).toFixed(2)}"/>`);
    }));
    return out.join("");
  };
  let simTimer = null;
  const runDaylight = async () => {
    const box = document.getElementById("simres");
    if (project.site?.north_deg == null) { setOverlay(""); box.innerHTML = `<p class="notice" style="margin:0">스캔에는 방향 정보가 없어요. 위 슬라이더로 평면도의 나침반을 실제 북쪽에 맞춰 주세요. (휴대폰 나침반 앱으로 확인)</p>`; return; }
    const d = await api(`/api/projects/${pid}/sim/daylight?date=${simState.date}&time=${simState.time}`);
    const maxH = Math.max(1, ...d.daily.values.flat().filter((v) => v != null));
    setOverlay(heat(d.daily, "#f2a900", maxH) + d.patches.map((p) => `<polygon class="sunpatch" points="${p.polygon.map((q) => q.join(",")).join(" ")}" style="stroke-width:${pv.sw(1.5)}px"/>`).join(""));
    const pls = project.scene_state.placements.filter((x) => x.placement_id in d.daily.points);
    box.innerHTML = `
      <p style="margin:0 0 6px">${d.sun.altitude_deg > 0 ? `해 높이 <b>${d.sun.altitude_deg.toFixed(0)}°</b> · 방위 <b>${d.sun.azimuth_deg.toFixed(0)}°</b> · 지금 볕 드는 창 ${d.patches.length}개` : "해가 진 시간입니다"} · 진한 노랑일수록 하루 직사광이 깁니다 (최대 ${maxH.toFixed(1)}시간)</p>
      ${pls.length ? `<ul class="reasons">${pls.map((x) => { const h = d.daily.points[x.placement_id]; return `<li>${esc(prodOf(x.sku)?.name || x.sku)}: 하루 직사광 <b>${h.toFixed(1)}시간</b>${h >= 2 ? ` <span class="badge conditional">햇빛 주의</span>` : ""}</li>`; }).join("")}</ul>` : ""}
      <p class="muted" style="font-size:12px;margin:6px 0 0">참고용 시뮬레이션 · ${d.assumptions.map(esc).join(" · ")}</p>`;
  };
  const daylightCtl = async () => {
    regions = regions || (await api("/api/regions"));
    const site = project.site || {};
    document.getElementById("simctl").innerHTML = `
      <div class="simgrid">
        <label>지역<select id="region">${Object.keys(regions).map((r) => `<option ${r === (site.region || "서울") ? "selected" : ""}>${r}</option>`).join("")}</select></label>
        <label>북쪽 방향 <span class="muted" id="nv">${site.north_deg ?? "미지정"}${site.north_deg != null ? "°" : ""}</span><input type="range" id="north" min="0" max="355" step="5" value="${site.north_deg ?? 0}"></label>
        <label>날짜<input type="date" id="sdate" value="${simState.date}"></label>
        <label>시각 <b id="tv">${simState.time}</b><input type="range" id="stime" min="300" max="1260" step="15" value="${(() => { const [h, m] = simState.time.split(":").map(Number); return h * 60 + m; })()}"></label>
      </div>
      <div class="chips" style="margin:6px 0 8px">${[["동지", "-12-21"], ["춘분", "-03-20"], ["하지", "-06-21"]].map(([k, v]) => `<button class="chip" data-day="${v}">${k}</button>`).join("")}<button class="chip" data-day="today">오늘</button></div>
      <div id="simres"></div>`;
    const kick = () => { clearTimeout(simTimer); simTimer = setTimeout(() => guard(runDaylight)(), 120); };
    document.getElementById("region").onchange = guard(async (e) => { project = await put(`/api/projects/${pid}/site`, { region: e.target.value }); kick(); });
    document.getElementById("north").oninput = (e) => {
      document.getElementById("nv").textContent = `${e.target.value}°`;
      svg.querySelector(".compass")?.setAttribute("transform", svg.querySelector(".compass").getAttribute("transform").replace(/rotate\([^ ]+/, `rotate(${e.target.value}`));
    };
    document.getElementById("north").onchange = guard(async (e) => { project = await put(`/api/projects/${pid}/site`, { north_deg: Number(e.target.value) }); draw(); kick(); });
    document.getElementById("sdate").onchange = (e) => { simState.date = e.target.value; kick(); };
    document.getElementById("stime").oninput = (e) => {
      const v = Number(e.target.value); simState.time = `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
      document.getElementById("tv").textContent = simState.time; kick();
    };
    document.querySelectorAll("[data-day]").forEach((b) => (b.onclick = () => {
      simState.date = b.dataset.day === "today" ? new Date().toISOString().slice(0, 10) : `${simState.date.slice(0, 4)}${b.dataset.day}`;
      document.getElementById("sdate").value = simState.date; kick();
    }));
    if (project.site?.north_deg == null) draw();
    await runDaylight();
  };
  // ---- 살아 보기: 와이파이 ----
  let armedRouter = false, band = "5";
  const WCOLOR = { good: "#1f7a4d", ok: "#e0a800", weak: "#b3261e" };
  const WLABEL = { good: "좋음", ok: "보통", weak: "약함" };
  const runWifi = async () => {
    const box = document.getElementById("simres");
    const rt = project.scene_state.router;
    if (!rt) { setOverlay(""); box.innerHTML = `<p class="notice" style="margin:0">공유기를 평면도에 놓거나 '추천 자리 찾기'를 눌러 보세요.</p>`; return; }
    const g = await api(`/api/projects/${pid}/sim/wifi?band=${band}`);
    const gradeOf = (v) => (v >= -60 ? "good" : v >= -70 ? "ok" : "weak");
    const [x0, y0] = g.origin, c = g.cell_m, cells = [];
    g.values.forEach((row, j) => row.forEach((v, i) => { if (v != null) cells.push(`<rect x="${x0 + i * c}" y="${y0 + j * c}" width="${c}" height="${c}" fill="${WCOLOR[gradeOf(v)]}" fill-opacity="0.28"/>`); }));
    const [rx, ry] = g.router, r = pv.sw(9);
    setOverlay(cells.join("") + `<g class="router"><circle cx="${rx}" cy="${ry}" r="${r}" style="stroke-width:${pv.sw(2)}px"/><text x="${rx}" y="${ry}" text-anchor="middle" dominant-baseline="central" style="font-size:${pv.sw(10)}px">📶</text></g>`);
    const pct = (v) => `${Math.round((v || 0) * 100)}%`;
    box.innerHTML = `
      <p style="margin:0 0 6px">${["good", "ok", "weak"].map((k) => `<span class="badge" style="background:${WCOLOR[k]}22;color:${WCOLOR[k]}">${WLABEL[k]} ${pct(g.share[k])}</span>`).join(" ")} · 가장 약한 곳 <b>${g.min_dbm} dBm</b></p>
      ${g.zones.length ? `<ul class="reasons">${g.zones.map((z) => `<li>${esc(z.name)}: ${z.min_dbm == null ? "영역 안 칸 없음" : `가장 약한 곳 ${z.min_dbm} dBm · 약함 ${pct(z.share.weak)}`}</li>`).join("")}</ul>` : `<p class="muted" style="font-size:12px;margin:0">영역을 그리면 영역별 요약도 보여 드려요.</p>`}
      <p class="muted" style="font-size:12px;margin:6px 0 0">참고용 시뮬레이션 · ${g.assumptions.map(esc).join(" · ")}</p>`;
  };
  const wifiCtl = async () => {
    document.getElementById("simctl").innerHTML = `
      <div class="row" style="margin-top:8px">
        <div class="tabs" style="margin:0"><button data-band="5" class="${band === "5" ? "on" : ""}">5 GHz</button><button data-band="2.4" class="${band === "2.4" ? "on" : ""}">2.4 GHz</button></div>
        <button class="small ghost" id="putRouter">${armedRouter ? "놓을 자리를 누르세요…" : "공유기 놓기"}</button>
        <button class="small ghost" id="bestRouter">추천 자리 찾기</button></div>
      <div id="simres" style="margin-top:8px"></div>`;
    document.querySelectorAll("[data-band]").forEach((b) => (b.onclick = () => { band = b.dataset.band; wifiCtl(); }));
    document.getElementById("putRouter").onclick = () => { armedRouter = !armedRouter; armed = null; mode = "move"; syncMode(); wifiCtl(); };
    document.getElementById("bestRouter").onclick = guard(async (e) => {
      e.target.disabled = true; e.target.textContent = "찾는 중…";
      const b = await api(`/api/projects/${pid}/sim/wifi/best?band=${band}`);
      project = await put(`/api/projects/${pid}/router`, { center_xz: b.center_xz, band });
      toast(`가장 약한 곳이 ${b.min_dbm} dBm가 되는 자리로 옮겼습니다`);
      wifiCtl();
    });
    await runWifi();
  };
  // ---- 살아 보기: 동선 ----
  let armedMark = null;
  const runFlow = async () => {
    const box = document.getElementById("simres");
    const f = await api(`/api/projects/${pid}/sim/flow`);
    const parts = [];
    const lw = pv.sw(3);
    for (const [k, r] of Object.entries(f.routes)) {
      if (!r.reachable) continue;
      parts.push(`<polyline class="route" points="${r.path.map((p) => p.join(",")).join(" ")}" style="stroke-width:${lw}px"/>`);
      for (const n of r.narrow) parts.push(`<circle class="narrow" cx="${n[0]}" cy="${n[1]}" r="${pv.sw(5)}"/>`);
    }
    if (f.entrance) { const [x, y] = f.entrance.point; parts.push(`<g class="mark"><circle cx="${x}" cy="${y}" r="${pv.sw(9)}" style="stroke-width:${pv.sw(1.5)}px"/><text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" style="font-size:${pv.sw(10)}px">🚪</text></g>`); }
    for (const [k, v] of Object.entries(f.marks || {})) if (k === "sink") parts.push(`<g class="mark"><circle cx="${v[0]}" cy="${v[1]}" r="${pv.sw(9)}" style="stroke-width:${pv.sw(1.5)}px"/><text x="${v[0]}" y="${v[1]}" text-anchor="middle" dominant-baseline="central" style="font-size:${pv.sw(10)}px">🚰</text></g>`);
    setOverlay(parts.join(""));
    const rows = Object.entries(f.routes).map(([k, r]) => {
      const nm = esc(f.names[k] || k);
      if (!r.reachable) return `<li><span class="badge no_fit">못 감</span> ${nm}: 현관에서 갈 길이 막혔어요</li>`;
      const bad = r.min_width_m < 0.9;
      return `<li><span class="badge ${bad ? "conditional" : "fit"}">${bad ? "좁음" : "여유"}</span> ${nm}: ${r.length_m} m · 가장 좁은 곳 ${r.min_width_m} m</li>`;
    }).join("");
    const t = f.triangle;
    box.innerHTML = `
      ${rows ? `<ul class="reasons">${rows}</ul>` : `<p class="muted" style="margin:0">제품을 놓으면 현관에서 제품 앞까지 동선을 그려 드려요.</p>`}
      ${t ? `<p style="margin:6px 0 0">주방 작업 삼각형(냉장고·싱크·쿡탑) 합계 <b>${t.perimeter_m} m</b> (${t.legs_m.join(" / ")} m) <span class="badge ${t.ok ? "fit" : "conditional"}">${t.ok ? "권장 범위" : "권장 범위 밖"}</span></p>` : ""}
      <p class="muted" style="font-size:12px;margin:6px 0 0">빨간 점 = 0.9 m보다 좁은 곳 · 참고용 시뮬레이션 · ${f.assumptions.map(esc).join(" · ")}</p>`;
  };
  const flowCtl = async () => {
    document.getElementById("simctl").innerHTML = `
      <div class="row" style="margin-top:8px">
        <button class="small ghost" id="mkEnt">${armedMark === "entrance" ? "현관 쪽을 누르세요…" : "현관 지정"}</button>
        <button class="small ghost" id="mkSink">${armedMark === "sink" ? "싱크 자리를 누르세요…" : "싱크 위치 지정"}</button>
        <span class="muted" style="font-size:12px">싱크를 지정하고 냉장고·쿡탑을 놓으면 작업 삼각형을 계산해요.</span></div>
      <div id="simres" style="margin-top:8px"></div>`;
    document.getElementById("mkEnt").onclick = () => { armedMark = armedMark === "entrance" ? null : "entrance"; armed = null; mode = "move"; syncMode(); flowCtl(); };
    document.getElementById("mkSink").onclick = () => { armedMark = armedMark === "sink" ? null : "sink"; armed = null; mode = "move"; syncMode(); flowCtl(); };
    await runFlow();
  };
  const SIMS = { daylight: daylightCtl, wifi: wifiCtl, flow: flowCtl };
  const showSim = guard(async () => {
    document.querySelectorAll("[data-sim]").forEach((x) => x.classList.toggle("on", x.dataset.sim === sim));
    if (!sim) { document.getElementById("simctl").innerHTML = ""; setOverlay(""); draw(); return; }
    draw();
    if (SIMS[sim]) await SIMS[sim]();
    else { setOverlay(""); document.getElementById("simctl").innerHTML = `<p class="muted">준비 중입니다.</p>`; }
  });
  document.querySelectorAll("[data-sim]").forEach((b) => (b.onclick = () => { sim = b.dataset.sim; showSim(); }));
  const refresh = async (force = false) => {
    if (drag) return;
    const v = (await api(`/api/projects/${pid}/version`)).version;
    if (!force && v === version) return;
    version = v;
    [project, room, zones] = await Promise.all([api(`/api/projects/${pid}`), api(`/api/projects/${pid}/room`), api(`/api/projects/${pid}/zones`)]);
    if (selPl && !project.scene_state.placements.some((q) => q.placement_id === selPl)) selPl = null;
    const measured = room.walls.filter((w) => w.measured).length, n = project.scene_state.placements.length;
    document.getElementById("sub").textContent = `${project.scan.scanned_by === "customer" ? "셀프 LiDAR 스캔" : "기사 방문 스캔"} · 벽 ${room.walls.length}개${measured ? ` (실측 ${measured}개)` : ""}${project.floorplan ? " · 도면 첨부" : ""} · 놓은 제품 ${n}개 · 마지막 갱신 ${new Date().toLocaleTimeString("ko-KR")}`;
    draw();
    if (sim === "daylight" && document.getElementById("simres")) guard(runDaylight)();
    if (sim === "wifi" && document.getElementById("simres")) guard(runWifi)();
    if (sim === "flow" && document.getElementById("simres")) guard(runFlow)();
    renderInspector();
    renderPlacements();
    renderZones();
    renderStyle();
    renderMats();
    renderRecs();
    floorplanBox(document.getElementById("fpBox"), pid, project, () => refresh(true));
    wallTable(document.getElementById("walls"), pid, room, { by: "customer", onChange: () => refresh(true) });
    viewer.load(`/api/projects/${pid}/files/scene.glb`);
    document.getElementById("hud").textContent = `드래그 회전 · 휠 확대 · ${project.scene.engine === "blender" ? "Blender" : "치수 박스 미리보기"}`;
  };
  setHint();
  await guard(refresh)(true);
  // 채팅(Claude·Codex) 쪽 변경을 2초마다 확인
  const timer = setInterval(() => refresh().catch(() => {}), 2000);
  cleanup.push(() => clearInterval(timer));
}

route();
