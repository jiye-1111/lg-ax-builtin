// 와이파이 전파 계산에 쓰는 표. 나중에 실측으로 맞출 수 있게 값만 따로 모아 둔다.
// 단위: dB, 길이 m. 손실 순서는 2.4 / 5 / 6 GHz.

export const BANDS = ["2.4", "5", "6"];
// 대표 채널 가운데 주파수(MHz): 2.4 GHz 6번, 5 GHz 36번, 6 GHz 37번
export const FREQ_MHZ = { "2.4": 2437, 5: 5180, 6: 6135 };
export const DEFAULT_WIDTH_MHZ = { "2.4": 20, 5: 80, 6: 160 };
export const WIDTHS_MHZ = [20, 40, 80, 160];

// t_ref: 기준 두께. null이면 두께 보정을 하지 않는다 (코팅 유리, 금속).
// refl: 벽에 부딪혀 튕겨 나갈 때 잃는 세기. er: 유전율(파동 보기용)
export const MATERIALS = {
  drywall: { ko: "석고보드 벽", t_ref: 0.1, loss: [3, 4, 5], refl: 12, er: 2.5 },
  wood: { ko: "나무 문·합판", t_ref: 0.04, loss: [3, 5, 6], refl: 12, er: 2 },
  glass: { ko: "유리", t_ref: 0.006, loss: [2, 3, 4], refl: 10, er: 6 },
  double_glass: { ko: "복층 유리", t_ref: 0.024, loss: [4, 7, 8], refl: 9, er: 6 },
  lowe_glass: { ko: "로이 유리", t_ref: null, loss: [25, 35, 40], refl: 2, er: 6 },
  brick: { ko: "벽돌 벽", t_ref: 0.1, loss: [8, 12, 14], refl: 8, er: 4 },
  concrete: { ko: "콘크리트 벽", t_ref: 0.15, loss: [15, 22, 25], refl: 6.5, er: 5.3 },
  reinforced_concrete: { ko: "철근콘크리트 벽", t_ref: 0.2, loss: [25, 35, 40], refl: 6, er: 5.3 },
  bathroom: { ko: "욕실 벽", t_ref: 0.15, loss: [18, 25, 28], refl: 7, er: 5 },
  metal: { ko: "금속 벽·문", t_ref: null, loss: [40, 50, 50], refl: 0.5, er: 1 },
  slab: { ko: "층간 바닥", t_ref: 0.2, loss: [25, 35, 40], refl: 6, er: 5.3 },
};
// 예전 저장 파일의 재질 이름
export const LEGACY = { concrete: "concrete", brick: "brick", wood: "wood", glass: "glass", gypsum: "drywall", plaster: "drywall" };
// 벽 재질 고르기에 보이는 순서
export const WALL_CHOICES = ["reinforced_concrete", "concrete", "brick", "drywall", "bathroom", "wood", "metal"];
export const WALL_MAX_DB = 60; // 벽 하나에서 잃는 세기 상한
export const ANGLE_MAX_DEG = 75, ANGLE_EXTRA_MAX_DB = 10;

export const materialOf = (name) => MATERIALS[name] || MATERIALS[LEGACY[name]] || MATERIALS.concrete;
export const bandIndex = (band) => Math.max(0, BANDS.indexOf(String(band)));

/** 벽을 곧게 지날 때 잃는 세기. 두께는 m */
export function wallLoss(name, band, thickness) {
  const m = materialOf(name), L = m.loss[bandIndex(band)];
  if (m.t_ref == null || !(thickness > 0)) return Math.min(WALL_MAX_DB, L);
  return Math.min(WALL_MAX_DB, (L * thickness) / m.t_ref);
}

// 가구·가전이 신호를 가릴 때 잃는 세기 [2.4, 5] (6 GHz는 5 GHz에서 조금 더 늘린다)
const RF = {
  refrigerator: [15, 20], kimchi_refrigerator: [15, 20], freezer: [15, 20], wine_cellar: [15, 20],
  washer: [12, 15], dryer: [12, 15], wash_tower: [12, 15], washer_dryer: [12, 15], styler: [12, 15], shoe_care: [10, 12],
  dishwasher: [10, 13], oven: [10, 13], microwave: [8, 10],
  tv: [6, 8], mirror: [8, 12], aquarium: [10, 15], bookshelf: [4, 6], storage: [4, 6],
  hood: [6, 8], cabinet: [3, 5], sofa: [2, 3], bed: [2, 3], person: [3, 5],
};
const RF_KO = {
  refrigerator: "냉장고", kimchi_refrigerator: "김치냉장고", freezer: "냉동고", wine_cellar: "와인셀러",
  washer: "세탁기", dryer: "건조기", wash_tower: "워시타워", washer_dryer: "세탁건조기", styler: "스타일러", shoe_care: "슈케어",
  dishwasher: "식기세척기", oven: "오븐", microwave: "전자레인지", tv: "TV", mirror: "거울", aquarium: "어항",
  bookshelf: "책장", storage: "수납장", hood: "후드", cabinet: "하부장", sofa: "소파", bed: "침대", person: "사람",
};
// 가구(decor:)와 스캔 가구 이름 → 위 표의 종류
const KIND = {
  "decor:hood": "hood", "decor:islandhood": "hood", "decor:basecab": "cabinet", "decor:island": "cabinet", "decor:islandtable": "cabinet",
  "decor:sink": "cabinet", "decor:tallcab": "storage", "decor:sofa": "sofa", "decor:bed": "bed", "decor:bookshelf": "bookshelf",
  "decor:wardrobe": "storage", "decor:storage": "storage", "decor:shelf": "bookshelf", "decor:dresser": "cabinet", "decor:tvstand": "cabinet",
  "decor:mirror": "mirror", tvstand: "cabinet", sofa: "sofa", bed: "bed", storage: "storage",
};

/** 종류(카탈로그 category, decor: sku, 스캔 가구 category) → { kind, ko, loss: [2.4, 5, 6] } 또는 null */
export function objectRf(key) {
  const k = RF[key] ? key : KIND[key];
  const v = RF[k];
  if (!v) return null;
  return { kind: k, ko: RF_KO[k], loss: [v[0], v[1], Math.round((v[1] + (v[1] - v[0]) / 2) * 10) / 10] };
}

// 설치 상태: 장식장·분전함 안에 넣으면 그만큼 약해진다
export const ENCLOSURE = { open: { ko: "밖에 둠", db: 0 }, cabinet: { ko: "장식장 안", db: 5 }, metal: { ko: "금속 함 안", db: 15 } };

// 802.11ax 2x2, 0.8 µs GI, 20 MHz 기준 속도(Mbps)와 그 MCS가 되는 SNR(dB)
export const MCS = [
  [2, 17.2], [5, 34.4], [9, 51.6], [11, 68.8], [15, 103.2], [18, 137.6],
  [20, 154.9], [25, 172.1], [29, 206.5], [31, 229.4], [34, 258.1], [37, 286.8],
];
export const WIDTH_SCALE = { 20: 1, 40: 2, 80: 4.19, 160: 8.38 };
export const MAC_EFFICIENCY = 0.6; // 실제로 쓰는 속도는 표 속도의 60% 정도
export const NOISE_FIGURE_DB = 7;
// 이웃 공유기·블루투스 혼잡: 2.4 GHz가 가장 붐비고 6 GHz는 거의 비어 있다
export const CONGESTION_SHARE = { "2.4": 1, 5: 0.6, 6: 0.2 };
export const MICROWAVE = { rise_db: 20, half_m: 3 }; // 켠 전자레인지: 바로 옆 +20 dB, 3 m에서 +10 dB

// 체감 기준 (범례)
export const ANCHORS = [[-50, "8K·게임"], [-60, "4K"], [-67, "화상통화"], [-75, "웹서핑"], [-85, "끊김"]];
export const DBM_TOP = -30, DBM_BOTTOM = -90;
