// 남는 틈 안내: 숫자를 늘어놓지 않고, 설치 여유가 모자란 곳에만 무엇을 얼마나 띄워야 하는지 한 문장으로 알려 준다.
// 잘 들어가면 아무것도 띄우지 않는다 (초록 테두리로 충분하다). 틈은 서버(recommender/gaps.py)가 잰 값을 그대로 쓴다.
const SIDE = { wall: "옆 벽과", placement: "옆 제품과", object: "옆 가구와" };
const BACK = { wall: "뒤 벽과", placement: "뒤 제품과", object: "뒤 가구와" };

const mm = (v) => (v < 10 && Math.abs(v - Math.round(v)) > 0.05 ? (Math.ceil(v * 10) / 10).toFixed(1) : String(Math.ceil(v - 0.05)));

export function gapNotes(gaps) {
  if (!gaps) return [];
  const out = [];
  for (const key of ["left", "right", "back", "top"]) {
    const q = gaps[key];
    if (!q || q.mm == null || !(q.need_mm > 0) || q.ok !== false) continue;
    const what = key === "top" ? "천장과" : (key === "back" ? BACK : SIDE)[q.kind] || (key === "back" ? "뒤쪽을" : "옆을");
    out.push({ key, line: q.line || null, text: `${what} ${mm(q.need_mm - Math.max(q.mm, 0))} mm 더 띄워야 해요` });
  }
  return out;
}
