// 굵은 등고선에 붙일 글자 자리 (marching squares). DOM 없음
/**
 * values: Float32Array (nx*ny, 칸 가운데 값), origin [x0, z0], cell(m)
 * levels: [값...], inside(xz): 집 안인지. 반환 [{level, xz, length}]
 */
export function contourLabels(values, nx, ny, origin, cell, levels, { inside = () => true, minLen = 1.2, perLevel = 2 } = {}) {
  const out = [];
  const at = (i, j) => [origin[0] + (i + 0.5) * cell, origin[1] + (j + 0.5) * cell];
  for (const L of levels) {
    const segs = [];
    for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const v = [values[j * nx + i], values[j * nx + i + 1], values[(j + 1) * nx + i + 1], values[(j + 1) * nx + i]];
      const p = [at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)];
      const cuts = [];
      for (let k = 0; k < 4; k++) {
        const a = v[k], b = v[(k + 1) % 4];
        if ((a >= L) !== (b >= L)) {
          const t = (L - a) / (b - a), pa = p[k], pb = p[(k + 1) % 4];
          cuts.push([pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t]);
        }
      }
      if (cuts.length === 2) segs.push(cuts);
      else if (cuts.length === 4) { segs.push([cuts[0], cuts[1]]); segs.push([cuts[2], cuts[3]]); }
    }
    // 끝점끼리 이어 선으로
    const key = (q) => `${Math.round(q[0] * 1e4)},${Math.round(q[1] * 1e4)}`;
    const ends = new Map();
    segs.forEach((s, k) => { for (const q of s) { const kk = key(q); (ends.get(kk) || ends.set(kk, []).get(kk)).push(k); } });
    const used = new Uint8Array(segs.length), lines = [];
    for (let k = 0; k < segs.length; k++) {
      if (used[k]) continue;
      used[k] = 1;
      const line = [...segs[k]];
      for (const dir of [1, -1]) {
        for (;;) {
          const tip = dir > 0 ? line[line.length - 1] : line[0];
          const nb = (ends.get(key(tip)) || []).find((m) => !used[m]);
          if (nb == null) break;
          used[nb] = 1;
          const [a, b] = segs[nb], nxt = key(a) === key(tip) ? b : a;
          if (dir > 0) line.push(nxt); else line.unshift(nxt);
        }
      }
      lines.push(line);
    }
    const picks = [];
    for (const line of lines) {
      let len = 0;
      for (let k = 1; k < line.length; k++) len += Math.hypot(line[k][0] - line[k - 1][0], line[k][1] - line[k - 1][1]);
      if (len < minLen) continue;
      let half = len / 2, xz = line[0];
      for (let k = 1; k < line.length; k++) {
        const d = Math.hypot(line[k][0] - line[k - 1][0], line[k][1] - line[k - 1][1]);
        if (half <= d) { const t = half / d; xz = [line[k - 1][0] + (line[k][0] - line[k - 1][0]) * t, line[k - 1][1] + (line[k][1] - line[k - 1][1]) * t]; break; }
        half -= d;
      }
      if (inside(xz)) picks.push({ level: L, xz, length: len });
    }
    picks.sort((a, b) => b.length - a.length);
    out.push(...picks.slice(0, perLevel));
  }
  return out;
}
