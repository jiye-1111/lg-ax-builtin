// 실제 벽지·바닥재의 질감을 캔버스로 그린다 (회벽·직물·스톤·우드·도장).
// 무늬는 밝은 회색조로만 그리고, 색은 재질 색(고른 톤)이 곱해져 정해진다. 사진을 가져다 쓰지 않는다.
import * as THREE from "three";

const SIZE = 512;
const cache = new Map();
export const TEXTURE_KO = { plaster: "회벽", fabric: "직물", stone: "스톤", wood: "우드", paint: "도장" };

const rng = (seed) => () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

// 값 노이즈 (부드러운 얼룩)
function noise(w, h, cell, rnd) {
  const gw = Math.ceil(w / cell) + 2, gh = Math.ceil(h / cell) + 2;
  const grid = Array.from({ length: gw * gh }, rnd);
  const s = (t) => t * t * (3 - 2 * t);
  return (x, y) => {
    const gx = x / cell, gy = y / cell, x0 = Math.floor(gx), y0 = Math.floor(gy), fx = s(gx - x0), fy = s(gy - y0);
    const at = (i, j) => grid[((j % gh) * gw) + (i % gw)];
    const a = at(x0, y0) * (1 - fx) + at(x0 + 1, y0) * fx, b = at(x0, y0 + 1) * (1 - fx) + at(x0 + 1, y0 + 1) * fx;
    return a * (1 - fy) + b * fy;
  };
}

function paintPixels(g, fn) {
  const img = g.createImageData(SIZE, SIZE);
  for (let y = 0; y < SIZE; y++) for (let x = 0; x < SIZE; x++) {
    const v = Math.max(0, Math.min(255, fn(x, y))), i = (y * SIZE + x) * 4;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
}

const DRAW = {
  // 손으로 바른 듯한 회벽: 큰 얼룩 + 흙손 자국
  plaster(g, r) {
    const n1 = noise(SIZE, SIZE, 96, r), n2 = noise(SIZE, SIZE, 22, r), n3 = noise(SIZE, SIZE, 5, r);
    paintPixels(g, (x, y) => 228 + (n1(x, y) - 0.5) * 34 + (n2(x, y) - 0.5) * 18 + (n3(x, y) - 0.5) * 8);
    for (let k = 0; k < 70; k++) {
      g.strokeStyle = `rgba(255,255,255,${0.05 + r() * 0.07})`;
      g.lineWidth = 6 + r() * 16;
      const x = r() * SIZE, y = r() * SIZE, a = r() * Math.PI;
      g.beginPath(); g.arc(x, y, 30 + r() * 60, a, a + 0.6 + r() * 0.8); g.stroke();
    }
  },
  // 직물: 가로·세로 실 + 굵기 얼룩
  fabric(g, r) {
    const n = noise(SIZE, SIZE, 40, r), slub = noise(SIZE, SIZE, 9, r);
    paintPixels(g, (x, y) => {
      const warp = Math.sin(x * 1.6) * 0.5 + 0.5, weft = Math.sin(y * 1.6) * 0.5 + 0.5;
      return 222 + (warp * weft - 0.25) * 26 + (n(x, y) - 0.5) * 14 + (slub(x, y) > 0.82 ? -10 : 0);
    });
  },
  // 대리석·스톤: 밝은 바탕 + 회색 결
  stone(g, r) {
    const n1 = noise(SIZE, SIZE, 120, r), n2 = noise(SIZE, SIZE, 30, r);
    paintPixels(g, (x, y) => 236 + (n1(x, y) - 0.5) * 18 + (n2(x, y) - 0.5) * 10);
    for (let k = 0; k < 9; k++) {
      let x = r() * SIZE, y = r() * SIZE, a = r() * Math.PI * 2;
      g.strokeStyle = `rgba(110,108,104,${0.12 + r() * 0.2})`;
      g.lineWidth = 0.6 + r() * 1.8;
      g.beginPath(); g.moveTo(x, y);
      for (let s = 0; s < 40; s++) { a += (r() - 0.5) * 0.7; x += Math.cos(a) * 14; y += Math.sin(a) * 14; g.lineTo(x, y); }
      g.stroke();
    }
  },
  // 마루·우드 판: 판마다 밝기 다르게 + 나뭇결 + 판 이음
  wood(g, r, rows = 8) {
    const rowH = SIZE / rows;
    for (let row = 0; row < rows; row++) {
      let x = -r() * 200;
      while (x < SIZE) {
        const len = 150 + r() * 140, v = 214 + r() * 38;
        g.fillStyle = `rgb(${v},${v},${v})`;
        g.fillRect(x, row * rowH, len, rowH);
        for (let k = 0; k < 7; k++) {
          g.strokeStyle = `rgba(70,70,70,${0.04 + r() * 0.06})`;
          g.lineWidth = 0.5 + r();
          const y = row * rowH + r() * rowH;
          g.beginPath(); g.moveTo(x, y);
          g.bezierCurveTo(x + len * 0.3, y + (r() - 0.5) * 6, x + len * 0.7, y + (r() - 0.5) * 6, x + len, y); g.stroke();
        }
        g.fillStyle = "rgba(40,40,40,.32)"; g.fillRect(x, row * rowH, 1.5, rowH);
        x += len;
      }
      g.fillStyle = "rgba(40,40,40,.28)"; g.fillRect(0, row * rowH, SIZE, 1.5);
    }
  },
  // 도장: 거의 평평한 면 (롤러 자국만 살짝)
  paint(g, r) {
    const n = noise(SIZE, SIZE, 64, r);
    paintPixels(g, (x, y) => 246 + (n(x, y) - 0.5) * 6);
  },
};

/** 질감 캔버스 (회색조). 같은 질감은 한 번만 그린다. */
export function textureCanvas(texture) {
  if (!cache.has(texture)) {
    const cv = document.createElement("canvas");
    cv.width = cv.height = SIZE;
    (DRAW[texture] || DRAW.paint)(cv.getContext("2d"), rng(texture.length * 977 + 13));
    if (texture === "stone") { // 타일 줄눈
      const g = cv.getContext("2d");
      g.fillStyle = "rgba(90,90,90,.35)";
      g.fillRect(0, 0, SIZE, 2); g.fillRect(0, 0, 2, SIZE);
    }
    cache.set(texture, cv);
  }
  return cache.get(texture);
}

/** 3D 재질용 텍스처. tileM = 무늬 한 장이 덮는 크기(m). */
export function finishTexture(finish) {
  const tex = new THREE.CanvasTexture(textureCanvas(finish.texture));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  return tex;
}

/** 무늬 한 장이 덮는 실제 크기(m): 마루는 판 폭 × 8줄, 타일은 타일 크기, 벽지는 0.9 m 정도 */
export function tileMeters(finish) {
  const s = finish.spec || {};
  if (finish.texture === "wood") return ((s.plank_width_mm || (finish.kind === "floor" ? 190 : 300)) / 1000) * 8;
  if (finish.texture === "stone") return s.tile_mm ? s.tile_mm[0] / 1000 : finish.kind === "floor" ? 0.6 : 1.2;
  if (finish.texture === "fabric") return 0.35;
  return 0.9;
}

export const BUMP = { plaster: 0.012, fabric: 0.006, stone: 0.002, wood: 0.004, paint: 0.001 };
export const ROUGH = { plaster: 0.95, fabric: 0.98, stone: 0.35, wood: 0.6, paint: 0.9 };

/** 카드용 미리보기 그림 (톤 색을 곱한 질감) */
export function swatchUrl(finish, hex, px = 120) {
  const key = `${finish.id}|${hex}|${px}`;
  if (cache.has(key)) return cache.get(key);
  const cv = document.createElement("canvas");
  cv.width = cv.height = px;
  const g = cv.getContext("2d");
  g.drawImage(textureCanvas(finish.texture), 0, 0, SIZE * (px / 160), SIZE * (px / 160));
  g.globalCompositeOperation = "multiply";
  g.fillStyle = hex; g.fillRect(0, 0, px, px);
  const url = cv.toDataURL("image/png");
  cache.set(key, url);
  return url;
}
