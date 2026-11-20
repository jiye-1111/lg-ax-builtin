// 단계별 옵션 필터: 설치 방식 → 종류 → 도어 수 → 용량 → 화면 크기 → 도어 재질 → 색상 순으로 좁혀 간다.
// 순서는 LGE.COM·삼성닷컴 상세필터를 따랐고, 값은 카탈로그의 LGE.COM 스펙(options)에서 온다. 화면과 떨어진 순수 함수.

const bucket = (edges, unit, open) => (n) => {
  if (typeof n !== "number") return null;
  for (let i = 0; i < edges.length; i++) {
    if (n < edges[i] || (i === 0 && n <= edges[0])) return i === 0 ? `${edges[0]}${unit} 이하` : `${edges[i - 1]}~${edges[i]}${unit}`;
  }
  return `${edges[edges.length - 1]}${unit} ${open}`;
};
const exact = (unit) => (n) => (n == null ? null : `${n}${unit}`);
// 값 종류가 많은 숫자 축은 구간으로 묶는다 (용량 구간은 LGE.COM 냉장고 필터와 같다)
const literBucket = bucket([300, 400, 600, 800], "L", "이상");
const kgBucket = bucket([10, 15, 20], "kg", "이상");
const cmBucket = bucket([110, 140, 170, 200], "cm", "이상");

export const INSTALL_STEP = { built_in: "빌트인", built_in_look: "빌트인", freestanding: "일반" };

export const AXES = [
  { key: "install", label: "설치 방식", of: (v) => INSTALL_STEP[v.install_type] || null, order: ["빌트인", "일반"] },
  { key: "kind", label: "종류", of: (v) => v.options?.kind ?? null },
  { key: "doors", label: "도어 수", of: (v) => v.options?.doors ?? null, numeric: true },
  { key: "capacity_l", label: "용량", of: (v) => v.options?.capacity_l ?? null, numeric: true, fine: exact("L"), coarse: literBucket },
  { key: "wash_kg", label: "세탁 용량", of: (v) => v.options?.wash_kg ?? null, numeric: true, fine: exact("kg"), coarse: kgBucket },
  { key: "dry_kg", label: "건조 용량", of: (v) => v.options?.dry_kg ?? null, numeric: true, fine: exact("kg"), coarse: kgBucket },
  { key: "capacity", label: "용량", of: (v) => v.options?.capacity ?? null, numeric: true },
  { key: "screen_cm", label: "화면 크기", of: (v) => v.options?.screen_cm ?? null, numeric: true, fine: exact("cm"), coarse: cmBucket },
  { key: "door_type", label: "문 여는 방향", of: (v) => v.options?.door_type ?? null },
  { key: "door_material", label: "도어 재질", of: (v) => v.options?.door_material ?? null },
  { key: "color", label: "색상", of: (v) => v.color ?? null },
];
const MAX_FINE = 6; // 이보다 값이 많으면 구간으로 묶는다
const firstNumber = (s) => { const m = String(s).match(/[\d.]+/); return m ? Number(m[0]) : Infinity; };

/** variants: 한 종류(카테고리)의 SKU 목록, sel: {축: 고른 값}.
 *  앞 단계에서 고른 것으로 좁힌 뒤, 남은 제품에서 값이 둘 이상 갈리는 축만 다음 단계로 보여 준다.
 *  더 이상 맞지 않는 선택은 버린다. keys를 주면 그 축만 쓴다. → { steps: [{key,label,picked,values:[{label,count}]}], remaining, sel } */
export function optionSteps(variants, sel = {}, keys = null) {
  let remaining = variants;
  const steps = [], kept = {};
  for (const ax of AXES) {
    if (keys && !keys.includes(ax.key)) continue;
    const raw = remaining.map((v) => ax.of(v));
    const distinct = new Set(raw.filter((x) => x != null));
    const fmt = ax.fine ? (distinct.size > MAX_FINE ? ax.coarse : ax.fine) : (x) => x;
    const labels = raw.map((x) => (x == null ? null : fmt(x)));
    const counts = new Map(), lowest = new Map();
    labels.forEach((l, i) => {
      if (l == null) return;
      counts.set(l, (counts.get(l) || 0) + 1);
      const n = typeof raw[i] === "number" ? raw[i] : firstNumber(raw[i]);
      lowest.set(l, Math.min(lowest.get(l) ?? Infinity, n));
    });
    if (counts.size < 2) continue;
    const values = [...counts].map(([label, count]) => ({ label, count }));
    if (ax.order) values.sort((a, b) => ax.order.indexOf(a.label) - ax.order.indexOf(b.label));
    else if (ax.numeric) values.sort((a, b) => lowest.get(a.label) - lowest.get(b.label));
    else values.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "ko"));
    const picked = counts.has(sel[ax.key]) ? sel[ax.key] : null;
    steps.push({ key: ax.key, label: ax.label, picked, values });
    if (picked) { kept[ax.key] = picked; remaining = remaining.filter((_, i) => labels[i] === picked); }
  }
  return { steps, remaining, sel: kept };
}
