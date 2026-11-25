// 가구 색 고르기: 가구마다 칠할 부분(모델의 재질 이름)과 그 재질에 어울리는 색.
// 색만 고른다. 브랜드나 제품 정보는 없다. 색 구성은 요즘 주방 문짝·소파에서 많이 보이는
// 흙빛 계열(브라운 베이지, 그레이 그린, 다크 베이지, 청록 그레이)을 넣었다.

const WOOD = [
  { name: "화이트 오크", hex: "#D8C3A0" }, { name: "오크", hex: "#A27A52" }, { name: "티크", hex: "#8F6A45" },
  { name: "월넛", hex: "#7A5638" }, { name: "다크 월넛", hex: "#4A3528" }, { name: "화이트", hex: "#ECE9E3" },
  { name: "그레이 워시", hex: "#A8A198" }, { name: "블랙", hex: "#2E2D2C" },
];
const FABRIC = [
  { name: "아이보리", hex: "#E6E0D4" }, { name: "그레이지", hex: "#BDB5A8" }, { name: "다크 베이지", hex: "#A8947C" },
  { name: "세이지", hex: "#93A088" }, { name: "청록 그레이", hex: "#6E8A8C" }, { name: "네이비", hex: "#3A4660" },
  { name: "테라코타", hex: "#B8674A" }, { name: "머스터드", hex: "#C9A24B" }, { name: "차콜", hex: "#4A4D50" },
];
const PAINT = [
  { name: "화이트", hex: "#E8E5DF" }, { name: "크림", hex: "#E9DFC9" }, { name: "브라운 베이지", hex: "#B9A58C" },
  { name: "그레이 그린", hex: "#8E9A8B" }, { name: "청록 그레이", hex: "#6E8A8C" }, { name: "더스티 블루", hex: "#8FA6B8" },
  { name: "네이비", hex: "#2E3B55" }, { name: "버건디", hex: "#6E2F37" }, { name: "차콜", hex: "#3F4245" },
];

const METAL = [{ name: "스테인리스", hex: "#C5C8CB" }, { name: "화이트", hex: "#ECE9E3" }, { name: "블랙", hex: "#2E2D2C" }];
// 상판: 주방 상판으로 많이 나오는 세라믹·인조대리석·원목 색
const STONE = [
  { name: "화이트", hex: "#E4E1DA" }, { name: "아이보리", hex: "#E3D9C6" }, { name: "베이지", hex: "#CDBFA8" },
  { name: "라이트 그레이", hex: "#BEBDB8" }, { name: "콘크리트 그레이", hex: "#8C8B87" }, { name: "차콜", hex: "#3A3B3D" },
  { name: "블랙", hex: "#232323" }, { name: "오크 원목", hex: "#B9996F" }, { name: "월넛 원목", hex: "#6F4E37" },
];

// 모델 → [칠할 재질 이름들, 팔레트]
const PARTS = {
  sofa: [["sofa", "sofa_seat"], FABRIC], chair: [["seat"], FABRIC], bed: [["headboard"], FABRIC], rug: [["wool"], FABRIC], lamp: [["shade"], FABRIC],
  table: [["oak"], WOOD], coffee: [["oak"], WOOD], shelf: [["oak"], WOOD], dresser: [["oak"], WOOD], partition: [["oak"], WOOD],
  tvstand: [["walnut", "oak"], WOOD], door: [["door_leaf"], WOOD],
  storage: [["white"], PAINT], basecab: [["white"], PAINT], island: [["white"], PAINT], islandtable: [["island_wood"], WOOD], hood: [["steel"], METAL], islandhood: [["steel"], METAL], sink: [["white"], PAINT], tallcab: [["white"], PAINT],
  wardrobe: [["white"], PAINT], desk: [["white"], PAINT], wall: [["white", "plaster"], PAINT], window: [["white"], PAINT], glassdoor: [["white"], PAINT],
};
// 상판 색을 몸통과 따로 고르는 가구 (서버 decor.py TOP_COLOUR_SKUS와 같은 목록)
const TOPS = { islandtable: [["stone"], STONE], island: [["stone"], STONE], basecab: [["stone"], STONE], sink: [["stone"], STONE] };
/** 이 모델의 상판 재질 이름들. 상판이 없으면 [] */
export const topParts = (model) => TOPS[model]?.[0] ?? [];
/** 이 모델 상판에 고를 수 있는 색 [{name, hex}] */
export const topColoursFor = (model) => TOPS[model]?.[1] ?? [];

/** 이 모델에서 색을 입힐 재질 이름들. 칠할 데가 없으면 [] */
export const paintParts = (model) => PARTS[model]?.[0] ?? [];
/** 이 모델에 고를 수 있는 색 [{name, hex}] */
export const coloursFor = (model) => PARTS[model]?.[1] ?? [];
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
