// 왼쪽 필터의 순수 로직 (apps/web/js/filters.js). 실행: node --test tests/web/
import test from "node:test";
import assert from "node:assert/strict";
import { appliedFilters, clearFilter, detailCount, installCounts, matchesQuery, parseManwon, wonText } from "../../apps/web/js/filters.js";
import { colorName, optionSteps } from "../../apps/web/js/options.js";

const NAMES = { cat: { refrigerator: "냉장고" } };
const EMPTY = { cat: "", sel: {}, budget: null, fW: "", fH: "", q: "" };

test("아무것도 안 골랐으면 적용된 필터가 없다", () => {
  assert.deepEqual(appliedFilters(EMPTY, NAMES), []);
  assert.equal(detailCount(EMPTY), 0);
});

test("적용된 필터는 화면 순서대로: 설치 방식 → 품목 → 가격 → 상세 조건 → 검색어", () => {
  const st = { cat: "refrigerator", sel: { color: "화이트", install: "일반", doors: "4도어" }, budget: { lo: 1000000, hi: 3000000 }, fW: "0-650", fH: "", q: "오브제" };
  assert.deepEqual(appliedFilters(st, NAMES).map((c) => [c.key, c.label]), [
    ["sel:install", "일반"],
    ["cat", "냉장고"],
    ["budget", "100만 ~ 300만원"],
    ["sel:doors", "4도어"],
    ["sel:color", "화이트"],
    ["fW", "폭 650 mm 이하"],
    ["q", "“오브제”"],
  ]);
});

test("상세 필터 개수는 접힌 칸 안의 조건만 센다 (설치 방식·품목·가격은 빼고)", () => {
  const st = { ...EMPTY, cat: "refrigerator", sel: { install: "빌트인", color: "화이트" }, budget: { lo: 0, hi: 1 }, fH: "900-1800" };
  assert.equal(detailCount(st), 2);
});

test("칩의 ×를 누르면 그 조건만 빠지고 원래 상태는 그대로다", () => {
  const st = { ...EMPTY, cat: "refrigerator", sel: { install: "일반", color: "화이트" }, budget: { lo: 1, hi: 2 }, fW: "0-650" };
  assert.deepEqual(clearFilter(st, "sel:color").sel, { install: "일반" });
  assert.equal(clearFilter(st, "budget").budget, null);
  assert.equal(clearFilter(st, "fW").fW, "");
  assert.deepEqual(st.sel, { install: "일반", color: "화이트" });
});

test("품목을 빼면 그 품목에만 있던 상세 조건도 같이 빠진다 (설치 방식은 남는다)", () => {
  const st = { ...EMPTY, cat: "refrigerator", sel: { install: "일반", doors: "4도어" } };
  const next = clearFilter(st, "cat");
  assert.equal(next.cat, "");
  assert.deepEqual(next.sel, { install: "일반" });
});

test("금액은 만 원 단위로 읽기 쉽게", () => {
  assert.equal(wonText(100000), "10만원");
  assert.equal(wonText(16500000), "1,650만원");
  assert.equal(wonText(100000000), "1억원");
  assert.equal(wonText(125000000), "1.3억원");
});

test("직접 넣은 금액(만 원)은 범위 안으로 맞추고 간격에 붙인다", () => {
  const scale = { lo: 100000, hi: 6000000, step: 100000 };
  assert.equal(parseManwon("150", scale), 1500000);
  assert.equal(parseManwon("1,234", scale), 6000000);
  assert.equal(parseManwon("3", scale), 100000);
  assert.equal(parseManwon("157", scale), 1600000);
  assert.equal(parseManwon("", scale), null);
  assert.equal(parseManwon("abc", scale), null);
});

test("설치 방식 개수: 빌트인 핏은 빌트인으로 센다", () => {
  const vs = [{ install_type: "built_in" }, { install_type: "built_in_look" }, { install_type: "freestanding" }, { install_type: null }];
  assert.deepEqual(installCounts(vs), { 빌트인: 2, 일반: 1 });
});

test("가격 칩: 한쪽 끝이 범위 끝에 닿아 있으면 이하·이상으로 짧게", () => {
  const chip = (budget) => appliedFilters({ ...EMPTY, budget }, NAMES)[0].label;
  assert.equal(chip({ lo: 200000, hi: 3000000, atMin: true }), "300만원 이하");
  assert.equal(chip({ lo: 2000000, hi: 5100000, atMax: true }), "200만원 이상");
  assert.equal(chip({ lo: 2000000, hi: 3000000 }), "200만 ~ 300만원");
});

test("설치 방식 개수는 목록과 같은 단위(모델)로 센다: 색만 다른 제품은 하나", () => {
  const vs = [{ fam: "a", install_type: "built_in" }, { fam: "a", install_type: "built_in" }, { fam: "a", install_type: "built_in" },
    { fam: "b", install_type: "freestanding" }, { fam: "b", install_type: "freestanding" }];
  assert.deepEqual(installCounts(vs), { 빌트인: 1, 일반: 1 });
});

test("옵션 칩의 숫자도 모델 수다", () => {
  const vs = [{ fam: "a", options: { doors: 4 } }, { fam: "a", options: { doors: 4 } }, { fam: "b", options: { doors: 2 } }];
  const doors = optionSteps(vs, {}).steps.find((st) => st.key === "doors");
  assert.deepEqual(doors.values, [{ label: 2, count: 1 }, { label: 4, count: 1 }]);
});

test("같은 색은 이름이 조금 달라도 한 칩으로 모은다", () => {
  for (const raw of ["오브제컬렉션 베이지 / 베이지", "오브제컬렉션 베이지", "오브제컬렉션 베이지 베이지", "베이지"]) assert.equal(colorName(raw), "베이지");
  assert.equal(colorName("오브제컬렉션 에센스화이트"), "에센스 화이트");
  assert.equal(colorName("오브제컬렉션 에센스 화이트 / 에센스 화이트"), "에센스 화이트");
  assert.equal(colorName("오브제컬렉션 클레이 민트 / 베이지"), "클레이 민트 / 베이지");
  assert.equal(colorName("프라임 실버"), "프라임 실버");
  assert.equal(colorName(null), null);
  const vs = [{ fam: "a", color: "오브제컬렉션 베이지 / 베이지" }, { fam: "b", color: "오브제컬렉션 베이지" }, { fam: "c", color: "화이트" }];
  assert.deepEqual(optionSteps(vs, {}).steps.find((st) => st.key === "color").values.map((v) => v.label), ["베이지", "화이트"]);
});

test("검색은 띄어 쓴 낱말이 모두 들어 있으면 찾는다", () => {
  const fridge = { words: ["냉장고", "LG 디오스 AI 오브제컬렉션 냉장고 (832L)", "S834MEE30", "양문형", "베이지"], liters: [832] };
  assert.ok(matchesQuery("양문형 냉장고", fridge));
  assert.ok(matchesQuery("  디오스   s834 ", fridge));
  assert.ok(!matchesQuery("양문형 세탁기", fridge));
  assert.ok(matchesQuery("", fridge));
});

test("검색에 용량을 어림수로 넣으면 그 근처 용량을 찾는다 (800 → 800리터대)", () => {
  const fridge = { words: ["냉장고", "LG 디오스 냉장고 (832L)"], liters: [832] };
  assert.ok(matchesQuery("양문형 냉장고 800".replace("양문형 ", ""), fridge));
  assert.ok(matchesQuery("832", fridge));
  assert.ok(!matchesQuery("냉장고 600", fridge));
});
