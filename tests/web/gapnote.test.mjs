import test from "node:test";
import assert from "node:assert/strict";
import { gapNotes } from "../../apps/web/js/gapnote.js";

const ok = { mm: 4, need_mm: 4, ok: true, kind: "placement", line: [[0, 0], [1, 0]] };

test("잘 들어가면 아무것도 띄우지 않는다", () => {
  assert.deepEqual(gapNotes({ left: ok, right: { mm: 1963, need_mm: 4, ok: true, kind: "wall" }, back: { mm: 30, need_mm: null, ok: null, kind: "wall" }, top: { mm: 500, need_mm: 15, ok: true } }), []);
});

test("필요한 값이 없는 틈(가구)은 말하지 않는다", () => {
  assert.deepEqual(gapNotes({ left: { mm: 0, need_mm: 0, ok: true, kind: "wall" }, right: { mm: 2, need_mm: null, ok: null, kind: "wall" } }), []);
});

test("모자란 틈은 무엇과 얼마나 띄워야 하는지 한 문장으로", () => {
  const n = gapNotes({ left: { mm: 2, need_mm: 4, ok: false, kind: "placement", line: [[0, 0], [1, 0]] }, back: { mm: 40, need_mm: 50, ok: false, kind: "wall", line: [[0, 0], [0, 1]] }, top: { mm: 9, need_mm: 15, ok: false, kind: "ceiling" } });
  assert.deepEqual(n.map((x) => x.text), ["옆 제품과 2 mm 더 띄워야 해요", "뒤 벽과 10 mm 더 띄워야 해요", "천장과 6 mm 더 띄워야 해요"]);
  assert.equal(n[0].key, "left");
});

test("겹쳐 있으면 필요한 값만큼, 소수는 올림", () => {
  assert.equal(gapNotes({ right: { mm: 0, need_mm: 4, ok: false, kind: "wall" } })[0].text, "옆 벽과 4 mm 더 띄워야 해요");
  assert.equal(gapNotes({ right: { mm: 1.5, need_mm: 4, ok: false, kind: "object" } })[0].text, "옆 가구와 2.5 mm 더 띄워야 해요");
});

test("양옆이 같은 말이면 한 번만 말한다", () => {
  const side = { mm: 0, need_mm: 4, ok: false, kind: "object" };
  const n = gapNotes({ left: { ...side, line: [[0, 0], [1, 0]] }, right: side });
  assert.deepEqual(n.map((x) => x.text), ["옆 가구와 4 mm 더 띄워야 해요"]);
});
