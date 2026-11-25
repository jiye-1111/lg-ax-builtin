"""제품 3D 모델(apps/web/models/products/*.glb)이 카탈로그 치수와 맞는지 확인한다.

지금 화면은 전달받은 모델 묶음(LG-WEB-DEVELOPER-01, 485 SKU)만 쓴다. tools/catalog/import_lg_handoff.mjs가 제품군별 파일로 줄여 담는다.
치수는 카탈로그(LGE.COM) 값이고, 세부 모양과 색은 사진을 보고 맞춘 화면용 표현이다.
"""
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "apps/web/models/products"
CATALOG = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
TOL_MM = 3


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON"
    return json.loads(data[20:20 + chunk_len])


def bbox_mm(gltf: dict) -> dict:
    lo, hi = [1e9] * 3, [-1e9] * 3
    for node in gltf["nodes"]:
        if "mesh" not in node:
            continue
        assert not any(k in node for k in ("rotation", "scale", "matrix")), "변형은 메시에 적용돼 있어야 한다"
        t = node.get("translation", [0, 0, 0])
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            lo = [min(a, b + c) for a, b, c in zip(lo, acc["min"], t)]
            hi = [max(a, b + c) for a, b, c in zip(hi, acc["max"], t)]
    # glTF Y-up: x = 폭, y = 높이, z = 깊이
    return {"w": (hi[0] - lo[0]) * 1000, "h": (hi[1] - lo[1]) * 1000, "d": (hi[2] - lo[2]) * 1000,
            "y0": lo[1] * 1000, "cx": (hi[0] + lo[0]) * 500, "cz": (hi[2] + lo[2]) * 500}


LINEUP = json.loads((ROOT / "data/catalog/lineup.json").read_text(encoding="utf-8"))["models"]
SHOWN = [p for p in CATALOG if p["sku"] in LINEUP]  # 화면에 내놓는 모델. 직접 만든 모델은 archive/own-models-2026-11-24에 따로 둔다
MAX_TOTAL_MB = 90  # 묶음 원본은 1.5 GB다. 저장소에는 줄인 것만 둔다


@pytest.fixture(scope="module")
def index():
    return json.loads((MODELS / "index.json").read_text(encoding="utf-8"))


def handoff() -> dict:
    """전달받은 모델 묶음에서 가져온 제품. 색이 모델에 들어 있고 원점은 전달본 기준이다."""
    return json.loads((MODELS / "handoff.json").read_text(encoding="utf-8"))["models"]


def companions() -> dict:
    return json.loads((MODELS / "companions.json").read_text(encoding="utf-8"))["models"]


def test_index_lists_exactly_the_lineup(index):
    assert set(index["models"]) == set(LINEUP) == {p["sku"] for p in SHOWN}
    used = {e["file"] for e in index["models"].values()} | {c["file"] for c in companions().values()}
    assert {f.name for f in MODELS.glob("*.glb")} == used
    assert all(e["layout"] == "handoff" for e in index["models"].values())
    assert sum(f.stat().st_size for f in MODELS.glob("*.glb")) < MAX_TOTAL_MB * 1e6


def test_lineup_is_only_what_lge_sells_now():
    """LGE.COM에서 지금 팔지 않는 모델(단종·비매품·출시 전)은 내놓지 않는다."""
    assert len(SHOWN) >= 400
    for p in SHOWN:
        assert p["sale_status"] in ("ACTIVE", "SOLD_OUT"), p["sku"]
        assert p["source_url"] and p["sale_checked_at"], p["sku"]


def test_colours_of_one_model_share_a_file(index):
    """색만 다른 모델은 파일 하나를 같이 쓰고, 파일 안의 색 이름(묶음 SKU)으로 고른다."""
    by_file = {}
    for sku, e in index["models"].items():
        by_file.setdefault(e["file"], []).append(sku)
    assert len(by_file) < len(index["models"]) / 1.5
    for file, skus in by_file.items():
        gltf = read_glb(MODELS / file)
        names = [v["name"] for v in gltf.get("extensions", {}).get("KHR_materials_variants", {}).get("variants", [])]
        for sku in skus:
            variant = index["models"][sku].get("variant")
            if variant:
                assert variant == LINEUP[sku]["handoff_sku"] and variant in names, sku
        assert set(names) <= {LINEUP[s]["handoff_sku"] for s in skus}, f"{file}: 내놓지 않는 색이 남아 있다"
        if len({index["models"][s].get("variant") for s in skus}) == 1:
            assert len(skus) == 1 or not names, f"{file}: 색 구분이 없다"


@pytest.mark.parametrize("prod", SHOWN, ids=[p["sku"] for p in SHOWN])
def test_model_matches_catalog_dims(prod, index):
    entry = index["models"][prod["sku"]]
    gltf = read_glb(MODELS / entry["file"])
    assert "EXT_meshopt_compression" in gltf.get("extensionsUsed", []), "눌러 담지 않은 모델"
    b = bbox_mm(gltf)
    info = handoff()[prod["sku"]]
    for k in ("w", "h", "d"):
        assert abs(b[k] - entry["bbox_mm"][k]) <= 1
    if "size_note" not in info:  # 묶음이 손잡이·받침까지 넣어 스펙 표보다 크게 만든 모델은 적어 두고 그대로 쓴다
        dims = prod["product_dims_mm"]
        for k in ("w", "h", "d"):
            assert abs(b[k] - dims[k]) <= TOL_MM, f"{prod['sku']} {k}: 모델 {b[k]:.1f} / 카탈로그 {dims[k]}"
    # 가운데가 원점: 화면에서 center_xz에 그대로 놓는다. 높이 기준은 전달본 그대로 (handoff.json y0_mm)
    assert abs(b["y0"] - info["y0_mm"]) <= 1 and abs(b["cx"]) <= TOL_MM and abs(b["cz"]) <= TOL_MM


def test_handoff_models_keep_their_datum_and_colour():
    """전달본 모델: 빌트인 인덕션은 상판에 닿는 면이 0이라 몸통이 상판 아래로 들어간다. 나머지는 바닥(놓는 면)이 0이다."""
    models = handoff()
    assert set(models) == set(LINEUP)
    by_sku = {p["sku"]: p for p in CATALOG}
    noted = [s for s, info in models.items() if "size_note" in info]
    assert len(noted) <= 10, noted
    for sku, info in models.items():
        names = {m["name"] for m in read_glb(MODELS / json.loads((MODELS / "index.json").read_text(encoding="utf-8"))["models"][sku]["file"])["materials"]}
        assert not names & {"finish", "glass"}, f"{sku}: 화면이 덧칠하는 재질 이름과 겹친다"
        if "counter" in (info["datum"] or ""):
            assert -60 <= info["y0_mm"] <= -50 and by_sku[sku]["category"] == "cooktop", sku
        else:
            assert info["y0_mm"] == 0, sku
        assert (ROOT / "apps/web/img/products" / f"{sku}.webp").exists()


def test_water_purifier_tap_comes_with_the_body(index):
    """빌트인 정수기는 하부장 본체와 상판 출수구가 같이 놓인다."""
    comps = companions()
    assert comps and all(by["category"] == "water_purifier" for by in CATALOG if by["sku"] in comps)
    for sku, c in comps.items():
        assert sku in index["models"] and (MODELS / c["file"]).exists() and len(c["offset_m"]) == 3


def test_own_models_are_kept_aside_not_deleted():
    """직접 만든 모델과 사진은 지우지 않고 따로 둔다. 되돌리는 방법은 그 폴더의 README."""
    kept = ROOT / "archive/own-models-2026-11-24"
    assert (kept / "README.md").exists()
    assert len(list((kept / "models/products").glob("*.glb"))) == 294
    assert len(list((kept / "img/products").glob("*.webp"))) == 1119
    old = json.loads((kept / "models/products/index.json").read_text(encoding="utf-8"))["models"]
    assert len(old) == 1150
