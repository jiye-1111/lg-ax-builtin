// 제품 겉면: LGE.COM 스펙 표의 재질(도어스타일/재질)과 색 이름으로 3D에서 어떻게 빛날지 정한다.
// 재질이 적혀 있지 않은 제품은 모델에 들어 있는 값을 그대로 둔다.

// 메탈 문짝 중 금속 결이 그대로 보이는 색. 그 밖의 메탈(흰색·베이지 등)은 칠한 강판이라 매끈하게 빛난다
const BARE_METAL = /퓨어|실버|그라파이트|샤인|샤이니|스테인/;

/** @returns {"stainless"|"stone"|"brushed"|"coated"|"glass"|"mist"|null} */
export function surfaceKind(material, color) {
  const m = material || "";
  if (m.includes("스테인리스")) return m.includes("스톤") ? "stone" : "stainless";
  if (m.includes("미스트")) return "mist";
  if (m.includes("글라스") || m.includes("미러")) return "glass";
  if (m.includes("메탈")) return BARE_METAL.test(color || "") ? "brushed" : "coated";
  return null;
}

const LOOKS = {
  stainless: { metalness: 1, roughness: 0.2, clearcoat: 0, clearcoatRoughness: 0, envMapIntensity: 1.3 },
  stone: { metalness: 0.9, roughness: 0.42, clearcoat: 0, clearcoatRoughness: 0, envMapIntensity: 1.05 },
  brushed: { metalness: 0.9, roughness: 0.22, clearcoat: 0, clearcoatRoughness: 0, envMapIntensity: 1.3 },
  coated: { metalness: 0.05, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.06, envMapIntensity: 1.1 },
  glass: { metalness: 0, roughness: 0.1, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.2 },
  mist: { metalness: 0, roughness: 0.48, clearcoat: 0.35, clearcoatRoughness: 0.4, envMapIntensity: 0.9 },
};

/** 겉면 종류 → three.js 재질 값 */
export function surfaceLook(kind) {
  return LOOKS[kind] ? { ...LOOKS[kind] } : null;
}

/** 모델 안 재질 이름이 마감 면인지: 문짝·앞판 "door", 몸통 "case", 그 밖(손잡이·패킹 등)은 null */
export function finishPart(name) {
  if (!name) return null;
  if (/__case_finish$/.test(name)) return "case";
  if (/__(door|trim)_finish$|__panel_/.test(name)) return "door";
  return null;
}

/** 금속 문짝은 몸통도 같은 강판이다. 유리는 문짝에만 붙는다 */
export function coversCase(kind) {
  return kind === "stainless" || kind === "stone" || kind === "brushed" || kind === "coated";
}

/** 상세 창에 보일 재질 글자 (없으면 "") */
export function materialLabel(product) {
  return product?.options?.door_material || product?.cmf_options?.[0]?.material || "";
}
