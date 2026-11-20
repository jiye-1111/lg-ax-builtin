// 계정: 로그인 창(고객·기사), 상단 계정 버튼, 내 집 목록, 기사 관리(관리자), 리모델링 저장 막대(자동·수동 저장)
import { $app, cleanup, esc, api, post, toast, guard, currentUser, authToken, setAuth, onAuth } from "./core.js";

const ROLE = { customer: "고객", technician: "기사", admin: "관리자" };
const TECH_STATUS = { pending: "승인 대기", approved: "승인됨", suspended: "이용 중지", rejected: "거절됨" };
const timeKo = (iso) => {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return d.toLocaleString("ko-KR", today ? { hour: "numeric", minute: "2-digit" } : { month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" });
};
const isTech = (u) => u && (u.role === "admin" || (u.role === "technician" && u.status === "approved"));

// ---------- 로그인 창 ----------
/** 로그인·회원가입 창을 띄운다. 로그인하면 계정, 닫으면 null */
export function openLogin({ role = "customer", mode = "login", reason = "" } = {}) {
  document.querySelector("dialog.auth")?.remove();
  const dlg = document.createElement("dialog");
  dlg.className = "auth";
  dlg.setAttribute("aria-labelledby", "authH");
  document.body.append(dlg);
  let done;
  const result = new Promise((r) => (done = r));
  const state = { role, mode };
  const render = () => {
    const signup = state.mode === "signup", tech = state.role === "technician";
    dlg.innerHTML = `
      <form method="dialog" class="auth-form" novalidate>
        <button type="button" class="auth-x" aria-label="닫기">×</button>
        <h2 id="authH">${signup ? (tech ? "기사 회원가입" : "회원가입") : "로그인"}</h2>
        ${reason ? `<p class="auth-reason">${esc(reason)}</p>` : ""}
        <div class="role-pick" role="radiogroup" aria-label="계정 종류">
          <button type="button" role="radio" aria-checked="${!tech}" data-role="customer">
            <b>고객</b><span>우리 집을 꾸미고 저장해요</span></button>
          <button type="button" role="radio" aria-checked="${tech}" data-role="technician">
            <b>기사</b><span>방문 스캔을 등록하고 고객 집을 도와요</span></button>
        </div>
        <label for="aEmail">이메일</label>
        <input id="aEmail" name="email" type="email" autocomplete="email" required maxlength="254">
        <label for="aPw">비밀번호${signup ? " <em>8자 이상</em>" : ""}</label>
        <input id="aPw" name="password" type="password" autocomplete="${signup ? "new-password" : "current-password"}" required minlength="${signup ? 8 : 1}" maxlength="128">
        ${signup ? `
          <label for="aName">이름</label><input id="aName" name="name" required maxlength="40" autocomplete="name">
          ${tech ? `
            <div class="auth-2">
              <div><label for="aCenter">서비스센터</label><input id="aCenter" name="center" required maxlength="60" placeholder="예: 강남 서비스센터"></div>
              <div><label for="aNo">사번</label><input id="aNo" name="employee_no" required maxlength="30"></div>
            </div>
            <label for="aPhone">연락처</label><input id="aPhone" name="phone" type="tel" required maxlength="30" autocomplete="tel">
            <p class="auth-note">기사 계정은 관리자가 확인하고 승인하면 상담 요청과 스캔 등록을 쓸 수 있어요.</p>` : ""}` : ""}
        <p class="auth-err" role="alert" hidden></p>
        <button class="primary auth-go">${signup ? "가입하기" : `${tech ? "기사로" : ""} 로그인`.trim()}</button>
        <p class="auth-switch">${signup ? "이미 계정이 있나요? <a href='#' data-mode='login'>로그인</a>" : `처음이라면 <a href='#' data-mode='signup'>${tech ? "기사 회원가입" : "회원가입"}</a>`}</p>
      </form>`;
    dlg.querySelector(".auth-x").onclick = () => dlg.close();
    dlg.querySelectorAll("[data-role]").forEach((b) => (b.onclick = () => { keep(); state.role = b.dataset.role; render(); }));
    dlg.querySelector("[data-mode]").onclick = (e) => { e.preventDefault(); keep(); state.mode = e.target.dataset.mode; render(); };
    const form = dlg.querySelector("form");
    for (const [k, v] of Object.entries(state.values || {})) if (form.elements[k]) form.elements[k].value = v;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const err = dlg.querySelector(".auth-err"), go = dlg.querySelector(".auth-go");
      const f = Object.fromEntries(new FormData(form));
      const miss = [...form.elements].find((i) => i.required && !i.value.trim());
      if (miss) { err.hidden = false; err.textContent = `${dlg.querySelector(`label[for="${miss.id}"]`)?.firstChild.textContent.trim() || "빈 칸"}을(를) 넣어 주세요`; miss.focus(); return; }
      go.disabled = true;
      try {
        const out = signup ? await post("/api/auth/signup", { ...f, role: state.role }) : await post("/api/auth/login", f);
        setAuth(out.token, out.user);
        dlg.close();
        const u = out.user;
        toast(u.role === "technician" && u.status === "pending" ? "가입했어요. 관리자 승인 후 기사 기능을 쓸 수 있어요"
          : u.role === "admin" ? "관리자 계정으로 로그인했어요" : `${u.name}님, ${ROLE[u.role]} 계정으로 로그인했어요`);
        done(u);
      } catch (ex) {
        err.hidden = false;
        err.textContent = ex.status === 422 && !signup ? "이메일과 비밀번호를 확인해 주세요" : ex.message;
      } finally { go.disabled = false; }
    };
    (form.elements.email.value ? form.elements.password : form.elements.email).focus();
  };
  const keep = () => { const form = dlg.querySelector("form"); if (form) state.values = Object.fromEntries([...new FormData(form)].filter(([k]) => k !== "password")); };
  dlg.addEventListener("close", () => { dlg.remove(); done(null); });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); }); // 바깥 누르면 닫기
  render();
  dlg.showModal();
  return result;
}

export async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* 이미 만료돼도 괜찮다 */ }
  setAuth(null);
  toast("로그아웃했어요");
}

// ---------- 상단 계정 버튼 ----------
export function mountAccount(el) {
  const draw = (u) => {
    if (!u) {
      el.innerHTML = `<button class="acct-btn" id="acctLogin">로그인</button>`;
      el.querySelector("#acctLogin").onclick = () => openLogin();
      return;
    }
    el.innerHTML = `
      <button class="acct-btn on" id="acctBtn" aria-haspopup="menu" aria-expanded="false">
        <span class="acct-ava" aria-hidden="true">${esc(u.name.slice(0, 1))}</span><span class="acct-name">${esc(u.name)}</span>
        <span class="acct-role ${u.role}">${ROLE[u.role]}${u.role === "technician" && u.status !== "approved" ? ` · ${TECH_STATUS[u.status]}` : ""}</span></button>
      <div class="acct-menu" role="menu" hidden>
        <p class="acct-mail">${esc(u.email)}</p>
        <a role="menuitem" href="#/me">${u.role === "customer" ? "내 집" : "내가 맡은 집"}</a>
        ${isTech(u) ? `<a role="menuitem" href="#/t">기사 화면</a>` : ""}
        ${u.role === "admin" ? `<a role="menuitem" href="#/admin">기사 관리</a>` : ""}
        <button role="menuitem" class="acct-out">로그아웃</button>
      </div>`;
    const btn = el.querySelector("#acctBtn"), menu = el.querySelector(".acct-menu");
    const show = (on) => { menu.hidden = !on; btn.setAttribute("aria-expanded", String(on)); };
    btn.onclick = (e) => { e.stopPropagation(); show(menu.hidden); };
    menu.onclick = (e) => { if (e.target.closest("a,button")) show(false); };
    el.querySelector(".acct-out").onclick = () => logout().then(() => { if (/^#\/(me|admin|t)/.test(location.hash)) location.hash = "#/"; });
  };
  document.addEventListener("click", () => { const m = el.querySelector(".acct-menu"); if (m && !m.hidden) { m.hidden = true; el.querySelector("#acctBtn")?.setAttribute("aria-expanded", "false"); } });
  draw(currentUser());
  onAuth(draw);
  // 저장해 둔 로그인이 아직 살아 있는지(정지·승인 상태 바뀜) 서버에 한 번 묻는다
  if (currentUser()) api("/api/auth/me").then((u) => { if (JSON.stringify(u) !== JSON.stringify(currentUser())) setAuth(authToken(), u); }).catch(() => {});
}

// ---------- 화면: 내 집 ----------
export async function myHomes() {
  const u = currentUser();
  if (!u) return needLogin("내 집", "로그인하면 꾸미던 집을 어느 기기에서든 이어서 볼 수 있어요.");
  $app.innerHTML = `
    <div class="page-head"><div><h1>${u.role === "customer" ? "내 집" : "내가 맡은 집"}</h1>
      <p class="sub">${esc(u.name)} · ${esc(u.email)} · ${ROLE[u.role]} 계정${u.role === "technician" ? ` (${TECH_STATUS[u.status]})` : ""}</p></div>
      <a class="btn ghost" href="#/new">새 집 스캔 올리기</a></div>
    ${u.role === "technician" && u.status === "pending" ? `<div class="notice">관리자가 기사 계정을 확인하고 있어요. 승인되면 상담 요청 목록과 스캔 등록을 쓸 수 있어요.</div>` : ""}
    <ul class="homes" id="homes"><li class="muted">불러오는 중…</li></ul>`;
  const ps = await api("/api/me/projects");
  const box = document.getElementById("homes");
  box.innerHTML = ps.length ? ps.slice().reverse().map((p) => `
    <li><a href="#/c/${esc(p.project_id)}?t=${esc(p.share_token)}">
      <b>${esc(p.style?.prompt || "스캔한 집")} <small class="muted">${esc(p.project_id)}</small></b>
      <span>${p.scan.scanned_by === "customer" ? "셀프 스캔" : "기사 방문 스캔"} · 제품 ${p.scene_state.placements.length}개${p.updated_at ? ` · ${timeKo(p.updated_at)} 수정` : ""}</span>
      <span class="go">이어서 꾸미기</span></a></li>`).join("")
    : `<li class="empty">아직 저장한 집이 없어요. 스캔을 올리거나, 꾸미던 집 화면에서 저장을 누르면 여기에 모여요.</li>`;
}

function needLogin(title, why, role = "customer") {
  $app.innerHTML = `<div class="panel gate"><h1>${esc(title)}</h1><p class="sub">${esc(why)}</p>
    <div class="row"><button class="primary" id="gLogin">로그인</button><button class="ghost" id="gSign">${role === "technician" ? "기사 회원가입" : "회원가입"}</button></div></div>`;
  document.getElementById("gLogin").onclick = () => openLogin({ role }).then((x) => x && window.dispatchEvent(new HashChangeEvent("hashchange")));
  document.getElementById("gSign").onclick = () => openLogin({ role, mode: "signup" }).then((x) => x && window.dispatchEvent(new HashChangeEvent("hashchange")));
}

/** 기사 화면 문지기: 승인된 기사·관리자만 통과 */
export function techGate(render) {
  const u = currentUser();
  if (isTech(u)) return render();
  if (u?.role === "technician") {
    $app.innerHTML = `<div class="panel gate"><h1>승인을 기다리고 있어요</h1>
      <p class="sub">${esc(u.center || "")} ${esc(u.name)} 기사님, 가입 신청이 접수됐어요. 관리자가 사번과 소속을 확인하고 승인하면 이 화면을 쓸 수 있어요.</p>
      <div class="row"><button class="ghost" id="gRe">승인됐는지 다시 확인</button></div></div>`;
    document.getElementById("gRe").onclick = guard(async () => {
      const me = await api("/api/auth/me");
      setAuth(authToken(), me);
      if (isTech(me)) render(); else toast(`아직 ${TECH_STATUS[me.status]} 상태예요`);
    });
    return;
  }
  return needLogin("기사 화면", u ? "고객 계정으로는 기사 화면을 쓸 수 없어요. 기사 계정으로 로그인해 주세요." : "상담 요청과 방문 스캔 등록은 승인된 기사 계정으로 로그인해야 볼 수 있어요.", "technician");
}

// ---------- 화면: 기사 관리 (관리자) ----------
export async function adminPage() {
  const u = currentUser();
  if (u?.role !== "admin") return needLogin("기사 관리", "관리자 계정으로 로그인해 주세요.");
  $app.innerHTML = `
    <div class="page-head"><div><h1>기사 관리</h1><p class="sub">기사 회원가입 신청을 확인하고 승인하거나, 그만둔 기사의 이용을 멈춰요.</p></div></div>
    <div class="seg" role="tablist" id="tf">
      ${Object.entries(TECH_STATUS).map(([k, v]) => `<button data-f="${k}">${v} <span class="count" data-n="${k}">0</span></button>`).join("")}</div>
    <div class="panel" style="margin-top:14px"><div class="table-scroll"><table class="techs">
      <thead><tr><th>이름</th><th>서비스센터</th><th>사번</th><th>연락처</th><th>이메일</th><th>가입</th><th></th></tr></thead>
      <tbody id="tb"></tbody></table></div></div>`;
  let filter = "pending", list = [];
  const ACT = { pending: [["approved", "승인", "primary"], ["rejected", "거절", "danger"]],
    approved: [["suspended", "이용 중지", "danger"]], suspended: [["approved", "다시 승인", ""]], rejected: [["approved", "승인", ""]] };
  const draw = () => {
    document.querySelectorAll("#tf [data-f]").forEach((b) => b.classList.toggle("on", b.dataset.f === filter));
    for (const k of Object.keys(TECH_STATUS)) document.querySelector(`[data-n="${k}"]`).textContent = list.filter((t) => t.status === k).length;
    const rows = list.filter((t) => t.status === filter);
    document.getElementById("tb").innerHTML = rows.length ? rows.map((t) => `<tr>
      <td><b>${esc(t.name)}</b></td><td>${esc(t.center)}</td><td>${esc(t.employee_no)}</td><td>${esc(t.phone)}</td><td>${esc(t.email)}</td>
      <td class="muted">${timeKo(t.created_at)}</td>
      <td class="row">${ACT[t.status].map(([s, label, cls]) => `<button class="small ${cls || "ghost"}" data-id="${esc(t.user_id)}" data-s="${s}">${label}</button>`).join("")}</td></tr>`).join("")
      : `<tr><td colspan="7" class="muted">${TECH_STATUS[filter]} 기사가 없어요.</td></tr>`;
    document.querySelectorAll("#tb [data-s]").forEach((b) => (b.onclick = guard(async () => {
      const t = await api(`/api/admin/technicians/${encodeURIComponent(b.dataset.id)}`, { method: "PATCH", body: JSON.stringify({ status: b.dataset.s }) });
      list = list.map((x) => (x.user_id === t.user_id ? t : x));
      toast(`${t.name} 기사: ${TECH_STATUS[t.status]}`);
      draw();
    })));
  };
  document.querySelectorAll("#tf [data-f]").forEach((b) => (b.onclick = () => { filter = b.dataset.f; draw(); }));
  list = await api("/api/admin/technicians");
  if (!list.some((t) => t.status === "pending") && list.length) filter = "approved";
  draw();
}

// ---------- 리모델링 화면: 저장 막대 ----------
const AUTO_EVERY_MS = 10000;
/**
 * 로그인했으면 꾸민 상태를 서버 저장본으로 남긴다.
 * - 자동 저장: 10초마다 바뀐 게 있으면 자동 저장 한 칸을 덮어쓴다 (창을 닫거나 다른 화면으로 갈 때도)
 * - 수동 저장: 저장 버튼이나 Ctrl+S(맥은 ⌘S). 이름 붙인 저장본이 쌓이고, 저장 기록에서 되돌릴 수 있다
 */
export function mountSaveBar(el, pid, shareToken) {
  let can = false, lastAuto = null, busy = false, lastAt = null, why = "";
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  let shown = "";
  const paint = (html, wire) => { if (html !== shown) { shown = html; el.innerHTML = html; wire?.(); } };
  const draw = () => {
    const u = currentUser();
    if (!u) {
      return paint(`<span class="save-state off"><i></i>저장 안 됨</span><button class="small primary" id="svLogin">로그인하고 저장</button>`, () => {
        el.querySelector("#svLogin").onclick = () => openLogin({ reason: "로그인하면 지금 꾸민 집이 서버에 저장되고, 다른 기기에서도 이어서 꾸밀 수 있어요." });
      });
    }
    if (!can) return paint(`<span class="save-state off" title="${esc(why)}"><i></i>${esc(why || "확인 중…")}</span>`);
    // 상태 글자만 바뀔 때는 버튼을 그대로 두고 글자만 고친다
    const state = `<i></i>${busy ? "저장 중…" : lastAt ? `자동 저장됨 ${timeKo(lastAt)}` : "서버에 저장돼요"}`;
    const st = el.querySelector(".save-state.live");
    if (st && el.querySelector("#svNow")) { st.className = `save-state live ${busy ? "busy" : "ok"}`; if (st.innerHTML !== state) st.innerHTML = state; return; }
    paint(`
      <span class="save-state live ${busy ? "busy" : "ok"}" aria-live="polite">${state}</span>
      <button class="small" id="svNow" title="지금 상태를 저장본으로 남겨요 (${mac ? "⌘S" : "Ctrl+S"})">저장 <kbd>${mac ? "⌘S" : "Ctrl+S"}</kbd></button>
      <button class="small ghost" id="svList">저장 기록</button>`, () => {
      el.querySelector("#svNow").onclick = () => manual();
      el.querySelector("#svList").onclick = () => history();
    });
  };
  const version = async () => (await api(`/api/projects/${pid}/version`)).version;
  // 로그인하면: 주인 없는 집이면 내 계정으로 가져오고, 저장할 수 있는지 확인
  const setup = async () => {
    if (!el.isConnected) return dispose();
    can = false; why = ""; lastAuto = null; draw();
    const u = currentUser();
    if (!u) return;
    try {
      if (u.role === "customer") await post(`/api/projects/${pid}/claim`, { share_token: shareToken() });
      const saves = await api(`/api/projects/${pid}/saves`);
      const auto = saves.find((s) => s.kind === "auto" && s.by === u.user_id);
      if (auto) { lastAuto = auto.project_version; lastAt = auto.saved_at; }
      can = true;
    } catch (e) {
      why = e.status === 403 ? (u.role === "customer" ? "다른 계정의 집이라 보기만 돼요" : "맡은 집이 아니라 보기만 돼요") : "저장 상태를 못 읽었어요";
    }
    draw();
    if (can) autoSave();
  };
  const autoSave = async (keepalive = false) => {
    if (!el.isConnected && !keepalive) return dispose();
    // 관리자는 남의 집을 살펴볼 뿐이라 자동 저장하지 않는다 (수동 저장은 된다)
    if (!can || busy || !currentUser() || currentUser().role === "admin") return;
    try {
      const v = await version();
      if (v === lastAuto) return;
      busy = !keepalive; draw();
      const s = await api(`/api/projects/${pid}/saves`, { method: "POST", body: JSON.stringify({ kind: "auto" }), keepalive });
      lastAuto = s.project_version; lastAt = s.saved_at;
    } catch { /* 다음 차례에 다시 */ }
    finally { busy = false; draw(); }
  };
  const manual = guard(async (label) => {
    if (!currentUser()) { openLogin({ reason: "저장하려면 로그인해 주세요." }); return; }
    if (!can) { toast(why || "이 집은 저장할 수 없어요", true); return; }
    busy = true; draw();
    try {
      const s = await post(`/api/projects/${pid}/saves`, { kind: "manual", ...(label ? { label } : {}) });
      lastAt = s.saved_at;
      toast(`‘${s.label}’로 저장했어요`);
      await autoSave();
      return s;
    } finally { busy = false; draw(); }
  });
  const history = () => {
    document.querySelector("dialog.saves")?.remove();
    const dlg = document.createElement("dialog");
    dlg.className = "saves";
    dlg.setAttribute("aria-labelledby", "svH");
    dlg.innerHTML = `<div class="saves-in">
      <button type="button" class="auth-x" aria-label="닫기">×</button>
      <h2 id="svH">저장 기록</h2>
      <p class="sub">되돌리면 그 저장본의 제품 배치·마감재·영역·실측값으로 바뀌어요. 지금 상태는 자동 저장에 먼저 남겨 둬요.</p>
      <form class="row" id="svForm"><input name="label" maxlength="60" placeholder="이름 붙여 저장 (예: 화이트 주방 1안)" aria-label="저장본 이름"><button class="primary">저장</button></form>
      <ul class="saves-list" id="svUl"><li class="muted">불러오는 중…</li></ul></div>`;
    document.body.append(dlg);
    dlg.querySelector(".auth-x").onclick = () => dlg.close();
    dlg.addEventListener("close", () => dlg.remove());
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    const load = guard(async () => {
      const list = await api(`/api/projects/${pid}/saves`);
      dlg.querySelector("#svUl").innerHTML = list.length ? list.map((s) => `
        <li><div><span><b>${esc(s.label)}</b>${s.kind === "auto" ? ` <span class="badge src">10초마다</span>` : ""}</span>
          <span class="muted">${timeKo(s.saved_at)} · ${esc(s.by_name)} · 제품 ${s.placements}개 · 영역 ${s.zones}개</span></div>
          <span class="spacer"></span>
          <button class="small ghost" data-restore="${esc(s.save_id)}">되돌리기</button>
          ${s.kind === "manual" ? `<button class="small danger" data-del="${esc(s.save_id)}" aria-label="${esc(s.label)} 지우기">지우기</button>` : ""}</li>`).join("")
        : `<li class="muted">아직 저장본이 없어요. 위에서 이름을 붙여 저장해 보세요.</li>`;
      dlg.querySelectorAll("[data-restore]").forEach((b) => (b.onclick = guard(async () => {
        if (b.dataset.armed !== "1") { b.dataset.armed = "1"; b.textContent = "한 번 더 누르면 되돌려요"; b.classList.add("primary"); return; }
        b.disabled = true;
        const auto = list.find((x) => x.kind === "auto");
        if (b.dataset.restore !== auto?.save_id) await autoSave(); // 되돌리기 전 상태를 자동 저장에 남김
        await post(`/api/projects/${pid}/saves/${encodeURIComponent(b.dataset.restore)}/restore`, {});
        lastAuto = null;
        toast("저장본으로 되돌렸어요");
        dlg.close();
        autoSave();
      })));
      dlg.querySelectorAll("[data-del]").forEach((b) => (b.onclick = guard(async () => {
        if (b.dataset.armed !== "1") { b.dataset.armed = "1"; b.textContent = "정말 지우기"; return; }
        await api(`/api/projects/${pid}/saves/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" });
        load();
      })));
    });
    dlg.querySelector("#svForm").onsubmit = async (e) => {
      e.preventDefault();
      const label = e.target.label.value.trim();
      await manual(label);
      e.target.label.value = "";
      load();
    };
    dlg.showModal();
    load();
  };
  const onKey = (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") { e.preventDefault(); manual(); }
  };
  const onHide = () => { if (document.visibilityState === "hidden") autoSave(true); };
  document.addEventListener("keydown", onKey);
  document.addEventListener("visibilitychange", onHide);
  const timer = setInterval(() => autoSave(), AUTO_EVERY_MS);
  const off = onAuth(() => setup());
  let gone = false;
  // 다른 화면으로 가면 타이머·키·로그인 감시를 모두 끊는다. 떠나기 직전 상태는 한 번 자동 저장
  function dispose() {
    if (gone) return;
    gone = true;
    clearInterval(timer); off(); document.removeEventListener("keydown", onKey); document.removeEventListener("visibilitychange", onHide);
  }
  cleanup.push(() => { autoSave(true); dispose(); });
  setup();
}
