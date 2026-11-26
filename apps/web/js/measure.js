// 벽 길이 재기: 넣은 글자를 길이로 읽고, 입력 카드 자리를 잡는다. 화면을 건드리지 않는 계산만.

const UNITS = [0.001, 0.01, 1]; // mm, cm, m
const NEAR = 0.2;               // 스캔 길이와 이 비율 안이면 그 단위로 넣은 것으로 본다

/** 넣은 글자 → 길이(m). 칸은 mm지만 줄자 눈금대로 cm·m로 넣어도 스캔 길이에 가까운 단위로 읽는다. 못 읽으면 null */
export function readLength(text, scanM) {
  const t = String(text ?? "").replace(/[,\s]/g, "").replace(/(mm|cm|m)$/i, "");
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  const n = parseFloat(t);
  if (!(n > 0)) return null;
  const fits = UNITS.map((u) => n * u).filter((m) => Math.abs(m - scanM) <= NEAR * scanM);
  const m = fits.length ? fits.reduce((a, b) => (Math.abs(a - scanM) <= Math.abs(b - scanM) ? a : b)) : n * UNITS[0];
  return Math.round(m * 1000) / 1000;
}

export const fmtMm = (m) => Math.round(m * 1000).toLocaleString("ko-KR");

/** 벽 발치(화면 좌표, 3D 칸 기준) 바로 아래에 카드를 둔다. 아래가 모자라면 위로, 옆은 칸 안으로 */
export function cardSpot([x, y], stage, card, pad = 8, gap = 18) {
  const left = Math.round(Math.min(Math.max(x - card.width / 2, pad), stage.width - card.width - pad));
  const below = y + gap;
  const top = below + card.height <= stage.height - pad ? below : Math.max(pad, y - gap - card.height);
  return { left, top: Math.round(top) };
}
