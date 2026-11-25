import test from "node:test";
import assert from "node:assert/strict";
import { energyBadge } from "../../apps/web/js/energy.js";

test("1~5등급은 등급 글자와 다섯 칸 눈금으로 보여 준다", () => {
  const h = energyBadge(1);
  assert.match(h, /1등급/);
  assert.match(h, /data-grade="1"/);
  assert.equal((h.match(/<i/g) || []).length, 5);
  assert.equal((h.match(/class="on"/g) || []).length, 1);
  assert.match(h, /aria-label="에너지 소비효율 1등급"/);
});

test("등급이 없거나 범위 밖이면 아무것도 보여 주지 않는다", () => {
  for (const g of [null, undefined, 0, 6, "1", 1.5]) assert.equal(energyBadge(g), "");
});
