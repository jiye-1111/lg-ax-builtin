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
  return home();
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
  for (const o of room.objects) {
    const [x, , zz] = o.position;
    const deg = (o.yaw_rad * 180) / Math.PI;
    html += `<rect class="obj" x="${x - o.bbox_m.w / 2}" y="${zz - o.bbox_m.d / 2}" width="${o.bbox_m.w}" height="${o.bbox_m.d}" transform="rotate(${deg} ${x} ${zz})" stroke-width="${sw(1)}"/>`;
    html += `<text x="${x}" y="${zz}" text-anchor="middle" dominant-baseline="middle" style="font-size:${sw(10)}px" fill="#6b6f76">${esc(o.category)}</text>`;
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
  for (const p of opts.placements || []) {
    const [w_, , d_] = p.size_m;
    const deg = ((p.yaw_rad - Math.PI / 2) * 180) / Math.PI;
    const [x, y] = p.center_xz;
    html += `<rect class="placed" x="${x - w_ / 2}" y="${y - d_ / 2}" width="${w_}" height="${d_}" transform="rotate(${deg} ${x} ${y})" style="fill:${esc(p.hex || "#fff")};stroke-width:${sw(1.5)}px"/>`;
  }
  html += `<g id="draft"></g>`;
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

// ---------- 화면: 상담 요청 ----------
async function home() {
  $app.innerHTML = `
    <h1>우리 집 빌트인 설계 상담</h1>
    <p class="sub">서비스센터 기사가 방문해 LiDAR로 공간을 스캔하고, 설치 가능한 LG 빌트인 가전과 어울리는 색상·재질을 추천해 드립니다.</p>
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
      <h2>벽 치수 · 실측 보정</h2>
      <div class="notice">빌트인 밀착 간격은 mm 단위입니다. 스캔값만으로는 "조건부"까지만 판정되고, 설치할 벽의 길이·높이·깊이를 줄자로 재서 넣으면 "적합"을 낼 수 있습니다. 원래 스캔값은 보존됩니다.</div>
      <table><thead><tr><th>벽</th><th>스캔 길이</th><th>스캔 높이</th><th>실측 길이 (m)</th><th>실측 높이 (m)</th><th>벽 앞 깊이 (m)</th><th></th></tr></thead><tbody id="walls"></tbody></table>
    </div>`;
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
    document.getElementById("walls").innerHTML = room.walls.map((w) => `
      <tr data-row="${w.wall_id}" ${sel === w.wall_id ? 'style="background:var(--accent-soft)"' : ""}>
        <td><b>${w.wall_id}</b></td><td class="mono">${w.scanned.length_m.toFixed(3)}</td><td class="mono">${w.scanned.height_m.toFixed(3)}</td>
        <td><input class="mono" name="length_m" type="number" step="0.001" value="${w.measured?.length_m ?? ""}"></td>
        <td><input class="mono" name="height_m" type="number" step="0.001" value="${w.measured?.height_m ?? ""}"></td>
        <td><input class="mono" name="depth_m" type="number" step="0.001" value="${w.measured?.depth_m ?? ""}"></td>
        <td class="row"><button class="small" data-save="${w.wall_id}">저장</button>${w.measured ? `<button class="small ghost" data-clear="${w.wall_id}">초기화</button>` : ""}</td></tr>`).join("");
    document.querySelectorAll("[data-save]").forEach((b) => (b.onclick = guard(async () => {
      const tr = b.closest("tr"), body = {};
      tr.querySelectorAll("input").forEach((i) => { if (i.value !== "") body[i.name] = parseFloat(i.value); });
      await put(`/api/projects/${pid}/walls/${b.dataset.save}/measured`, body);
      toast(`${b.dataset.save} 실측값 저장`);
      load();
    })));
    document.querySelectorAll("[data-clear]").forEach((b) => (b.onclick = guard(async () => {
      await api(`/api/projects/${pid}/walls/${b.dataset.clear}/measured`, { method: "DELETE" });
      load();
    })));
    viewer.load(`/api/projects/${pid}/files/scene.glb`);
    document.getElementById("hud").textContent = "드래그 회전 · 휠 확대";
  };
  await guard(load)();
}

// ---------- 화면: 고객 ----------
async function customer(pid) {
  $app.innerHTML = `
    <div class="row"><div><h1>우리 집 빌트인 설계 · ${esc(pid)}</h1><p class="sub" id="sub">불러오는 중…</p></div></div>
    <div class="grid3">
      <div class="panel">
        <h2>1. 영역 지정</h2>
        <div class="tabs"><button data-mode="rect" class="on">사각형</button><button data-mode="poly">다각형</button></div>
        <label>용도</label>
        <select id="purpose">${Object.entries(PURPOSE).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
        <svg class="plan" id="plan" style="margin-top:10px"></svg>
        <p class="muted" style="font-size:12px;margin:6px 0 10px" id="hint">평면도에서 드래그해 영역을 그리세요 (5cm 단위).</p>
        <ul class="list" id="zones"></ul>
      </div>
      <div>
        <div class="panel"><div class="row"><h2 style="margin:0">2. 3D 공간</h2><span class="spacer"></span><button class="ghost small" id="render">렌더 이미지</button></div>
          <div class="viewer" id="viewer" style="margin-top:10px"><span class="hud" id="hud"></span></div>
          <img id="renderImg" alt="렌더 결과" style="display:none;width:100%;margin-top:10px;border-radius:10px"></div>
        <div class="panel" style="margin-top:16px"><h2>3. 스타일</h2><div id="style"></div></div>
      </div>
      <div class="panel"><div class="row"><h2 style="margin:0">4. 추천 제품</h2><span class="spacer"></span><select id="zoneSel" style="width:auto"></select></div>
        <div id="recs" class="cards" style="margin-top:10px"></div></div>
    </div>`;
  const viewer = makeViewer(document.getElementById("viewer"));
  cleanup.push(() => viewer.dispose());
  let mode = "rect", draft = [], dragging = null, version = -1, zoneSel = null, project, room, zones;
  document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => {
    mode = b.dataset.mode; draft = [];
    document.querySelectorAll("[data-mode]").forEach((x) => x.classList.toggle("on", x === b));
    document.getElementById("hint").textContent = mode === "rect" ? "평면도에서 드래그해 영역을 그리세요 (5cm 단위)." : "꼭짓점을 차례로 누르고, 첫 점을 다시 누르거나 더블클릭하면 완성됩니다.";
    drawDraft();
  }));
  let pv;
  const drawDraft = () => {
    const g = document.getElementById("draft");
    if (!g || !pv) return;
    let pts = draft;
    if (mode === "rect" && dragging) { const [a, b] = dragging; pts = [a, [b[0], a[1]], b, [a[0], b[1]]]; }
    g.innerHTML = pts.length ? `<polygon class="draft" points="${pts.map((p) => p.join(",")).join(" ")}" stroke-width="${pv.sw(1.5)}"/>` + pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="${pv.sw(4)}" fill="#a50034"/>`).join("") : "";
  };
  const createZone = guard(async (poly) => {
    const purpose = document.getElementById("purpose").value;
    const n = zones.filter((z) => z.purpose === purpose).length;
    const z = await post(`/api/projects/${pid}/zones`, { purpose, polygon_m: poly, name: PURPOSE[purpose] + (n ? ` ${n + 1}` : "") });
    zoneSel = z.zone_id;
    draft = [];
    toast(`${z.name} 영역을 만들었습니다`);
    await refresh(true);
  });
  const svg = document.getElementById("plan");
  svg.onpointerdown = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (mode === "rect") { dragging = [p, p]; svg.setPointerCapture(e.pointerId); }
    else {
      if (draft.length >= 3 && Math.hypot(p[0] - draft[0][0], p[1] - draft[0][1]) < 0.15) { createZone(draft); return; }
      draft.push(p);
    }
    drawDraft();
  };
  svg.onpointermove = (e) => { if (dragging) { dragging[1] = pv.toWorld(e); drawDraft(); } };
  svg.onpointerup = () => {
    if (!dragging) return;
    const [a, b] = dragging; dragging = null;
    if (Math.abs(a[0] - b[0]) < 0.3 || Math.abs(a[1] - b[1]) < 0.3) { drawDraft(); return; }
    const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    createZone([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
  };
  svg.ondblclick = () => { if (mode === "poly" && draft.length >= 3) createZone(draft); };

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
      <span class="muted">${s.materials.map(esc).join(" · ")}</span></div>
      <p class="muted" style="font-size:12px;margin:8px 0 0">Claude 또는 Codex 대화에서 바꾸면 여기에 바로 반영됩니다.</p>`
      : `<p class="muted" style="margin:0">아직 스타일이 없습니다. Claude 또는 Codex에서 예: <b>“화이트 우드 톤의 미니멀한 주방으로 해 줘”</b>라고 말해 보세요. (MCP 도구 <code>set_style</code>)</p>`;
  };
  const renderZones = () => {
    document.getElementById("zones").innerHTML = zones.length ? zones.map((z) => `
      <li><b>${esc(z.name || z.purpose)}</b><span class="muted">${esc(z.zone_id)} · 벽 ${esc((z.wall_ids.length ? z.wall_ids : z.auto_wall_ids || []).join(", ") || "없음")}</span>
        <span class="spacer"></span><button class="small ghost" data-del="${esc(z.zone_id)}">삭제</button></li>`).join("")
      : `<li class="muted">영역이 없습니다.</li>`;
    document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = guard(async () => {
      await api(`/api/projects/${pid}/zones/${b.dataset.del}`, { method: "DELETE" });
      if (zoneSel === b.dataset.del) zoneSel = null;
      refresh(true);
    })));
    const zs = document.getElementById("zoneSel");
    if (!zoneSel || !zones.find((z) => z.zone_id === zoneSel)) zoneSel = zones[0]?.zone_id || null;
    zs.innerHTML = zones.map((z) => `<option value="${esc(z.zone_id)}" ${z.zone_id === zoneSel ? "selected" : ""}>${esc(z.name || z.purpose)}</option>`).join("");
  };
  const renderRecs = guard(async () => {
    const box = document.getElementById("recs");
    if (!zoneSel) { box.innerHTML = `<p class="empty">영역을 먼저 지정하세요.</p>`; return; }
    const r = await api(`/api/projects/${pid}/zones/${zoneSel}/recommendations`);
    const placed = new Set(project.scene_state.placements.filter((p) => p.zone_id === zoneSel).map((p) => p.sku));
    box.innerHTML = r.items.length ? r.items.map((it) => card(it, placed.has(it.product.sku), r.margins_mm)).join("")
      : `<p class="empty">이 용도(${esc(PURPOSE[r.zone.purpose] || r.zone.purpose)})에 맞는 카탈로그 제품이 없습니다.</p>`;
    box.querySelectorAll("[data-place]").forEach((b) => (b.onclick = guard(async () => {
      const [sku, color] = [b.dataset.place, b.dataset.color || undefined];
      if (b.dataset.on === "1") await api(`/api/projects/${pid}/placements/${zoneSel}/${encodeURIComponent(sku)}`, { method: "DELETE" });
      else await post(`/api/projects/${pid}/placements`, { zone_id: zoneSel, sku, color });
      await refresh(true);
    })));
  });
  const card = (it, isPlaced, margins) => {
    const p = it.product, f = it.fit;
    const dims = Object.entries(f.dims || {}).map(([k, d]) => `
      <tr><td>${DIM[k]}</td><td class="mono">${mm(d.available_mm)}</td><td class="mono">${mm(d.required_mm)}</td>
      <td class="mono">${d.slack_mm == null ? "–" : (d.slack_mm >= 0 ? "+" : "") + mm(d.slack_mm)}</td>
      <td><span class="badge ${d.verdict}">${LABEL[d.verdict]}</span></td><td class="muted">${d.source === "measured" ? "실측" : "스캔"}</td></tr>`).join("");
    const sw = it.cmf.map((c, i) => `
      <span class="swatch" title="${esc(c.reasons.join(" / "))}"><i style="background:${esc(c.hex_approx || "#fff")}"></i>${i === 0 ? "<b>" : ""}${esc(c.color)}${i === 0 ? "</b>" : ""}
      <span class="muted">${c.material ? esc(c.material) + " · " : ""}${Math.round(c.score * 100)}점</span></span>`).join("");
    const top = it.cmf[0];
    const canPlace = f.placement && f.verdict !== "no_fit";
    return `<div class="card">
      <div class="head"><div style="flex:1"><div class="name">${esc(p.name)}</div>
        <div class="cat">${esc(CATEGORY[p.category] || p.category)} · ${esc(p.sku)} · ${p.install_type === "built_in" ? "빌트인" : p.install_type === "built_in_look" ? "빌트인 룩" : "프리스탠딩"}</div></div>
        <span class="badge ${f.verdict}">${LABEL[f.verdict]}</span></div>
      <div class="row" style="margin-top:6px">${p.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}
        ${f.wall_id ? `<span class="badge src">벽 ${esc(f.wall_id)}</span>` : ""}${(f.notes || []).map((n) => `<span class="badge src">${esc(NOTE[n] || n)}</span>`).join("")}</div>
      ${dims ? `<table class="dims"><thead><tr><th></th><th>가용 mm</th><th>필요 mm</th><th>여유</th><th></th><th></th></tr></thead><tbody>${dims}</tbody></table>` : ""}
      ${sw ? `<div class="swatches">${sw}</div>` : ""}
      ${top && top.reasons.length ? `<div class="reason">추천 이유: ${esc(top.reasons.join(" · "))}${top.hex_approx ? " (색은 근사값)" : ""}</div>` : ""}
      <div class="row" style="margin-top:10px">
        ${canPlace ? `<button class="small ${isPlaced ? "ghost" : ""}" data-place="${esc(p.sku)}" data-on="${isPlaced ? 1 : 0}" data-color="${esc(top?.color || "")}">${isPlaced ? "배치 취소" : "3D에 배치해 보기"}</button>` : ""}
        <span class="spacer"></span>
        ${p.source_url ? `<a class="muted" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기 ↗</a>` : `<span class="muted" style="font-size:12px">출처 없음</span>`}
      </div></div>`;
  };

  const refresh = async (force = false) => {
    const v = (await api(`/api/projects/${pid}/version`)).version;
    if (!force && v === version) return;
    version = v;
    [project, room, zones] = await Promise.all([api(`/api/projects/${pid}`), api(`/api/projects/${pid}/room`), api(`/api/projects/${pid}/zones`)]);
    const measured = room.walls.filter((w) => w.measured).length;
    document.getElementById("sub").textContent = `벽 ${room.walls.length}개 중 ${measured}개 기사 실측 완료 · 상태 ${project.status} · 마지막 갱신 ${new Date().toLocaleTimeString("ko-KR")}`;
    pv = planView(svg, room, { zones, placements: project.scene_state.placements });
    drawDraft();
    renderZones();
    renderStyle();
    renderRecs();
    viewer.load(`/api/projects/${pid}/files/scene.glb`);
    document.getElementById("hud").textContent = `3D 엔진: ${project.scene.engine === "blender" ? "Blender" : "치수 박스 미리보기"}`;
  };
  await guard(refresh)(true);
  // 채팅(Claude·Codex) 쪽 변경을 2초마다 확인
  const timer = setInterval(() => refresh().catch(() => {}), 2000);
  cleanup.push(() => clearInterval(timer));
}

route();
