// 화면: 우리 집 가상 리모델링 (제품 배치, 색·재질, 살아 보기)
import { $app, cleanup, LABEL, PURPOSE, CATEGORY, DIM, OBJ, NOTE, esc, mm, api, post, put, toast, guard } from "./core.js";
import { makeViewer } from "./viewer.js";
import { planView, placedSvg } from "./plan.js";
import { wallTable, WALL_HEAD, floorplanBox } from "./pages.js";

export async function customer(pid) {
  $app.innerHTML = `
    <div class="studio" data-tab="sel" data-view="3d">
      <header class="studio-head">
        <div class="studio-title"><h1>우리 집 가상 리모델링</h1><p class="sub" id="sub">불러오는 중…</p></div>
        <div class="seg" role="group" aria-label="보기 전환">
          <button data-view="3d" class="on">3D</button><button data-view="plan">평면</button><button data-view="split">나란히</button></div>
      </header>

      <aside class="lib" data-panel="lib" aria-label="LG 제품">
        <div class="lib-head"><h2>LG 제품</h2><span class="muted" id="libCount"></span></div>
        <input id="q" type="search" placeholder="제품 이름·모델명 검색" aria-label="제품 검색">
        <div class="chips" id="cats"></div>
        <ul class="list" id="lib"></ul>
        <p class="hint-sm">제품을 누른 뒤 3D 바닥이나 평면을 누르세요. 끌어다 놓아도 돼요. 벽 가까이 놓으면 등이 벽에 붙어요.</p>
      </aside>

      <section class="stage" aria-label="우리 집">
        <div class="toolbar">
          <div class="seg" role="group" aria-label="평면 도구">
            <button data-mode="move" class="on" title="제품 놓기·옮기기">놓기·옮기기</button><button data-mode="rect" title="사각형 영역 그리기">영역 □</button><button data-mode="poly" title="다각형 영역 그리기">영역 ⬠</button></div>
          <span class="spacer"></span>
          <div class="seg sims" role="group" aria-label="살아 보기">
            <span class="seg-label">살아 보기</span>
            <button data-sim="" class="on">끄기</button><button data-sim="daylight">☀ 채광</button><button data-sim="wifi">📶 와이파이</button><button data-sim="flow">🚶 동선</button></div>
        </div>
        <div class="canvas">
          <div class="pane plan-pane"><svg class="plan" id="plan" aria-label="평면도"></svg>
            <button class="pip-swap" data-swap="plan">평면 크게</button></div>
          <div class="pane view-pane"><div class="viewer" id="viewer"><span class="hud" id="hud"></span></div>
            <button class="pip-swap" data-swap="3d">3D 크게</button>
            <button class="render-btn" id="render">렌더 이미지</button></div>
          <figure class="render-shot" id="renderBox" hidden><img id="renderImg" alt="렌더 결과"><button class="ghost small" id="renderClose">닫기</button></figure>
        </div>
        <p class="hint" id="hint"></p>
        <div class="sheet" id="simctl"></div>
      </section>

      <aside class="side" aria-label="선택한 제품과 설정">
        <nav class="side-tabs" role="tablist">
          <button data-tab="lib" class="m-only">제품</button>
          <button data-tab="sel">선택</button>
          <button data-tab="list">놓은 제품 <span class="count" id="plCount">0</span></button>
          <button data-tab="finish">마감재</button>
          <button data-tab="zones">추천</button>
          <button data-tab="extra">도면·실측</button>
        </nav>
        <div class="side-body">
          <section data-panel="sel" id="insp"></section>
          <section data-panel="list"><ul class="list" id="pls"></ul></section>
          <section data-panel="finish">
            <h3>벽·바닥</h3><div id="mats"></div>
            <h3 class="gap">스타일</h3><div id="style"></div>
          </section>
          <section data-panel="zones">
            <p class="hint-sm">평면 도구에서 ‘영역 □’로 주방 자리를 그리면, 그 안에 들어가는 제품을 골라 줍니다.</p>
            <ul class="list" id="zones"></ul>
            <select id="zoneSel" aria-label="영역 선택"></select>
            <div id="recs" class="cards"></div>
          </section>
          <section data-panel="extra">
            <p class="hint-sm">스캔만으로도 판정합니다. 도면이나 줄자로 잰 값이 있으면 넣어 주세요. 더 촘촘하게 판정해요.</p>
            <h3>도면 <span class="badge src">선택</span></h3><div id="fpBox"></div>
            <h3 class="gap">벽 실측값 (m) <span class="badge src">선택</span></h3>
            <p class="hint-sm">평면의 벽 번호를 보고, 잰 값만 넣으면 됩니다.</p>
            <div class="table-scroll"><table>${WALL_HEAD}<tbody id="walls"></tbody></table></div>
          </section>
        </div>
      </aside>
    </div>`;
  const studio = $app.querySelector(".studio");
  const setTab = (t) => {
    studio.dataset.tab = t;
    studio.querySelectorAll("[data-tab]").forEach((b) => b.classList?.toggle("on", b.dataset.tab === t));
  };
  studio.querySelectorAll(".side-tabs [data-tab]").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
  setTab(matchMedia("(max-width: 900px)").matches ? "lib" : "sel");
  const setView = (v) => {
    studio.dataset.view = v;
    studio.querySelectorAll(".studio-head [data-view]").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
    viewer?.reframe();
  };
  studio.querySelectorAll(".studio-head [data-view]").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
  studio.querySelectorAll("[data-swap]").forEach((b) => (b.onclick = () => setView(b.dataset.swap)));
  // 3D 안에서 바로 놓기·옮기기·고르기 (plans/virtual-remodel.md S10)
  let drag3d = null;
  const viewer = makeViewer(document.getElementById("viewer"), {
    canDrag: () => mode === "move" && !armed && !armedRouter && !armedMark,
    onHover: (p) => { if (armed && mode === "move") preview({ sku: armed, center_xz: p, yaw_rad: Math.PI / 2 }); },
    onLeave: () => { if (armed) ghost(null); },
    onClick: ({ hit, point }) => {
      if (point && floorAction(point)) return;
      if (hit?.type === "placement") { selPl = hit.id; selObj = null; setTab("sel"); }
      else if (hit?.type === "object") { selObj = hit.id; selPl = null; setTab("sel"); }
      else { selPl = null; selObj = null; }
      draw(); renderInspector(); renderPlacements();
    },
    onDragMove: (id, c) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      if (!x) return;
      drag3d = id; selPl = id; selObj = null;
      preview({ sku: x.sku, center_xz: c, yaw_rad: x.yaw_rad, placement_id: id }, (r) => viewer.setDragVerdict(id, r.verdict));
    },
    onDragEnd: (id, c) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      drag3d = null;
      setTab("sel");
      if (x) patch(id, { center_xz: c, yaw_rad: x.yaw_rad });
    },
    onDropSku: (sku, p) => placeAt(sku, p),
  });
  cleanup.push(() => viewer.dispose());
  const svg = document.getElementById("plan");
  let mode = "move", draft = [], dragging = null, version = -1, zoneSel = null, project, room, zones, pv;
  let armed = null, selPl = null, selObj = null, drag = null, cat = "", catalog = [];
  let sim = "", overlay = "", simState = { date: new Date().toISOString().slice(0, 10), time: "12:00" }, regions = null;
  const prodOf = (sku) => catalog.find((p) => p.sku === sku);
  const HINT = {
    move: "제품을 끌면 옮겨지고, 빈 곳을 끌면 시점이 돌아가요. 고른 뒤 R 키나 오른쪽 버튼으로 돌려요. 스캔된 가구를 누르면 치울 수 있어요.",
    rect: "평면도에서 드래그해 영역을 그리세요 (5cm 단위).",
    poly: "꼭짓점을 차례로 누르고, 첫 점을 다시 누르거나 더블클릭하면 완성됩니다.",
  };
  const setHint = () => {
    document.getElementById("hint").innerHTML = armed ? `<b>${esc(prodOf(armed)?.name || armed)}</b> 3D 바닥이나 평면에서 놓을 자리를 누르세요 · <a href="#" id="unarm">취소</a>` : HINT[mode];
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
    document.getElementById("libCount").textContent = `${items.length}개`;
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
    viewer.setGhost(res && { ...res, hex: prodOf(armed)?.cmf_options[0]?.hex_approx });
  };
  let busy = false, queued = null, lastPreview = null;
  const preview = async (args, onRes) => {
    if (busy) { queued = [args, onRes]; return; }
    busy = true;
    try {
      lastPreview = await post(`/api/projects/${pid}/pose-check`, args);
      if (onRes) onRes(lastPreview);
      else if (lastPreview.size_m && (armed || drag)) ghost(lastPreview);
    } catch { /* 미리 보기 실패는 무시 */ }
    busy = false;
    if (queued) { const [a, cb] = queued; queued = null; preview(a, cb); }
  };

  const placeAt = guard(async (sku, p) => {
    const r = await post(`/api/projects/${pid}/placements`, { sku, center_xz: p, yaw_rad: Math.PI / 2 });
    selPl = r.placement.placement_id; selObj = null; armed = null; ghost(null); setTab("sel");
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
    if (mode !== "move") setView("plan"); // 영역 그리기는 평면에서
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
    toast(`${z.name} 영역을 만들었어요. ‘추천’ 탭에서 들어가는 제품을 확인하세요`); setTab("zones");
    await refresh(true);
  });
  // 바닥을 눌렀을 때 할 일 (평면·3D 공통): 현관·싱크 지정, 공유기 놓기, 제품 놓기
  const floorAction = (p) => {
    if (mode !== "move") return false;
    if (armedMark) {
      const name = armedMark; armedMark = null;
      guard(async () => { project = await put(`/api/projects/${pid}/marks/${name}`, { center_xz: p }); if (sim === "flow") await flowCtl(); })();
      return true;
    }
    if (armedRouter) {
      armedRouter = false;
      guard(async () => { project = await put(`/api/projects/${pid}/router`, { center_xz: p, band }); if (sim === "wifi") await wifiCtl(); })();
      return true;
    }
    if (armed) { placeAt(armed, p); return true; }
    return false;
  };
  svg.onpointerdown = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (mode === "move") {
      if (floorAction(p)) return;
      const g = e.target.closest("[data-pl]");
      if (g) {
        const x = project.scene_state.placements.find((q) => q.placement_id === g.dataset.pl);
        drag = { plid: x.placement_id, sku: x.sku, start: p, orig: x.center_xz, yaw: x.yaw_rad, moved: false };
        selPl = x.placement_id; selObj = null;
        svg.setPointerCapture(e.pointerId);
        setTab("sel"); renderInspector();
        return;
      }
      const o = e.target.closest("[data-obj]");
      selObj = o ? o.dataset.obj : null;
      selPl = null;
      if (selObj) setTab("sel");
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
        <div class="verdict-strip v-${x.verdict}"><span>${LABEL[x.verdict]}</span>${x.wall_id ? `<em>벽 ${esc(x.wall_id)}에 붙임</em>` : ""}</div>
        <h2 class="insp-name">${esc(p.name)}</h2>
        <p class="insp-meta">${esc(x.sku)}${p.demo_only ? ` <span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}</p>
        ${reasons ? `<ul class="reasons">${reasons}</ul>` : `<p class="ok-line">걸리는 것 없이 들어가요.</p>`}
        <div class="tool-row"><button class="small ghost" id="rl" title="왼쪽으로 15° (Shift+R)">⟲ 15°</button><button class="small ghost" id="rr" title="오른쪽으로 15° (R)">⟳ 15°</button>
          <button class="small ghost" id="snap">벽에 붙이기</button><span class="spacer"></span><button class="small danger" id="del" title="Delete">빼기</button></div>
        ${p.cmf_options.length ? `<h3 class="gap">색상 <span class="muted">LGE.COM 옵션</span></h3><div class="swatches">${p.cmf_options.map((o) => `<button class="swatch ${o.color === x.color ? "on" : ""}" data-color="${esc(o.color)}"><i style="background:${esc(o.hex_approx || "#fff")}"></i>${esc(o.color)}</button>`).join("")}</div>` : ""}
        ${p.source_url ? `<a class="src-link" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM 제품 페이지 열기 ↗</a>` : ""}`;
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
      box.innerHTML = `<div class="verdict-strip v-object"><span>스캔된 가구</span><em>${esc(o.object_id)}</em></div>
        <h2 class="insp-name">${esc(OBJ[o.category] || o.category)}</h2>
        <p class="insp-meta">${o.bbox_m.w.toFixed(2)} × ${o.bbox_m.d.toFixed(2)} m · 높이 ${o.bbox_m.h.toFixed(2)} m</p>
        <div class="tool-row"><button class="small" id="hide">${gone ? "되돌리기" : "치우기"}</button></div>
        <p class="hint-sm">치운 가구는 판정과 3D에서 빠져요. 원래 스캔은 그대로 남습니다.</p>`;
      box.querySelector("#hide").onclick = guard(async () => {
        await put(`/api/projects/${pid}/objects/${o.object_id}/hidden`, { hidden: !gone });
        await refresh(true);
      });
      return;
    }
    box.innerHTML = `<div class="insp-empty"><h2>아직 고른 게 없어요</h2>
      <p>3D나 평면에서 놓은 제품이나 스캔된 가구를 누르면 여기에 판정과 조작 버튼이 나와요.</p>
      <ul class="keys"><li><kbd>R</kbd> 15° 돌리기</li><li><kbd>Shift</kbd>+<kbd>R</kbd> 반대로</li><li><kbd>Delete</kbd> 빼기</li><li><kbd>Esc</kbd> 놓기 취소</li></ul></div>`;
  };
  const renderPlacements = () => {
    const pls = project.scene_state.placements;
    document.getElementById("plCount").textContent = pls.length;
    document.getElementById("pls").innerHTML = pls.length ? pls.map((x) => `
      <li data-sel="${esc(x.placement_id || "")}" class="${x.placement_id === selPl ? "on" : ""}">
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i><span style="flex:1">${esc(prodOf(x.sku)?.name || x.sku)}</span><span class="badge ${x.verdict}">${LABEL[x.verdict]}</span></li>`).join("")
      : `<li class="muted">아직 없어요. 제품 목록에서 하나 골라 평면에 놓아 보세요.</li>`;
    document.querySelectorAll("#pls [data-sel]").forEach((li) => (li.onclick = () => { selPl = li.dataset.sel || null; selObj = null; setTab("sel"); draw(); renderInspector(); renderPlacements(); }));
    const gone = project.scene_state.hidden_objects || [];
    if (gone.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">치운 기존 가구 ${gone.length}개 <span class="spacer"></span><button class="small ghost" id="restore">모두 되돌리기</button></li>`);
    const rb = document.getElementById("restore");
    if (rb) rb.onclick = guard(async () => { for (const id of gone) await put(`/api/projects/${pid}/objects/${id}/hidden`, { hidden: false }); await refresh(true); });
  };
  const SWATCH = { wall: ["#F2EFEA", "#E8E4DC", "#D9D4CB", "#C9CFD3", "#3E4247"], floor: ["#C8A27A", "#A67C52", "#E3D5C1", "#8D8D8A", "#5B4636"] };
  const renderMats = () => {
    const m = project.scene_state.materials || {};
    document.getElementById("mats").innerHTML = Object.entries({ wall: "벽", floor: "바닥" }).map(([t, label]) => `
      <div class="mats-row"><span>${label}</span>
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
      document.getElementById("renderImg").src = `/api/projects/${pid}/files/render.png?v=${Date.now()}`;
      document.getElementById("renderBox").hidden = false;
    } finally { e.target.disabled = false; e.target.textContent = "렌더 이미지"; }
  });
  document.getElementById("renderClose").onclick = () => (document.getElementById("renderBox").hidden = true);
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
    if (!drag3d) viewer.setPlacements(project.scene_state.placements, selPl);
  };
  const setOverlay = (html) => {
    overlay = html;
    const g = document.getElementById("overlay");
    if (g) g.innerHTML = html;
    viewer.setOverlay(html, svg.getAttribute("viewBox")?.split(" ").map(Number));
  };

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
  let lastSceneKey = null;
  const refresh = async (force = false) => {
    if (drag || drag3d) return;
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
    // glb(벽·가구·색)는 바뀌었을 때만 다시 받는다. 놓은 제품은 화면에서 직접 그린다.
    const sceneKey = JSON.stringify([project.scene_state.materials, project.scene_state.finish, project.scene_state.hidden_objects, room.walls.map((w) => w.measured)]);
    if (sceneKey !== lastSceneKey) { lastSceneKey = sceneKey; viewer.load(`/api/projects/${pid}/files/scene.glb`); }
    document.getElementById("hud").textContent = `빈 곳 끌기 회전 · 휠 확대 · 제품 끌어 옮기기 · ${project.scene.engine === "blender" ? "Blender" : "치수 박스 미리보기"}`;
  };
  setHint();
  await guard(refresh)(true);
  // 채팅(Claude·Codex) 쪽 변경을 2초마다 확인
  const timer = setInterval(() => refresh().catch(() => {}), 2000);
  cleanup.push(() => clearInterval(timer));
}
