// 에너지 소비효율등급 배지: 라벨처럼 다섯 칸 눈금에 그 등급 칸만 칠하고 옆에 "1등급".
// 값은 LGE.COM 스펙 표에 적힌 것만 온다. 등급이 없는 제품은 아무것도 그리지 않는다.
// 에어컨(냉방·난방)·워시타워(세탁·건조)처럼 등급이 둘이면 parts로 오고, 이름을 붙여 나란히 그린다.
const GRADES = [1, 2, 3, 4, 5];

function one(grade, name = "") {
  const steps = GRADES.map((n) => `<i${n === grade ? ' class="on"' : ""}></i>`).join("");
  const text = `${name ? name + " " : ""}${grade}등급`;
  return `<span class="energy" data-grade="${grade}" role="img" aria-label="에너지 소비효율 ${text}"><span class="energy-steps" aria-hidden="true">${steps}</span><b>${text}</b></span>`;
}

export function energyBadge(grade, parts) {
  if (GRADES.includes(grade)) return one(grade);
  const named = Object.entries(parts || {}).filter(([, g]) => GRADES.includes(g));
  return named.length ? `<span class="energy-set">${named.map(([name, g]) => one(g, name)).join("")}</span>` : "";
}
