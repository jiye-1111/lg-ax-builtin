// 리모델링 화면 안내: 3단계 진행 표시, 설치 적합성 검사 카드. 판정은 서버가 계산한 값만 쓴다.
import { esc } from "./core.js";

const WORST = { fit: 0, conditional: 1, unknown: 2, no_fit: 3 };
const worst = (list) => list.reduce((a, v) => (WORST[v] > WORST[a] ? v : a), "fit");

/** 지금 어디까지 했는지 (공간 확인 → 제품 고르기 → 설치 확인). state: done | current | todo | warn */
export function stepState(project, armed) {
  const pls = project?.scene_state?.placements || [];
  const placed = pls.length > 0;
  const bad = pls.some((p) => p.verdict === "no_fit");
  const steps = [
    { key: "scan", label: "공간 확인", sub: "스캔한 우리 집", done: true },
    { key: "pick", label: "제품 고르기", sub: armed ? "놓을 자리 누르기" : "골라서 3D에 놓기", done: placed },
    { key: "check", label: "설치 확인", sub: bad ? "다시 놓기 필요" : placed ? "구매 및 설치 신청" : "들어가는지 확인", done: false, warn: bad },
  ];
  let seenCurrent = false;
  return steps.map((s) => {
    let state = s.done ? "done" : "todo";
    if (s.warn) state = "warn";
    if (!s.done && !seenCurrent) { seenCurrent = true; if (state === "todo") state = "current"; }
    return { ...s, state };
  });
}

export function stepperHtml(steps) {
  return steps.map((s, i) => `<li class="step is-${s.state}"${s.state === "current" ? ' aria-current="step"' : ""}>
    <button type="button" data-step="${s.key}"><span class="num" aria-hidden="true">${s.state === "done" ? "✓" : i + 1}</span>
    <span class="txt"><b>${esc(s.label)}</b><small>${esc(s.sub)}</small></span></button></li>`).join("");
}

// 판정 코드 → 검사 카드의 줄. 데이터가 있는 것만 검사한다.
const GROUPS = [
  { label: "놓을 공간", codes: ["dims_unknown", "outside_room", "hits_wall", "clearance_blocked", "tight", "overlaps_object", "overlaps_placement"] },
  { label: "제품 문 여는 공간", codes: ["front_blocked"] },
  { label: "통행 공간", codes: ["passage_narrow"] },
  // 아래는 걸릴 때만 줄을 보인다 (카드를 짧게)
  { label: "방문 여닫이", codes: ["door_blocked", "door_swing_assumed"], optional: true },
  { label: "방으로 들여오는 길", codes: ["entry_narrow"], optional: true },
  { label: "창 가림", codes: ["covers_window"], optional: true },
  { label: "천장 높이", codes: ["ceiling_low", "ceiling_tight"], optional: true },
];
// 판정을 바꾸지는 않고 안내만 하는 코드
const NOTES = ["clearance_unknown", "scan_based", "front_space_assumed"];
const VERDICT = { fit: "적합", conditional: "확인 필요", no_fit: "부적합", unknown: "판정 불가" };

export function fitRows(placement) {
  const reasons = placement?.reasons || [];
  return GROUPS.map((g) => {
    const mine = reasons.filter((r) => g.codes.includes(r.code));
    if (g.optional && !mine.length) return null;
    return { label: g.label, verdict: worst(mine.map((r) => r.verdict)), why: [...new Set(mine.map((r) => r.label))].join(" · ") };
  }).filter(Boolean);
}

const BANNER = { fit: "설치 가능합니다!", conditional: "설치할 수 있어요. 확인할 점이 있어요", no_fit: "이 자리에는 설치하기 어려워요", unknown: "판정할 정보가 부족해요" };
const NOTE_WHY = { clearance_unknown: "옆·뒤 여유 공간은 설치 기사가 방문해서 확인해요", scan_based: "치수는 스캔값 기준이에요",
  front_space_assumed: "문 여는 공간은 보통 필요한 600 mm로 봤어요" };
const LIFE = { ok: "fit", warn: "conditional", unknown: "unknown" };
const LIFE_WORD = { ok: "좋아요", warn: "확인", unknown: "" };

/** 놓은 제품 하나의 설치 확인 카드. life: 서버 life-check의 그 제품 값({daylight, wifi}), 없으면 그 줄을 뺀다 */
export function fitCardHtml(placement, life = null) {
  const v = placement.verdict in VERDICT ? placement.verdict : "unknown";
  const rows = fitRows(placement).map((r) => ({ ...r, word: VERDICT[r.verdict] }));
  // 판정을 조건부로 만든 안내 코드(옆·뒤 여유 모름 등)는 한 줄로 보여서 왜 '확인'인지 알 수 있게
  const noted = (placement.reasons || []).filter((r) => NOTES.includes(r.code) && r.verdict !== "fit");
  if (noted.length) rows.push({ label: "설치 기사 확인", verdict: worst(noted.map((r) => r.verdict)), why: [...new Set(noted.map((r) => NOTE_WHY[r.code] || r.label))].join(" · "), word: "확인" });
  for (const [k, label] of [["daylight", "채광"], ["wifi", "와이파이"]]) {
    const x = life?.[k];
    if (x) rows.push({ label, verdict: LIFE[x.status] || "unknown", why: x.label, word: LIFE_WORD[x.status] || "", life: x.status === "unknown" ? k : "" });
  }
  const scan = (placement.reasons || []).some((r) => r.code === "scan_based");
  return `<section class="fit-card v-${v}" aria-label="설치 확인 결과">
    <header><span class="mark" aria-hidden="true">${v === "fit" ? "✓" : v === "no_fit" ? "✕" : "!"}</span><h3>${BANNER[v]}</h3></header>
    <ul>${rows.map((r) => `<li class="v-${r.verdict}"><span class="dot" aria-hidden="true"></span><span class="what">${esc(r.label)}${r.why ? `<small>${esc(r.why)}</small>` : ""}</span>${r.life ? `<button class="small ghost" data-life="${r.life}">정하기</button>` : `<b>${esc(r.word)}</b>`}</li>`).join("")}</ul>
    <details class="fit-note"><summary>더 알아두기</summary>전원·배관 위치와 옆·뒤 여유는 설치 기사가 방문해서 확인해요.${scan ? " 치수는 스캔값 기준이에요." : ""}</details>
  </section>`;
}

export const VERDICT_LABEL = VERDICT;
