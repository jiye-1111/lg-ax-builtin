// 가구 색 고르기: 가구마다 색을 바꿀 수 있는 부위(상판·다리·쿠션 등)와 그 부위에 어울리는 색.
// 색만 고른다. 브랜드나 제품 정보는 없다. 색 이름과 구성은 실제로 파는 가구의 색 선택지를 따랐다
// (소파 커버: 라이트 베이지·미디엄 그레이·다크 그린·블루·그레이 터쿼이즈, 주방 문짝: 오트 크림·얼그레이·베이지 오크·헤이즐넛·에스프레소).
// 색 값은 화면용 근사색이다. 출처는 docs/furniture-looks.md
// tex: "wood"면 나뭇결 무늬를 같이 입힌다. metal: 금속 느낌 (스테인리스·브라스).

const W = (name, hex) => ({ name, hex, tex: "wood" });
const WOOD = [
  W("화이트 오크", "#D8C3A0"), W("베이지 오크", "#CBB799"), W("앰버 오크", "#B5854F"), W("오크", "#A27A52"),
  W("헤이즐넛", "#8F6A45"), W("월넛", "#7A5638"), W("에스프레소", "#4A3528"),
  { name: "화이트", hex: "#ECE9E3" }, { name: "블랙", hex: "#2E2D2C" },
];
const FABRIC = [
  { name: "아이보리", hex: "#E6E0D4" }, { name: "라이트 베이지", hex: "#D6CBB8" }, { name: "베이지 그레이", hex: "#BDB5A8" },
  { name: "미디엄 그레이", hex: "#8E8F8F" }, { name: "차콜", hex: "#4A4D50" }, { name: "세이지 그린", hex: "#93A088" },
  { name: "다크 그린", hex: "#44574A" }, { name: "블루", hex: "#5F7896" }, { name: "그레이 터쿼이즈", hex: "#6E8A8C" },
  { name: "캐러멜", hex: "#B88A5E" },
];
const PAINT = [
  { name: "화이트", hex: "#E8E5DF" }, { name: "크림", hex: "#E9DFC9" }, { name: "브라운 베이지", hex: "#B9A58C" },
  { name: "그레이 그린", hex: "#8E9A8B" }, { name: "청록 그레이", hex: "#6E8A8C" }, { name: "더스티 블루", hex: "#8FA6B8" },
  { name: "네이비", hex: "#2E3B55" }, { name: "버건디", hex: "#6E2F37" }, { name: "차콜", hex: "#3F4245" },
];
// 장 문짝: 무광 색 + 나무 무늬
const DOOR = [
  { name: "화이트", hex: "#E8E5DF" }, { name: "오트 크림", hex: "#E9DFC9" }, { name: "그레이지", hex: "#C9C0B2" },
  { name: "얼그레이", hex: "#A9A7A2" }, { name: "세이지", hex: "#8E9A8B" }, { name: "더스티 블루", hex: "#8FA6B8" },
  { name: "딥 틸", hex: "#2F5D62" }, { name: "차콜", hex: "#3F4245" }, W("베이지 오크", "#CBB799"), W("헤이즐넛", "#8F6A45"),
];
// 상판: 주방 상판으로 많이 나오는 세라믹·인조대리석·원목 색 + 스테인리스
const TOP = [
  { name: "화이트", hex: "#E4E1DA" }, { name: "아이보리", hex: "#E3D9C6" }, { name: "베이지", hex: "#CDBFA8" },
  { name: "라이트 그레이", hex: "#BEBDB8" }, { name: "콘크리트 그레이", hex: "#8C8B87" }, { name: "차콜", hex: "#3A3B3D" },
  { name: "블랙", hex: "#232323" }, W("오크 원목", "#B9996F"), W("월넛 원목", "#6F4E37"), { name: "스테인리스", hex: "#C5C8CB", metal: true },
];
const LEG = [
  { name: "블랙", hex: "#2A2A2B" }, { name: "화이트", hex: "#ECE9E3" }, { name: "실버", hex: "#C5C8CB", metal: true },
  { name: "브라스", hex: "#B08D57", metal: true }, W("화이트 오크", "#D8C3A0"), W("오크", "#A27A52"), W("월넛", "#7A5638"),
];
const FRAME = [
  { name: "화이트", hex: "#E8E5DF" }, { name: "크림", hex: "#E9DFC9" }, { name: "그레이지", hex: "#C9C0B2" },
  { name: "다크 그레이", hex: "#5A5B5D" }, { name: "블랙", hex: "#2A2A2B" }, W("오크", "#CBB799"), W("월넛", "#7A5638"),
];
const HANDLE = [
  { name: "블랙", hex: "#2A2A2B" }, { name: "실버", hex: "#C5C8CB", metal: true }, { name: "브라스", hex: "#B08D57", metal: true },
  { name: "화이트", hex: "#ECE9E3" },
];
const METAL = [{ name: "스테인리스", hex: "#C5C8CB", metal: true }, { name: "화이트", hex: "#ECE9E3" }, { name: "블랙", hex: "#2E2D2C" }];

// 모델 → 색을 바꿀 수 있는 부위들. P(부위 이름, 화면에 보이는 말, 그 부위의 재질 이름들, 팔레트)
// 맨 앞 부위가 대표 색이다 (예전에 고른 가구 색은 여기에 입혀진다).
// field: 서버에서 그 색을 따로 두는 자리. 장 상판 색은 top_hex에 둔다 (끼워 넣은 가전 위 상판 덮개가 같이 쓴다. decor.py TOP_COLOUR_SKUS)
const P = (key, label, mats, colours, field = null) => ({ key, label, mats, colours, field });
const SLAB = P("top", "상판", ["stone"], TOP, "top_hex");
const CAB = [P("door", "문", ["white"], DOOR), SLAB];
const GLAZED = [P("frame", "창틀", ["frame"], FRAME), P("handle", "손잡이", ["handle"], HANDLE)];
const PARTS = {
  sofa: [P("fabric", "패브릭", ["fabric"], FABRIC), P("cushion", "쿠션", ["cushion"], FABRIC), P("leg", "다리", ["leg"], LEG)],
  chair: [P("seat", "방석", ["seat"], FABRIC), P("back", "등받이", ["back"], FABRIC), P("frame", "다리", ["frame"], LEG)],
  bed: [P("head", "헤드", ["head"], FABRIC), P("frame", "프레임", ["frame"], FABRIC), P("bedding", "이불", ["bedding"], FABRIC), P("throw", "담요", ["throw"], FABRIC)],
  rug: [P("rug", "러그", ["wool"], FABRIC)],
  lamp: [P("shade", "갓", ["shade"], FABRIC), P("pole", "기둥", ["pole"], HANDLE)],
  plant: [P("pot", "화분", ["pot"], PAINT)],
  table: [P("top", "상판", ["top"], WOOD), P("leg", "다리", ["leg"], LEG)],
  coffee: [P("top", "상판", ["top"], WOOD), P("leg", "다리", ["leg"], LEG)],
  desk: [P("top", "상판", ["top"], WOOD), P("leg", "다리", ["leg"], LEG)],
  shelf: [P("body", "몸통", ["body"], WOOD)],
  partition: [P("body", "살", ["oak"], WOOD)],
  tvstand: [P("body", "몸통", ["body"], WOOD), P("door", "문", ["door"], WOOD)],
  dresser: [P("body", "서랍", ["body"], DOOR), P("top", "상판", ["top"], WOOD), P("leg", "다리", ["leg"], LEG)],
  door: [P("leaf", "문짝", ["door_leaf"], DOOR), P("frame", "문틀", ["frame"], FRAME), P("handle", "손잡이", ["handle"], HANDLE)],
  storage: [P("door", "문", ["white"], DOOR), P("niche", "안쪽 칸", ["niche"], WOOD)],
  wardrobe: [P("door", "문", ["white"], DOOR)], tallcab: [P("door", "문", ["white"], DOOR)],
  basecab: CAB, island: CAB, sink: [...CAB, P("faucet", "수전", ["faucet"], HANDLE)],
  islandtable: [P("body", "몸통", ["island_wood"], WOOD), SLAB],
  hood: [P("body", "후드", ["steel"], METAL)], islandhood: [P("body", "후드", ["steel"], METAL)],
  wall: [P("wall", "벽", ["white", "plaster"], PAINT)], window: GLAZED, glassdoor: GLAZED,
};

/** 이 모델에서 색을 바꿀 수 있는 부위들 [{key, label, mats, colours}]. 없으면 [] */
export const partsOf = (model) => PARTS[model] ?? [];
/** 대표 부위(맨 앞)의 재질 이름들. 칠할 데가 없으면 [] */
export const paintParts = (model) => PARTS[model]?.[0].mats ?? [];
/** 대표 부위에 고를 수 있는 색 [{name, hex}] */
export const coloursFor = (model) => PARTS[model]?.[0].colours ?? [];
/** 3D에서 누른 면의 재질 이름 → 그 부위. 색을 못 바꾸는 면이면 null */
export const partOfMaterial = (model, mat) => partsOf(model).find((q) => q.mats.includes(mat)) ?? null;
/** 저장된 색을 부위별로 모은다: 대표 색(hex)은 맨 앞 부위, 장 상판은 topHex, 나머지는 part_colors. {부위: hex} */
export function partColours(model, hex, partColors, topHex = null) {
  const parts = partsOf(model), out = {};
  if (!parts.length) return out;
  if (hex) out[parts[0].key] = hex;
  for (const q of parts.slice(1)) {
    const v = (q.field === "top_hex" && topHex) || partColors?.[q.key]; // 스캔한 장은 상판 색도 part_colors에
    if (v) out[q.key] = v;
  }
  return out;
}
/** 놓은 가구(placement)에 저장된 부위별 색 */
export const placedColours = (model, p) => partColours(model, p.hex, p.part_colors, p.top_hex);

/** 스캔 가구가 그려지는 모델 이름: 허리 높이 수납장은 하부장 */
export const COUNTER_MAX_M = 1.0;
/** 나란히 붙어 있는 같은 종류 가구 (싱크대 하부장처럼 여러 칸으로 스캔된 한 줄). 색은 한 줄을 같이 바꾼다. */
const TOUCH_GAP_M = 0.08;
// 한 줄로 짜 넣는 수납만 같이 칠한다. 의자·탁자·소파는 붙어 있어도 하나씩 쓰는 가구라 고른 것만 바꾼다
const RUN_LOOKS = new Set(["basecab", "storage", "tallcab", "wardrobe", "sink"]);
export function runOf(objects, id) {
  const first = objects.find((o) => o.object_id === id);
  if (!first) return [];
  const look = (o) => lookOf(o.category, o.bbox_m.h);
  if (!RUN_LOOKS.has(look(first))) return [first.object_id];
  const touch = (a, b) => Math.hypot(a.position[0] - b.position[0], a.position[2] - b.position[2])
    <= (Math.max(a.bbox_m.w, a.bbox_m.d) + Math.max(b.bbox_m.w, b.bbox_m.d)) / 2 + TOUCH_GAP_M;
  const run = [first];
  for (let i = 0; i < run.length; i++)
    for (const o of objects)
      if (!run.includes(o) && look(o) === look(first) && touch(run[i], o)) run.push(o);
  return run.map((o) => o.object_id);
}

export const lookOf = (category, heightM) => (category === "storage" && heightM <= COUNTER_MAX_M ? "basecab" : category);
