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
  { label: "제품 문 여는 공간", codes: ["front_blocked"] },
  { label: "방문 여닫이", codes: ["door_blocked", "door_swing_assumed"] },
  { label: "방으로 들여오는 길", codes: ["entry_narrow"], optional: true }, // 걸릴 때만 줄을 보인다
  { label: "창 가림", codes: ["covers_window"] },
  { label: "천장 높이", codes: ["ceiling_low", "ceiling_tight"] },
];
// 판정을 바꾸지는 않고 안내만 하는 코드
const NOTES = ["clearance_unknown", "scan_based", "front_space_assumed"];
const VERDICT = { fit: "적합", conditional: "확인 필요", no_fit: "부적합", unknown: "판정 불가" };
const HEAD = { fit: "이 자리에 설치할 수 있어요", conditional: "설치할 수 있지만 확인할 점이 있어요", no_fit: "이 자리에는 설치하기 어려워요", unknown: "판정할 정보가 부족해요" };

export function fitRows(placement) {
  const reasons = placement?.reasons || [];
  return GROUPS.map((g) => {
    const mine = reasons.filter((r) => g.codes.includes(r.code));
    if (g.optional && !mine.length) return null;
    return { label: g.label, verdict: worst(mine.map((r) => r.verdict)), why: [...new Set(mine.map((r) => r.label))].join(" · ") };
  }).filter(Boolean);
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

/**
 * 3D 아래 안내 줄: 공간별 추천과 설치 전 체크리스트.
 * zones: [{ zone_id, name, count, top }] (count: 그 영역에 들어가는 제품 수, top: 첫 번째 제품 이름)
 * check: 서버의 설치 전 확인 목록(install-check) 응답. 없으면 놓은 제품의 판정만 센다.
 */
export function guideBarHtml({ zones, placements, check }) {
  const rec = zones.length
    ? `<p>${zones.map((z) => `<button type="button" class="gb-zone" data-zone="${esc(z.zone_id)}"><b>${esc(z.name)}</b> ${z.count ? `들어가는 제품 ${z.count}개${z.top ? ` · ${esc(z.top)}` : ""}` : "들어가는 제품이 없어요"}</button>`).join("")}</p>`
    : `<p>평면에 영역을 그리면 그 자리에 들어가는 제품을 골라 드려요.</p><button type="button" class="small ghost" data-gb="draw">영역 그리기</button>`;
  const n = placements.length;
  const by = (v) => placements.filter((x) => x.verdict === v).length;
  let sum, site = 0;
  if (!n) sum = "제품을 놓으면 설치 전에 확인할 것을 정리해 드려요.";
  else if (check?.summary) {
    const c = check.summary;
    site = new Set((check.items || []).flatMap((it) => it.checks.filter((k) => k.status === "site").map((k) => k.label))).size;
    sum = [`제품 ${c.products}개`, c.blocked ? `안 들어감 ${c.blocked}` : "", c.check ? `확인 필요 ${c.check}` : "", !c.blocked && !c.check ? "모두 들어가요" : "",
      c.walls_to_measure?.length ? `잴 벽 ${c.walls_to_measure.join(", ")}` : "", site ? `현장 확인 ${site}가지` : ""].filter(Boolean).join(" · ");
  } else {
    sum = [`제품 ${n}개`, by("no_fit") ? `부적합 ${by("no_fit")}` : "", by("conditional") + by("unknown") ? `확인 필요 ${by("conditional") + by("unknown")}` : "",
      by("fit") === n ? "모두 들어가요" : ""].filter(Boolean).join(" · ");
  }
  const tone = !n ? "" : (check?.summary?.blocked || by("no_fit")) ? "no_fit" : (check?.summary?.check || by("conditional") + by("unknown")) ? "conditional" : "fit";
  return `<section class="gb" aria-label="공간별 추천"><h3>공간별 추천</h3>${rec}</section>
    <section class="gb ${tone ? `v-${tone}` : ""}" aria-label="설치 전 체크리스트"><h3>설치 전 체크리스트</h3><p>${esc(sum)}</p>${n ? `<button type="button" class="small ghost" data-gb="check">자세히</button>` : ""}</section>`;
}
