// 왼쪽 필터의 순수 로직: 적용된 조건을 칩으로 풀기, 하나씩 빼기, 금액 읽기·쓰기. 화면과 떨어져 있어 node로 테스트한다.
import { AXES, INSTALL_STEP } from "./options.js";

export const SIZE_W = [["0-650", "폭 650 mm 이하"], ["650-850", "폭 650~850 mm"], ["850-99999", "폭 850 mm 이상"]];
export const SIZE_H = [["0-900", "높이 900 mm 이하"], ["900-1800", "높이 900~1,800 mm"], ["1800-99999", "높이 1,800 mm 이상"]];
const sizeLabel = (list, v) => list.find(([k]) => k === v)?.[1] || v;
const AXIS_ORDER = AXES.map((a) => a.key);

/** 원 → "10만원", "1,650만원", "1.3억원" */
export function wonText(v) {
  if (v >= 1e8) return `${+(v / 1e8).toFixed(1)}억원`;
  return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만원`;
}
/** 가격 범위 → "200만 ~ 300만원". 한쪽이 범위 끝(atMin·atMax)이면 "300만원 이하", "200만원 이상" */
export function budgetText(b) {
  if (b.atMin && !b.atMax) return `${wonText(b.hi)} 이하`;
  if (b.atMax && !b.atMin) return `${wonText(b.lo)} 이상`;
  return `${wonText(b.lo).replace(/원$/, "")} ~ ${wonText(b.hi)}`;
}

/** 직접 넣은 금액(만 원) → 원. 범위(scale.lo~hi) 안으로 맞추고 간격(step)에 붙인다. 숫자가 아니면 null */
export function parseManwon(text, scale) {
  const digits = String(text ?? "").replace(/[,\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(digits)) return null;
  const snapped = Math.round((Number(digits) * 1e4) / scale.step) * scale.step;
  return Math.min(scale.hi, Math.max(scale.lo, snapped));
}

/** 접힌 '상세 필터' 안에서 고른 조건 수 (설치 방식·품목·가격은 밖에 늘 보이므로 세지 않는다) */
export function detailCount(st) {
  return Object.keys(st.sel || {}).filter((k) => k !== "install").length + (st.fW ? 1 : 0) + (st.fH ? 1 : 0);
}

/** 지금 어떤 조건으로 보고 있는지: [{key, label}] (화면 순서대로). names.cat = {품목 코드: 이름} */
export function appliedFilters(st, names = {}) {
  const sel = st.sel || {}, out = [];
  if (sel.install) out.push({ key: "sel:install", label: sel.install });
  if (st.cat) out.push({ key: "cat", label: names.cat?.[st.cat] || st.cat });
  if (st.budget) out.push({ key: "budget", label: budgetText(st.budget) });
  Object.keys(sel).filter((k) => k !== "install").sort((a, b) => AXIS_ORDER.indexOf(a) - AXIS_ORDER.indexOf(b))
    .forEach((k) => out.push({ key: `sel:${k}`, label: String(sel[k]) }));
  if (st.fW) out.push({ key: "fW", label: sizeLabel(SIZE_W, st.fW) });
  if (st.fH) out.push({ key: "fH", label: sizeLabel(SIZE_H, st.fH) });
  if (st.q) out.push({ key: "q", label: `“${st.q}”` });
  return out;
}

/** 조건 하나를 뺀 새 상태. 품목을 빼면 그 품목의 상세 조건도 같이 뺀다 */
export function clearFilter(st, key) {
  const sel = { ...(st.sel || {}) };
  if (key.startsWith("sel:")) { delete sel[key.slice(4)]; return { ...st, sel }; }
  if (key === "cat") return { ...st, cat: "", sel: sel.install ? { install: sel.install } : {} };
  if (key === "budget") return { ...st, budget: null };
  if (key === "fW" || key === "fH" || key === "q") return { ...st, [key]: "" };
  return { ...st };
}

/** 설치 방식별 제품 수 (빌트인 핏은 빌트인) */
export function installCounts(variants) {
  const n = { 빌트인: 0, 일반: 0 };
  for (const v of variants) { const k = INSTALL_STEP[v.install_type]; if (k) n[k] += 1; }
  return n;
}
