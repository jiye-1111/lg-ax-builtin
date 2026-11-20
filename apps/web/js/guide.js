// 리모델링 화면 안내: 3단계 진행 표시, 설치 적합성 검사 카드. 판정은 서버가 계산한 값만 쓴다.
import { esc, shownVerdict } from "./core.js";

const WORST = { fit: 0, conditional: 1, unknown: 2, no_fit: 3 };
const worst = (list) => list.reduce((a, v) => (WORST[v] > WORST[a] ? v : a), "fit");

/** 지금 어디까지 했는지 (공간 확인 → 제품 고르기 → 설치 확인). state: done | current | todo | warn */
/**
 * 3단계 진행. 단계마다 직접 해야 넘어간다 (앞 단계를 안 했으면 뒤 단계는 체크하지 않는다).
 * flow: { space: 공간 확인을 눌렀는지, order: 구매·설치 신청까지 봤는지 } (화면 상태로 저장)
 */
export function stepState(project, armed, flow = {}) {
  const pls = project?.scene_state?.placements || [];
  const placed = pls.length > 0;
  const bad = pls.some((p) => p.verdict === "no_fit");
  const space = !!flow.space, pick = space && placed, check = pick && !bad && !!flow.order;
  const steps = [
    { key: "scan", label: "공간 확인", sub: space ? "스캔한 우리 집" : "벽·문·창이 맞나요?", done: space },
    { key: "pick", label: "제품 고르기", sub: armed ? "놓을 자리 누르기" : "골라서 3D에 놓기", done: pick },
    { key: "check", label: "설치 확인", sub: bad && pick ? "다시 놓기 필요" : "구매 및 설치 신청", done: check, warn: bad && pick },
  ];
  let seenCurrent = false;
  return steps.map((s) => {
    let state = s.done ? "done" : "todo";
    if (!s.done && !seenCurrent) { seenCurrent = true; state = s.warn ? "warn" : "current"; }
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
const VERDICT = { fit: "적합", conditional: "적합", no_fit: "부적합", unknown: "판정 불가" };

export function fitRows(placement) {
  const reasons = placement?.reasons || [];
  return GROUPS.map((g) => {
    const mine = reasons.filter((r) => g.codes.includes(r.code));
    if (g.optional && !mine.length) return null;
    return { label: g.label, verdict: worst(mine.map((r) => r.verdict)), why: [...new Set(mine.map((r) => r.label))].join(" · ") };
  }).filter(Boolean);
}

const BANNER = { fit: "설치 가능합니다!", conditional: "설치 가능합니다!", no_fit: "이 자리에는 설치하기 어려워요", unknown: "판정할 정보가 부족해요" };

/** 놓은 제품 하나의 설치 확인 카드. life: 서버 life-check의 그 제품 값({daylight, wifi}), 없으면 그 줄을 뺀다 */
export function fitCardHtml(placement, life = null) {
  // 놓을 수 없는 것만 알린다: 조건부는 적합으로, 이유 문구는 '불가' 줄에만
  const v = shownVerdict(placement.verdict in VERDICT ? placement.verdict : "unknown");
  const rows = fitRows(placement).map((r) => { const rv = shownVerdict(r.verdict); return { ...r, verdict: rv, why: rv === "no_fit" ? r.why : "", word: VERDICT[rv] }; });
  // 채광·와이파이는 판정이 아니라 그 자리 정보로만 보여 준다
  for (const [k, label] of [["daylight", "채광"], ["wifi", "와이파이"]]) {
    const x = life?.[k];
    if (x) rows.push({ label, verdict: x.status === "unknown" ? "unknown" : "info", why: x.label, word: "", life: x.status === "unknown" ? k : "" });
  }
  const scan = (placement.reasons || []).some((r) => r.code === "scan_based");
  return `<section class="fit-card v-${v}" aria-label="설치 확인 결과">
    <header><span class="mark" aria-hidden="true">${v === "fit" ? "✓" : v === "no_fit" ? "✕" : "!"}</span><h3>${BANNER[v]}</h3></header>
    <ul>${rows.map((r) => `<li class="v-${r.verdict}"><span class="dot" aria-hidden="true"></span><span class="what">${esc(r.label)}${r.why ? `<small>${esc(r.why)}</small>` : ""}</span>${r.life ? `<button class="small ghost" data-life="${r.life}">정하기</button>` : `<b>${esc(r.word)}</b>`}</li>`).join("")}</ul>
    <details class="fit-note"><summary>더 알아두기</summary>전원·배관 위치와 옆·뒤 여유는 설치 기사가 방문해서 확인해요.${scan ? " 치수는 스캔값 기준이에요." : ""}</details>
  </section>`;
}

export const VERDICT_LABEL = VERDICT;
