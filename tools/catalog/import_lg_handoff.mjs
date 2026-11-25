// 전달받은 LG 모델 묶음(LG-HANDOFF-01)을 우리 사이트 모델로 옮긴다.
//   node tools/catalog/import_lg_handoff.mjs <압축 푼 폴더> [--deps <node_modules가 있는 폴더>]
// 필요한 패키지: @gltf-transform/core, @gltf-transform/extensions, @gltf-transform/functions, meshoptimizer
// 하는 일
//   - 제품군 GLB 하나에 색이 여러 개 들어 있다(KHR_materials_variants). 우리 화면은 모델명마다 파일 하나라서 색을 입혀 따로 저장한다
//   - 우리 카탈로그(data/catalog/products.json)에 있는 모델만 바꾼다. 없는 모델은 건드리지 않고 목록만 남긴다
//   - 조각이 많아 느린 모델은 재질별로 합치고, 삼각형이 너무 많으면 모양이 안 변하는 선에서 줄인다
//   - 원점은 전달본 그대로 둔다. 인덕션은 상판에 닿는 면이 0이라 55 mm가 상판 아래로 들어간다
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const src = args[0];
const depsAt = args.includes("--deps") ? args[args.indexOf("--deps") + 1] : process.cwd();
if (!src || !fs.existsSync(path.join(src, "catalog/library.json"))) {
  console.error("압축 푼 폴더(catalog/library.json이 있는 곳)를 알려 주세요"); process.exit(1);
}
const req = createRequire(path.join(path.resolve(depsAt), "package.json"));
const load = (name) => import(pathToFileURL(req.resolve(name)).href);
const { NodeIO } = await load("@gltf-transform/core");
const { ALL_EXTENSIONS, KHRMaterialsVariants } = await load("@gltf-transform/extensions");
const { join, flatten, prune, weld, simplify, getBounds, transformMesh } = await load("@gltf-transform/functions");
const { MeshoptSimplifier } = await load("meshoptimizer");
await MeshoptSimplifier.ready;

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const OUT = path.join(ROOT, "apps/web/models/products");
const MAX_TRIANGLES = 45000; // 내장 그래픽에서도 여러 대를 놓고 움직일 수 있는 선
const RESERVED = new Set(["finish", "glass"]); // 우리 화면이 색을 덧입히는 재질 이름. 전달본 재질은 색이 이미 맞아서 겹치면 안 된다

const library = JSON.parse(fs.readFileSync(path.join(src, "catalog/library.json"), "utf-8"));
const catalog = new Map(JSON.parse(fs.readFileSync(path.join(ROOT, "data/catalog/products.json"), "utf-8")).products.map((p) => [p.sku, p]));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const triangles = (doc) => doc.getRoot().listMeshes().flatMap((m) => m.listPrimitives())
  .reduce((n, p) => n + (p.getIndices()?.getCount() ?? p.getAttribute("POSITION").getCount()) / 3, 0);

const done = {}, skipped = [], index = {};
for (const fam of library.families) {
  for (const v of fam.variants) {
    const sku = v.sku.slice(0, v.sku.lastIndexOf(".")); // 전달본은 DUE6BGE.AKOR, 우리 카탈로그는 DUE6BGE
    if (!catalog.has(sku)) { skipped.push({ sku: v.sku, family_id: fam.family_id, label: fam.label, color: v.color_label, source_url: v.source_url }); continue; }
    const doc = await io.read(path.join(src, fam.glb));
    const variant = doc.getRoot().listExtensionsUsed().find((e) => e instanceof KHRMaterialsVariants);
    for (const prim of doc.getRoot().listMeshes().flatMap((m) => m.listPrimitives())) {
      const list = prim.getExtension("KHR_materials_variants");
      const hit = list?.listMappings().find((m) => m.listVariants().some((x) => x.getName() === v.variant_name));
      if (hit) prim.setMaterial(hit.getMaterial());
      prim.setExtension("KHR_materials_variants", null);
    }
    variant?.dispose();
    for (const m of doc.getRoot().listMaterials()) if (RESERVED.has(m.getName())) m.setName(`lg_${m.getName()}`);
    const before = triangles(doc);
    await doc.transform(flatten());
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
    await doc.transform(prune());
    for (const n of doc.getRoot().listNodes()) { // 변형이 남으면 치수 검사가 틀린다
      const [t, r, s] = [n.getTranslation(), n.getRotation(), n.getScale()];
      if (t.some((x) => Math.abs(x) > 1e-9) || Math.abs(r[3] - 1) > 1e-9 || s.some((x) => Math.abs(x - 1) > 1e-9)) throw new Error(`${sku}: 노드 변형이 남았다`);
    }
    const b = getBounds(doc.getRoot().listScenes()[0]);
    const size = [0, 1, 2].map((i) => Math.round((b.max[i] - b.min[i]) * 1000));
    if (size.some((x, i) => Math.abs(x - fam.whd_mm[i]) > 2)) throw new Error(`${sku}: 크기 ${size} / 전달본 ${fam.whd_mm}`);
    await io.write(path.join(OUT, `${sku}.glb`), doc);
    index[sku] = { file: `${sku}.glb`, layout: "handoff", bbox_mm: { w: size[0], h: size[1], d: size[2] } };
    done[sku] = { package_id: library.package_id, family_id: fam.family_id, handoff_sku: v.sku, color: v.color_label,
      datum: fam.placement_datum.type, y0_mm: Math.round(b.min[1] * 1000), revision: fam.source_revision ?? null };
    console.log(sku, size.join("x"), `${before} -> ${triangles(doc)} tri`, doc.getRoot().listMeshes().flatMap((m) => m.listPrimitives()).length, "prims");
  }
}
const note = "전달받은 모델 묶음에서 가져온 제품. 색은 모델에 들어 있어서 finish 재질이 없다. LG 공식 3D가 아니고 세부 모양과 색은 사진을 보고 맞춘 것이다";
fs.writeFileSync(path.join(OUT, "handoff.json"), JSON.stringify({ note, models: done, not_in_catalog: skipped }, null, 1) + "\n");
// 화면은 index.json에 있는 모델만 불러온다. 지금은 전달받은 모델만 쓴다
fs.writeFileSync(path.join(OUT, "index.json"), JSON.stringify({ _note: "제품 3D 모델 목록. 전달받은 모델 묶음(LG-HANDOFF-01)만 쓴다. tools/catalog/import_lg_handoff.mjs가 만든다", models: index }, null, 1) + "\n");
fs.writeFileSync(path.join(OUT, "companions.json"), JSON.stringify({ models: {} }) + "\n");
console.log(Object.keys(done).length, "개 바꿈,", skipped.length, "개는 카탈로그에 없어 그대로 둠");
