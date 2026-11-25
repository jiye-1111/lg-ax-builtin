import test from "node:test";
import assert from "node:assert/strict";
import { surfaceKind, surfaceLook, finishPart, materialLabel } from "../../apps/web/js/surface.js";

test("재질 글자와 색 이름으로 겉면 종류를 정한다", () => {
  assert.equal(surfaceKind("스테인리스", "오브제컬렉션 실버"), "stainless");
  assert.equal(surfaceKind("스톤 (스테인리스)", "오브제컬렉션 실버"), "stone");
  assert.equal(surfaceKind("글라스", "오브제컬렉션 베이지"), "glass");
  assert.equal(surfaceKind("글라스 (크리스탈)", "오브제컬렉션 핑크"), "glass");
  assert.equal(surfaceKind("미러", "블랙틴트미러"), "glass");
  assert.equal(surfaceKind("미스트 (글라스)", "오브제컬렉션 베이지"), "mist");
  // 메탈: 은빛·그라파이트 색은 금속 결이 보이고, 흰색·베이지는 칠한 강판이라 매끈하게 빛난다
  assert.equal(surfaceKind("네이처 (메탈)", "퓨어"), "brushed");
  assert.equal(surfaceKind("메탈", "프라임 실버"), "brushed");
  assert.equal(surfaceKind("메탈", "다크 그라파이트"), "brushed");
  assert.equal(surfaceKind("메탈", "화이트"), "coated");
  assert.equal(surfaceKind("메탈", "오브제컬렉션 베이지"), "coated");
});

test("재질을 모르면 모델을 건드리지 않는다", () => {
  assert.equal(surfaceKind(null, "화이트"), null);
  assert.equal(surfaceKind("", ""), null);
  assert.equal(surfaceKind("인조가죽", "블랙"), null);
  assert.equal(surfaceLook(null), null);
});

test("금속은 금속답게, 유리는 맑은 겉칠로", () => {
  const steel = surfaceLook("stainless"), glass = surfaceLook("glass"), coated = surfaceLook("coated"), mist = surfaceLook("mist");
  assert.ok(steel.metalness >= 0.9 && steel.roughness < 0.4);
  assert.ok(glass.metalness === 0 && glass.clearcoat === 1 && glass.roughness < 0.15);
  assert.ok(coated.metalness < 0.3 && coated.clearcoat > 0.5);
  assert.ok(mist.roughness > glass.roughness);
  for (const k of ["stainless", "stone", "brushed", "coated", "glass", "mist"]) assert.ok(surfaceLook(k).envMapIntensity >= 0.9, k);
});

test("문짝·앞판에만 입히고, 금속이면 몸통까지", () => {
  assert.equal(finishPart("B332S34.AKOR__door_finish"), "door");
  assert.equal(finishPart("B332S34.AKOR__case_finish"), "case");
  assert.equal(finishPart("DUE6BGE.AKOR__panel_nature_beige"), "door");
  assert.equal(finishPart("W0082GLE.AKOR__trim_finish"), "door");
  assert.equal(finishPart("gasket_black"), null);
  assert.equal(finishPart("door_glass"), null);
  assert.equal(finishPart(undefined), null);
});

test("상세 창에 보일 재질 글자", () => {
  assert.equal(materialLabel({ options: { door_material: "네이처 (메탈)" }, cmf_options: [{ material: null }] }), "네이처 (메탈)");
  assert.equal(materialLabel({ options: {}, cmf_options: [{ material: "글라스" }] }), "글라스");
  assert.equal(materialLabel({ options: {}, cmf_options: [{ material: null }] }), "");
  assert.equal(materialLabel({}), "");
});
