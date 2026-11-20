// 리모델링 화면 안내: 5단계 진행 표시, 설치 적합성 검사 카드. 판정은 서버가 계산한 값만 쓴다.
import { esc } from "./core.js";

const WORST = { fit: 0, conditional: 1, unknown: 2, no_fit: 3 };
const worst = (list) => list.reduce((a, v) => (WORST[v] > WORST[a] ? v : a), "fit");

/** 지금 어디까지 했는지. state: done | current | todo | warn */
export function stepState(project, armed) {
  const pls = project?.scene_state?.placements || [];
  const placed = pls.length > 0;
  const bad = pls.some((p) => p.verdict === "no_fit");
  const checked = placed && !bad;
  const steps = [
    { key: "scan", label: "집 스캔", sub: "공간 확인", done: true },
    { key: "pick", label: "제품 선택", sub: "목록에서 고르기", done: placed || !!armed },
    { key: "place", label: "3D 배치", sub: "위치 조정", done: placed },
    { key: "check", label: "설치 적합성", sub: bad ? "다시 놓기 필요" : "검사", done: checked, warn: bad },
    { key: "order", label: "결과 확인", sub: "구매·설치 신청", done: false },
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
  { label: "제품 본체 공간", codes: ["dims_unknown", "outside_room", "hits_wall", "clearance_blocked", "tight", "overlaps_object", "overlaps_placement"] },
  { label: "문 열림 공간", codes: ["door_blocked", "door_swing_assumed"] },
  { label: "창 가림", codes: ["covers_window"] },
  { label: "천장 높이", codes: ["ceiling_low", "ceiling_tight"] },
];
// 판정을 바꾸지는 않고 안내만 하는 코드
const NOTES = ["clearance_unknown", "scan_based"];
const VERDICT = { fit: "적합", conditional: "확인 필요", no_fit: "부적합", unknown: "판정 불가" };
const HEAD = { fit: "이 자리에 설치할 수 있어요", conditional: "설치할 수 있지만 확인할 점이 있어요", no_fit: "이 자리에는 설치하기 어려워요", unknown: "판정할 정보가 부족해요" };

export function fitRows(placement) {
  const reasons = placement?.reasons || [];
  return GROUPS.map((g) => {
    const mine = reasons.filter((r) => g.codes.includes(r.code));
    return { label: g.label, verdict: worst(mine.map((r) => r.verdict)), why: mine.map((r) => r.label).join(" · ") };
  });
}

/** 놓은 제품 하나의 설치 적합성 검사 결과 카드 */
export function fitCardHtml(placement) {
  const v = placement.verdict in VERDICT ? placement.verdict : "unknown";
  const rows = fitRows(placement);
  const scan = (placement.reasons || []).some((r) => r.code === "scan_based");
  return `<section class="fit-card v-${v}" aria-label="설치 적합성 검사 결과">
    <header><span class="mark" aria-hidden="true">${v === "fit" ? "✓" : v === "no_fit" ? "✕" : "!"}</span>
      <div><h3>설치 적합성 검사</h3><p>${HEAD[v]}</p></div><span class="pill">${VERDICT[v]}</span></header>
    <ul>${rows.map((r) => `<li class="v-${r.verdict}"><span class="dot" aria-hidden="true"></span><span class="what">${esc(r.label)}${r.why ? `<small>${esc(r.why)}</small>` : ""}</span><b>${VERDICT[r.verdict]}</b></li>`).join("")}</ul>
    <p class="fit-note">전원·배관 위치와 옆·뒤 여유는 설치 기사가 방문해서 확인해요.${scan ? " 치수는 스캔값 기준이에요." : ""}</p>
  </section>`;
}

export const VERDICT_LABEL = VERDICT;
