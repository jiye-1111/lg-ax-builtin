// 첫 안내: 화면을 어둡게 하고 하우니가 메뉴를 하나씩 밝게 짚으며 무슨 기능인지 알려 준다.
// steps: [{ sel, title, text, cta? }] — sel이 없으면 가운데 말풍선, 화면에 없거나 숨은 메뉴는 건너뛴다.
// cta: { label, run } 마지막 단계에서 '직접 해 보기' 같은 버튼.
import { esc } from "./core.js";

const SEEN_KEY = "lgb.tour.v1";
const NARROW_W = 640; // 이보다 좁으면 말풍선을 화면 폭에 맞춘다

export const tourSeen = () => { try { return localStorage.getItem(SEEN_KEY) === "1"; } catch { return true; } };
const markSeen = () => { try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* 저장 못 해도 안내는 끝낸다 */ } };

const visible = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";

/** 안내를 띄운다. 끝내면(다 보거나 건너뛰면) 다시 안 뜨게 적어 둔다. 돌려주는 함수로 강제로 닫을 수 있다. */
export function startTour(steps, { face = "", onEnd } = {}) {
  const list = steps.filter((s) => !s.sel || visible(document.querySelector(s.sel)));
  if (!list.length) return () => {};
  const root = document.createElement("div");
  root.className = "tour";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-label", "화면 안내");
  root.innerHTML = `<div class="tour-hole" aria-hidden="true"></div><div class="tour-tip" tabindex="-1"></div>`;
  document.body.append(root);
  const hole = root.querySelector(".tour-hole"), tip = root.querySelector(".tour-tip");
  let i = 0;
  const place = () => {
    const el = list[i].sel && document.querySelector(list[i].sel);
    root.classList.toggle("center", !el);
    if (!el) {
      const tw = Math.min(380, innerWidth - 24);
      Object.assign(hole.style, { left: `${innerWidth / 2}px`, top: `${innerHeight / 2}px`, width: "0px", height: "0px" });
      Object.assign(tip.style, { width: `${tw}px`, left: `${(innerWidth - tw) / 2}px`, top: `${Math.max(12, (innerHeight - (tip.offsetHeight || 220)) / 2)}px` });
      return;
    }
    const r = el.getBoundingClientRect(), pad = 6;
    Object.assign(hole.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px` });
    // 말풍선: 밝힌 곳 옆 빈 쪽으로 (오른쪽 → 왼쪽 → 아래 → 위). 좁은 화면은 가로 꽉 채워 위·아래 넓은 쪽에
    const W = innerWidth, H = innerHeight, narrow = W < NARROW_W, gap = 12;
    const tw = narrow ? W - 24 : Math.min(340, W - 24);
    tip.style.width = `${tw}px`;
    const th = tip.offsetHeight || 180;
    let x, y;
    if (narrow) {
      x = 12;
      if (r.bottom + gap + th < H - 12) y = r.bottom + gap;
      else if (r.top - gap - th > 12) y = r.top - gap - th;
      else y = r.top + r.height / 2 > H / 2 ? 12 : H - th - 12; // 밝힌 곳이 크면 그 반대쪽 끝에 겹쳐 둔다
    }
    else if (r.right + gap + tw < W) { x = r.right + gap; y = r.top; }
    else if (r.left - gap - tw > 0) { x = r.left - gap - tw; y = r.top; }
    else if (r.bottom + gap + th < H) { x = r.left; y = r.bottom + gap; }
    else { x = r.left; y = r.top - gap - th; }
    x = Math.max(12, Math.min(x, W - tw - 12));
    y = Math.max(12, Math.min(y, H - th - 12));
    Object.assign(tip.style, { left: `${x}px`, top: `${y}px`, width: `${tw}px` });
  };
  const show = () => {
    const s = list[i], last = i === list.length - 1;
    tip.innerHTML = `<div class="tour-face" aria-hidden="true">${face}</div>
      <div class="tour-body"><p class="tour-n">${i + 1} / ${list.length}</p><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p>
        <div class="tour-acts"><button class="ghost small" data-t="skip">${last ? "닫기" : "건너뛰기"}</button><span class="spacer"></span>
          ${i ? `<button class="ghost small" data-t="prev">이전</button>` : ""}<button class="primary small" data-t="next">${s.cta ? esc(s.cta.label) : last ? "시작하기" : "다음"}</button></div></div>`;
    tip.querySelectorAll("[data-t]").forEach((b) => (b.onclick = () => go(b.dataset.t)));
    if (s.sel) document.querySelector(s.sel)?.scrollIntoView?.({ block: "nearest" });
    place();
    requestAnimationFrame(place);
    tip.querySelector('[data-t="next"]').focus({ preventScroll: true });
  };
  const end = () => {
    markSeen();
    removeEventListener("resize", place);
    root.removeEventListener("keydown", onKey);
    root.remove();
    onEnd?.();
  };
  const go = (t) => {
    if (t === "next" && list[i].cta) { const run = list[i].cta.run; end(); run(); return; }
    if (t === "skip" || (t === "next" && i === list.length - 1)) return end();
    i = Math.max(0, Math.min(list.length - 1, i + (t === "prev" ? -1 : 1)));
    show();
  };
  const onKey = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); end(); }
    else if (e.key === "ArrowRight") go("next");
    else if (e.key === "ArrowLeft") go("prev");
  };
  root.addEventListener("keydown", onKey);
  addEventListener("resize", place);
  show();
  return end;
}
