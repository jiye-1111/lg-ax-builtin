// 조합 추천: 가전 종류 + 목표 가격 + 분위기 → 서버가 만든 조합 2~3개 → 누르면 3D에 한 번에.
// 제품·자리·가격은 서버 코드가 계산한다. 여기서는 보여 주고 고르게만 한다.
import { esc, api, post, guard, toast } from "./core.js";

export const COMBO_CATS = [
  ["refrigerator", "냉장고"], ["kimchi_refrigerator", "김치냉장고"], ["water_purifier", "정수기"], ["air_conditioner", "에어컨"],
  ["air_purifier", "공기청정기"], ["tv", "TV"], ["washer", "세탁기"], ["dryer", "건조기"], ["styler", "스타일러"],
  ["dishwasher", "식기세척기"], ["cooktop", "인덕션"], ["microwave", "전자레인지"], ["wine_cellar", "와인셀러"], ["dehumidifier", "제습기"],
];
const MOODS = ["호텔 같은 침실", "내추럴 우드 거실", "모던 다크", "밝은 미니멀"];
const man = (v) => `${Math.round(v / 1e4).toLocaleString("ko-KR")}만 원`;

export function comboPopHtml() {
  return `<section class="combo-pop" id="comboPop" role="dialog" aria-label="추천 배치" hidden>
    <div class="keys-head"><b>추천 배치</b><button class="ghost small" id="comboClose">닫기</button></div>
    <p class="hint-sm">원하는 가전과 목표 가격만 고르면, 이 집 구조에 맞춰 가구·가전·벽지까지 조합으로 놓아 볼게요.</p>
    <h4>가전</h4>
    <div class="chips combo-cats" id="comboCats">${COMBO_CATS.map(([k, v]) => `<button class="chip" data-cat="${k}" aria-pressed="false">${v}</button>`).join("")}</div>
    <h4>목표 가격 <span class="muted">LG 가전 합계</span></h4>
    <label class="combo-budget"><input id="comboBudget" type="number" inputmode="numeric" min="10" max="10000" step="10" placeholder="예) 300"><span>만 원</span></label>
    <h4>분위기 <span class="muted">선택</span></h4>
    <input id="comboMood" maxlength="200" autocomplete="off" placeholder="예) 호텔 같은 침실">
    <div class="chips combo-moods">${MOODS.map((m) => `<button class="chip" data-mood="${esc(m)}">${esc(m)}</button>`).join("")}</div>
    <button class="primary combo-go" id="comboGo">조합 만들기</button>
    <div id="comboRes" aria-live="polite"></div>
  </section>`;
}

const diffText = (cb) => {
  if (cb.budget_diff == null) return "";
  const d = cb.budget_diff;
  if (Math.abs(d) < 50000) return "목표 가격과 거의 같아요";
  return d < 0 ? `목표보다 ${man(-d)} 낮아요` : `목표보다 ${man(d)} 높아요`;
};

export function comboCardsHtml(d) {
  if (!d.combos?.length) return `<p class="hint-sm">이 집 구조로는 조합을 못 만들었어요. 가구를 치우거나 다른 분위기로 해 보세요.</p>`;
  return `<ol class="combo-list">${d.combos.map((cb) => {
    const lg = cb.items.filter((i) => i.kind === "lg"), decor = cb.items.filter((i) => i.kind === "decor");
    const names = [...new Set(decor.map((i) => i.name))];
    return `<li class="combo" data-combo="${esc(cb.combo_id)}">
      <header><span class="palette">${cb.palette.map((h) => `<i style="background:${esc(h)}"></i>`).join("")}</span>
        <b>${esc(cb.name)}</b><span class="tag">${esc(cb.plan_label)}</span></header>
      <p class="why">${esc(cb.why)}</p>
      ${lg.length ? `<ul class="combo-lg">${lg.map((i) => `<li><b>${esc(i.name)}</b><span class="price">${i.price ? man(i.price) : ""}</span>
        ${i.why?.length ? `<small>${esc(i.why.join(" · "))}</small>` : ""}</li>`).join("")}</ul>` : ""}
      ${cb.missing?.length ? `<p class="hint-sm">${esc(cb.missing.join(", "))}은 이 집에 들어갈 자리가 없어 뺐어요.</p>` : ""}
      <p class="combo-decor">${esc(names.join(" · "))}${cb.finishes?.wall ? ` · 벽 ${esc(cb.finishes.wall.name)}` : ""}${cb.finishes?.floor ? ` · 바닥 ${esc(cb.finishes.floor.name)}` : ""}</p>
      <details class="combo-tips"><summary>이렇게 살리면 좋아요</summary><ul>${cb.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></details>
      <footer>${lg.length ? `<span class="total">${man(cb.lg_total)}</span><span class="muted">${esc(diffText(cb))}</span>` : ""}
        <button class="primary small" data-apply="${esc(cb.combo_id)}">이 조합으로 꾸미기</button></footer>
    </li>`;
  }).join("")}</ol>`;
}

// root 안의 [data-apply] 버튼을 묶는다. 적용하면 onApplied(응답)
export function bindComboCards(root, pid, onApplied) {
  root.querySelectorAll("[data-apply]").forEach((b) => (b.onclick = guard(async () => {
    b.disabled = true; b.textContent = "놓는 중…";
    try {
      const r = await post(`/api/projects/${pid}/combos/${b.dataset.apply}/apply`, {});
      root.querySelectorAll(".combo").forEach((li) => li.classList.toggle("on", li.dataset.combo === b.dataset.apply));
      toast(r.combo.skipped?.length ? `‘${r.combo.name}’ 조합을 넣었어요. ${r.combo.skipped.join(", ")}은 지금 자리에 안 들어가 뺐어요` : `‘${r.combo.name}’ 조합을 넣었어요`);
      await onApplied(r);
    } finally { b.disabled = false; b.textContent = "이 조합으로 꾸미기"; }
  })));
}

export function mountComboPop(pid, onApplied) {
  const pop = document.getElementById("comboPop"), btn = document.getElementById("comboBtn");
  if (!pop || !btn) return;
  const cats = new Set();
  const open = (v) => { pop.hidden = !v; btn.setAttribute("aria-expanded", v); };
  btn.onclick = () => open(pop.hidden);
  document.getElementById("comboClose").onclick = () => open(false);
  pop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); open(false); btn.focus(); } });
  pop.querySelectorAll("[data-cat]").forEach((b) => (b.onclick = () => {
    const k = b.dataset.cat;
    if (cats.has(k)) cats.delete(k); else if (cats.size < 6) cats.add(k); else { toast("가전은 6개까지 골라 주세요", true); return; }
    b.setAttribute("aria-pressed", cats.has(k)); b.classList.toggle("on", cats.has(k));
  }));
  const mood = document.getElementById("comboMood");
  pop.querySelectorAll("[data-mood]").forEach((b) => (b.onclick = () => { mood.value = b.dataset.mood; }));
  const go = document.getElementById("comboGo"), res = document.getElementById("comboRes");
  go.onclick = guard(async () => {
    const man10k = Number(document.getElementById("comboBudget").value);
    if (man10k && (man10k < 10 || man10k > 10000)) { toast("목표 가격은 10만 ~ 1억 원 사이로 적어 주세요", true); return; }
    if (!cats.size && !mood.value.trim()) { toast("가전을 고르거나 분위기를 적어 주세요", true); return; }
    go.disabled = true; go.textContent = "이 집에 맞춰 짜는 중…";
    try {
      const d = await post(`/api/projects/${pid}/combos`, { categories: [...cats], budget: man10k ? man10k * 10000 : null, prompt: mood.value.trim() });
      res.innerHTML = comboCardsHtml(d) + `<button class="ghost small combo-clear" id="comboClear">넣은 조합 빼기</button>`;
      bindComboCards(res, pid, onApplied);
      document.getElementById("comboClear").onclick = guard(async () => {
        const r = await api(`/api/projects/${pid}/combos/applied`, { method: "DELETE" });
        res.querySelectorAll(".combo").forEach((li) => li.classList.remove("on"));
        toast("넣은 조합을 뺐어요");
        await onApplied(r);
      });
    } finally { go.disabled = false; go.textContent = "조합 만들기"; }
  });
}
