// 하우니가 먼저 건네는 것들: 내게 맞는 가전 묻기(눌러서 답하기), 꾸민 집에 더하면 좋은 것.
// 무엇을 권할지·어디에 놓을지·어떤 제품인지는 서버가 계산한다. 여기서는 묻고 보여 주기만 한다.
import { esc } from "./core.js";

const PEOPLE = [["1인", "혼자 살아요"], ["2인", "2인 가구"], ["3인", "3인 가족"], ["4인", "4인 가족"], ["5인 이상", "5인 가족"]];
const LIFE = [["맞벌이", "맞벌이"], ["아기", "아기가 있어요"], ["반려동물", "반려동물과 살아요"], ["장 몰아 보기", "장은 몰아서 봐요"], ["김장", "김장을 해요"]];

export function personaHtml() {
  return `<p>몇 가지만 눌러 주시면 생활에 맞는 LG 가전을 골라 드릴게요.</p>
    <form class="persona" novalidate>
      <fieldset><legend>함께 사는 사람</legend><div class="chips">${PEOPLE.map(([k, v], i) => `<button type="button" class="chip" data-people="${esc(v)}" aria-pressed="false">${esc(k)}</button>`).join("")}</div></fieldset>
      <fieldset><legend>생활 <span class="muted">해당하는 것 모두</span></legend><div class="chips">${LIFE.map(([k, v]) => `<button type="button" class="chip" data-life="${esc(v)}" aria-pressed="false">${esc(k)}</button>`).join("")}</div></fieldset>
      <fieldset><legend>예산 <span class="muted">선택</span></legend><label class="combo-budget"><input name="budget" type="number" inputmode="numeric" min="10" max="10000" step="10" placeholder="예) 500"><span>만 원</span></label></fieldset>
      <p class="hint-sm warn" role="alert" hidden></p>
      <button class="primary small" type="submit">가전 추천 받기</button>
    </form>`;
}

/** 폼을 묶는다. 다 고르면 onDone(문장, 예산(원) | null) */
export function bindPersona(root, onDone) {
  const form = root.querySelector(".persona"), warn = form.querySelector("[role=alert]");
  let people = null;
  const life = new Set();
  form.querySelectorAll("[data-people]").forEach((b) => (b.onclick = () => {
    people = people === b.dataset.people ? null : b.dataset.people;
    form.querySelectorAll("[data-people]").forEach((x) => x.setAttribute("aria-pressed", x.dataset.people === people));
  }));
  form.querySelectorAll("[data-life]").forEach((b) => (b.onclick = () => {
    const k = b.dataset.life;
    if (life.has(k)) life.delete(k); else life.add(k);
    b.setAttribute("aria-pressed", life.has(k));
  }));
  form.onsubmit = (e) => {
    e.preventDefault();
    const man = Number(form.elements.budget.value);
    const say = (t) => { warn.textContent = t; warn.hidden = !t; };
    if (!people && !life.size) return say("함께 사는 사람 수나 생활을 하나 이상 눌러 주세요.");
    if (man && (man < 10 || man > 10000)) return say("예산은 10만 ~ 1억 원 사이로 적어 주세요.");
    say("");
    form.querySelectorAll("button, input").forEach((x) => (x.disabled = true));
    onDone([people, ...life].filter(Boolean).join(", "), man ? man * 10000 : null);
  };
}

/** 더하면 좋은 것 목록. thumbOf(item) → 그림 주소 | null */
export function addonsHtml(items, thumbOf) {
  return `<ul class="bot-prods addons">${items.map((it) => {
    const th = thumbOf(it);
    return `<li class="best" data-addon-row="${esc(it.id)}"><span class="ph">${th ? `<img src="${esc(th)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</span>
      <span class="nm"><b>${esc(it.name)}</b><small class="say">${esc(it.text)}</small>${it.price ? `<small>${it.price.toLocaleString("ko-KR")}원</small>` : ""}</span>
      <button class="small primary" data-addon="${esc(it.id)}">더하기</button></li>`;
  }).join("")}</ul>`;
}
