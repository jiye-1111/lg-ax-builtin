// 전달받은 LG 모델 묶음(LG-WEB-DEVELOPER-01, 485 SKU)을 우리 사이트 모델로 옮긴다.
//   node tools/catalog/import_lg_handoff.mjs <압축 푼 폴더> [--deps <node_modules가 있는 폴더>] [--only <제품군 이름 일부>]
// 필요한 패키지: @gltf-transform/core, @gltf-transform/extensions, @gltf-transform/functions, meshoptimizer, sharp
// 먼저 tools/catalog/add_handoff_products.py를 돌려 data/catalog/lineup.json(화면에 내놓는 모델)을 만들어 둔다.
// 하는 일
//   - 내놓는 모델이 하나라도 있는 제품군만 옮긴다. 제품군 파일 하나에 색이 여러 개 들어 있고(KHR_materials_variants,
//     이름이 정확한 SKU), 그대로 한 파일로 둔다. 화면이 모델명에 맞는 색을 골라 입힌다 (index.json의 variant)
//   - 조각이 많아 느린 모델은 색 묶음이 같은 조각끼리 합치고, 삼각형이 너무 많으면 모양이 안 변하는 선에서 줄인다
//   - 그림은 1024px webp로, 꼭짓점은 meshopt로 눌러 담는다 (위치 값은 그대로 두어 치수가 변하지 않는다)
//   - 원점은 전달본 그대로 둔다. 인덕션은 상판에 닿는 면이 0이라 몸통이 상판 아래로 들어간다
//   - 제품 사진은 묶음의 검수 사진(<SKU>-quarter.png)을 360px webp로 줄여 쓴다
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const src = args[0];
const opt = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : null);
const depsAt = opt("--deps") ?? process.cwd();
const only = opt("--only");
if (!src || !fs.existsSync(path.join(src, "catalog/library.json"))) {
  console.error("압축 푼 폴더(catalog/library.json이 있는 곳)를 알려 주세요"); process.exit(1);
}
const req = createRequire(path.join(path.resolve(depsAt), "package.json"));
const load = (name) => import(pathToFileURL(req.resolve(name)).href);
const { NodeIO } = await load("@gltf-transform/core");
const { ALL_EXTENSIONS, EXTMeshoptCompression } = await load("@gltf-transform/extensions");
const { join, flatten, prune, weld, simplify, dedup, reorder, quantize, textureCompress, getBounds, transformMesh } = await load("@gltf-transform/functions");
const { MeshoptSimplifier, MeshoptEncoder, MeshoptDecoder } = await load("meshoptimizer");
const sharp = (await load("sharp")).default;
await Promise.all([MeshoptSimplifier.ready, MeshoptEncoder.ready, MeshoptDecoder.ready]);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(ROOT, "apps/web/models/products");
const IMG = path.join(ROOT, "apps/web/img/products");
const MAX_TRIANGLES = 45000; // 내장 그래픽에서도 여러 대를 놓고 움직일 수 있는 선
const RESERVED = new Set(["finish", "glass"]); // 우리 화면이 색을 덧입히는 재질 이름. 전달본 재질은 색이 이미 맞아서 겹치면 안 된다
const VARIANTS = "KHR_materials_variants";
// 정수기 출수구: 조리대 높이 850mm(국내 표준 주방 높이로 가정) 위, 본체 가운데에서 100mm 뒤. 전에 쓰던 자리와 같다
const FAUCET_OFFSET_M = [0, 0.85, -0.1];

const library = JSON.parse(fs.readFileSync(path.join(src, "catalog/library.json"), "utf-8"));
const lineup = JSON.parse(fs.readFileSync(path.join(ROOT, "data/catalog/lineup.json"), "utf-8")).models;
const catalog = new Map(JSON.parse(fs.readFileSync(path.join(ROOT, "data/catalog/products.json"), "utf-8")).products.map((p) => [p.sku, p]));
const ours = new Map(Object.entries(lineup).map(([sku, m]) => [m.handoff_sku, sku])); // 묶음 SKU → 우리 모델명
const product = new Map(library.products.map((p) => [p.sku, p]));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ "meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder });
const prims = (doc) => doc.getRoot().listMeshes().flatMap((m) => m.listPrimitives());
const triangles = (doc) => prims(doc).reduce((n, p) => n + (p.getIndices()?.getCount() ?? p.getAttribute("POSITION").getCount()) / 3, 0);
const fileName = (id, tail) => `${id.replace(/[^\w.-]/g, "_")}-${tail}.glb`;

/** 묶음 GLB 하나를 옮긴다. keep = 남길 색(묶음 SKU). 색이 하나뿐이거나 모두 같은 재질이면 색 정보 없이 저장한다 */
async function convert(glb, keep, out) {
  const doc = await io.read(path.join(src, glb));
  const ext = doc.getRoot().listExtensionsUsed().find((e) => e.extensionName === VARIANTS);
  // 조각마다 "색별 재질 묶음"을 적어 두고, 묶음이 같은 조각끼리 합칠 수 있게 임시 재질을 입힌다
  const sets = new Map(), ids = new Map();
  const idOf = (m) => ids.get(m) ?? ids.set(m, ids.size).get(m);
  for (const prim of prims(doc)) {
    const list = prim.getExtension(VARIANTS)?.listMappings() ?? [];
    const mats = keep.map((name) => list.find((m) => m.listVariants().some((v) => v.getName() === name))?.getMaterial() ?? prim.getMaterial());
    const key = mats.map(idOf).join("|");
    // 임시 재질은 서로 달라 보여야 한다 (같으면 뒤 단계가 하나로 합쳐 버린다)
    if (!sets.has(key)) sets.set(key, { mats, stand: doc.createMaterial(`set${sets.size}`).setBaseColorFactor([(sets.size % 251) / 251, Math.floor(sets.size / 251) / 251, 0.5, 1]) });
    prim.setExtension(VARIANTS, null).setMaterial(sets.get(key).stand);
  }
  const before = triangles(doc);
  await doc.transform(dedup({ propertyTypes: ["Accessor", "Mesh", "Texture"] }), flatten());
  for (const n of doc.getRoot().listNodes()) { // 노드 변형을 메시에 구워 넣는다 (같은 메시를 여러 곳에 쓰면 복사해서)
    const mesh = n.getMesh();
    if (!mesh) continue;
    const own = mesh.listParents().filter((x) => x.propertyType === "Node").length > 1 ? mesh.clone() : mesh;
    for (const prim of own.listPrimitives()) for (const sem of prim.listSemantics()) {
      const acc = prim.getAttribute(sem);
      if (acc.listParents().filter((x) => x.propertyType === "Primitive").length > 1) prim.setAttribute(sem, acc.clone());
    }
    transformMesh(own, n.getWorldMatrix());
    n.setMesh(own).setMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
  }
  await doc.transform(join({ keepNamed: false }), weld());
  if (before > MAX_TRIANGLES) await doc.transform(simplify({ simplifier: MeshoptSimplifier, ratio: MAX_TRIANGLES / before, error: 0.0004 }));
  // 임시 재질을 실제 재질로 되돌리고, 색마다 재질이 다른 조각에만 색 정보를 단다
  for (const v of ext?.listVariants() ?? []) v.dispose();
  const byStand = new Map([...sets.values()].map((s) => [s.stand, s.mats]));
  const vars = keep.map((name) => ext?.createVariant(name));
  let mixed = false;
  for (const prim of prims(doc)) {
    const mats = byStand.get(prim.getMaterial());
    if (mats.some((m) => m.isDisposed())) throw new Error(`${glb}: 재질이 사라졌다`);
    prim.setMaterial(mats[0]);
    if (mats.every((m) => m === mats[0])) continue;
    mixed = true;
    const list = ext.createMappingList();
    for (const m of new Set(mats)) {
      const map = ext.createMapping().setMaterial(m);
      mats.forEach((x, i) => { if (x === m) map.addVariant(vars[i]); });
      list.addMapping(map);
    }
    prim.setExtension(VARIANTS, list);
  }
  if (!mixed) ext?.dispose();
  for (const m of doc.getRoot().listMaterials()) if (RESERVED.has(m.getName())) m.setName(`lg_${m.getName()}`);
  await doc.transform(prune());
  for (const n of doc.getRoot().listNodes()) { // 변형이 남으면 치수 검사가 틀린다
    const [t, r, s] = [n.getTranslation(), n.getRotation(), n.getScale()];
    if (t.some((x) => Math.abs(x) > 1e-9) || Math.abs(r[3] - 1) > 1e-9 || s.some((x) => Math.abs(x - 1) > 1e-9)) throw new Error(`${glb}: 노드 변형이 남았다`);
  }
  const b = getBounds(doc.getRoot().listScenes()[0]);
  if (doc.getRoot().listTextures().length) await doc.transform(textureCompress({ encoder: sharp, targetFormat: "webp", resize: [1024, 1024] }));
  await doc.transform(reorder({ encoder: MeshoptEncoder }), quantize({ pattern: /^(NORMAL|TANGENT|TEXCOORD_\d+)$/ }));
  doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
  await io.write(path.join(OUT, out), doc);
  return { mixed, before, after: triangles(doc), parts: prims(doc).length,
    size: [0, 1, 2].map((i) => Math.round((b.max[i] - b.min[i]) * 1000)), y0: Math.round(b.min[1] * 1000) };
}

// 묶음 폴더의 검수 사진
const photos = new Map();
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) walk(path.join(dir, e.name));
    else if (e.name.endsWith("-quarter.png") && !e.name.includes("reaudit")) photos.set(e.name.slice(0, -12), path.join(dir, e.name));
  }
})(src);

const todo = library.assets.filter((a) => a.skus.some((s) => ours.has(s)) && (!only || a.family_id.includes(only)));
if (!only) { // 다 새로 만든다. 전에 옮긴 모델 파일은 지운다
  for (const f of fs.readdirSync(OUT)) if (f.endsWith(".glb")) fs.rmSync(path.join(OUT, f));
}
const index = {}, done = {}, companions = {}, odd = [];
for (const a of todo) {
  const keep = a.skus.filter((s) => ours.has(s));
  const file = fileName(a.family_id, a.id.slice(-6));
  const r = await convert(a.glb, keep, file);
  if (r.size.some((x, i) => Math.abs(x - a.placement_whd_mm[i]) > 2)) throw new Error(`${a.family_id}: 크기 ${r.size} / 전달본 ${a.placement_whd_mm}`);
  for (const s of keep) {
    const sku = ours.get(s), p = product.get(s), dims = catalog.get(sku).product_dims_mm;
    index[sku] = { file, ...(r.mixed ? { variant: s } : {}), layout: "handoff", bbox_mm: { w: r.size[0], h: r.size[1], d: r.size[2] } };
    done[sku] = { package_id: "LG-WEB-DEVELOPER-01", family_id: a.family_id, handoff_sku: s, color: p.color_label,
      datum: a.placement_datum?.type ?? null, y0_mm: r.y0, revision: a.source_release };
    if ([dims.w - r.size[0], dims.h - r.size[1], dims.d - r.size[2]].some((x) => Math.abs(x) > 3)) {
      // 카탈로그는 LGE.COM 스펙 표 치수, 모델은 묶음이 따로 확인한 치수(손잡이·받침 포함)라 다른 것. 모델을 줄이지 않고 적어 둔다
      done[sku].size_note = `모델 ${r.size.join("x")} / 스펙 표 ${dims.w}x${dims.h}x${dims.d}`;
      odd.push(sku);
    }
    await sharp(photos.get(s)).resize(360, 360, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } }).webp({ quality: 82 }).toFile(path.join(IMG, `${sku}.webp`));
  }
  for (const id of a.linked_components) { // 본체와 떨어져 놓이는 부품 (정수기 출수구)
    const c = library.components.find((x) => x.id === id);
    const use = c.skus.filter((s) => keep.includes(s));
    if (!use.length) continue;
    const cfile = fileName(c.id, "part");
    const cr = await convert(c.glb, use, cfile);
    for (const s of use) companions[ours.get(s)] = { file: cfile, ...(cr.mixed ? { variant: s } : {}), offset_m: FAUCET_OFFSET_M,
      note: `${c.label} ${cr.size.join("x")} mm. 조리대 높이 850mm(국내 표준 주방 높이로 가정) 위, 본체 가운데에서 100mm 뒤에 놓는다. 실제 타공 자리는 현장마다 다르다` };
  }
  console.log(a.family_id, keep.length, "색", r.size.join("x"), `${r.before} -> ${r.after} tri`, r.parts, "조각", Math.round(fs.statSync(path.join(OUT, file)).size / 1024), "KB");
}
if (only) { console.log("일부만 돌려서 목록 파일은 쓰지 않았다"); process.exit(0); }
const missing = Object.keys(lineup).filter((s) => !index[s]);
if (missing.length) throw new Error(`모델이 없는 제품: ${missing}`);
const note = "전달받은 모델 묶음(LG-WEB-DEVELOPER-01)에서 가져온 제품. 색은 모델에 들어 있어서 finish 재질이 없다. LG 공식 3D가 아니고 세부 모양과 색은 사진을 보고 맞춘 것이다";
fs.writeFileSync(path.join(OUT, "handoff.json"), JSON.stringify({ note, models: done }, null, 1) + "\n");
fs.writeFileSync(path.join(OUT, "index.json"), JSON.stringify({ _note: "제품 3D 모델 목록. 전달받은 모델 묶음(LG-WEB-DEVELOPER-01)만 쓴다. 색만 다른 모델은 파일 하나를 같이 쓰고 variant로 색을 고른다. tools/catalog/import_lg_handoff.mjs가 만든다", models: index }, null, 1) + "\n");
fs.writeFileSync(path.join(OUT, "companions.json"), JSON.stringify({ models: companions }, null, 1) + "\n");
const total = fs.readdirSync(OUT).filter((f) => f.endsWith(".glb")).reduce((n, f) => n + fs.statSync(path.join(OUT, f)).size, 0);
console.log(Object.keys(index).length, "개 모델,", todo.length, "개 파일,", Math.round(total / 1e6), "MB. 스펙 표와 크기가 다른 것:", odd.join(" ") || "없음");
