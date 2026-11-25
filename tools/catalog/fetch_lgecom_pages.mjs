// LGE.COM 제품 페이지를 열어 이름·판매 상태·가격·스펙 표를 읽는다.
//   node tools/catalog/fetch_lgecom_pages.mjs <urls.json> <결과.json> [받은 페이지를 둘 폴더]
// urls.json: {"DUE6BGE.AKOR": "https://www.lge.co.kr/product/dishwashers/due6bge", ...}
// 읽는 값
//   name, sku, model  페이지 제품 정보(JSON-LD Product)
//   model_status      modelStatus.code (ACTIVE, SOLD_OUT, NOT_FOR_SALE, DISCONTINUED, READY_FOR_SALE ...)
//   price_krw         판매가 obsSellingPrice (없으면 제품 정보의 offers.price, 0이면 null)
//   specs             스펙 표의 항목 이름과 값 (적힌 글자 그대로)
// 한 번에 3개씩만 받고, 받은 페이지는 폴더에 두어 다시 돌릴 때 또 받지 않는다.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
const text = (s) => s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();

export function parse(html) {
  const ld = [...html.matchAll(/<script type="application\/ld\+json"[^>]*>(.*?)<\/script>/gs)]
    .map((m) => { try { return JSON.parse(m[1]); } catch { return null; } }).find((x) => x?.["@type"] === "Product");
  const status = html.match(/modelStatus\\":\{\\"code\\":\\"([A-Z_]+)\\"/)?.[1] ?? null;
  // 가격: 이 모델 정보(modelStatus)에 가장 가까이 적힌 판매가 obsSellingPrice. 같은 페이지에 다른 색 모델 가격도 섞여 있어서 가까운 것을 쓴다.
  // 제품 정보(JSON-LD offers.price)는 보통 같은 수지만 구독 페이지에서는 월 요금이라 판매가가 없을 때만 쓴다
  const at = html.search(/modelStatus\\":\{\\"code\\"/);
  const near = [...html.matchAll(/obsSellingPrice\\":(\d+)/g)].map((m) => [Math.abs(m.index - at), Number(m[1])]).sort((x, y) => x[0] - y[0])[0];
  const price = (at >= 0 && near?.[1]) || Number(ld?.offers?.price ?? 0) || null;
  const specs = {};
  for (const m of html.matchAll(/<dt[^>]*>(.*?)<\/dt>\s*<dd[^>]*>(.*?)<\/dd>/gs)) {
    const k = text(m[1]);
    if (k && !(k in specs) && k !== "구매 옵션") specs[k] = text(m[2]);
  }
  return { name: ld?.name ?? null, sku: ld?.sku ?? null, model: ld?.model ?? null, model_status: status, price_krw: price, specs };
}

async function get(key, url, cacheAt) {
  const file = cacheAt && path.join(cacheAt, key.replace(/[^\w.-]/g, "_") + ".html");
  if (file && fs.existsSync(file)) return { status: 200, final: url, html: fs.readFileSync(file, "utf-8") };
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(url, { headers: { "user-agent": UA, "accept-language": "ko" }, redirect: "follow", signal: AbortSignal.timeout(40000) });
      const html = await r.text();
      if (r.status === 200 && file) fs.writeFileSync(file, html);
      if (r.status === 200 || r.status === 404) return { status: r.status, final: r.url, html };
    } catch { /* 다시 */ }
    await new Promise((ok) => setTimeout(ok, 1500 * (i + 1)));
  }
  return { status: 0, final: url, html: "" };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [urlsAt, outAt, cacheAt] = process.argv.slice(2);
  if (!urlsAt || !outAt) { console.error("urls.json과 결과 파일을 알려 주세요"); process.exit(1); }
  const urls = JSON.parse(fs.readFileSync(urlsAt, "utf-8"));
  if (cacheAt) fs.mkdirSync(cacheAt, { recursive: true });
  const out = {}, todo = Object.entries(urls);
  let n = 0;
  await Promise.all([0, 1, 2].map(async () => {
    for (let job; (job = todo.shift());) {
      const [key, url] = job;
      const r = await get(key, url, cacheAt);
      out[key] = r.status === 200 ? { ...parse(r.html), source_url: url, final_url: r.final } : { error: r.status || "받지 못함", source_url: url };
      if (++n % 25 === 0) console.log(n, "/", Object.keys(urls).length);
      await new Promise((ok) => setTimeout(ok, 300));
    }
  }));
  const sorted = Object.fromEntries(Object.keys(urls).map((k) => [k, out[k]]));
  fs.writeFileSync(outAt, JSON.stringify(sorted, null, 1) + "\n");
  const c = {};
  for (const v of Object.values(sorted)) { const k = v.error ? "error:" + v.error : v.model_status; c[k] = (c[k] ?? 0) + 1; }
  console.log(c);
}
