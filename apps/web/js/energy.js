// 에너지 소비효율등급 배지: 라벨처럼 다섯 칸 눈금에 그 등급 칸만 칠하고 옆에 "1등급".
// 값은 LGE.COM 스펙 표에 적힌 것만 온다. 등급이 없는 제품은 아무것도 그리지 않는다.
export function energyBadge(grade) {
  if (![1, 2, 3, 4, 5].includes(grade)) return "";
  const steps = [1, 2, 3, 4, 5].map((n) => `<i${n === grade ? ' class="on"' : ""}></i>`).join("");
  return `<span class="energy" data-grade="${grade}" role="img" aria-label="에너지 소비효율 ${grade}등급"><span class="energy-steps" aria-hidden="true">${steps}</span><b>${grade}등급</b></span>`;
}
