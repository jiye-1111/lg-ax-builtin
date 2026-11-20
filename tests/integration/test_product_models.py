"""제품 3D 모델(apps/web/models/products/*.glb)이 카탈로그 치수와 맞는지 확인한다.

모델은 services/blender-worker/worker/bpy_scripts/build_products.py로 Blender에서 만든다.
치수는 카탈로그(LGE.COM) 값이고, 문 나눔·손잡이 같은 모양은 화면용 표현이다.
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


@pytest.fixture(scope="module")
def index():
    return json.loads((MODELS / "index.json").read_text(encoding="utf-8"))


def test_index_lists_every_catalog_product(index):
    assert {p["sku"] for p in CATALOG} <= set(index["models"])


@pytest.mark.parametrize("prod", CATALOG, ids=[p["sku"] for p in CATALOG])
def test_model_matches_catalog_dims(prod, index):
    entry = index["models"][prod["sku"]]
    gltf = read_glb(MODELS / entry["file"])
    b = bbox_mm(gltf)
    dims = prod["product_dims_mm"]
    for k in ("w", "h", "d"):
        assert abs(b[k] - dims[k]) <= TOL_MM, f"{prod['sku']} {k}: 모델 {b[k]:.1f} / 카탈로그 {dims[k]}"
    # 바닥 가운데가 원점: 화면에서 center_xz에 그대로 놓는다
    assert abs(b["y0"]) <= 1 and abs(b["cx"]) <= TOL_MM and abs(b["cz"]) <= TOL_MM


def companions() -> dict:
    p = MODELS / "companions.json"
    return json.loads(p.read_text(encoding="utf-8"))["models"] if p.exists() else {}


@pytest.mark.parametrize("prod", CATALOG, ids=[p["sku"] for p in CATALOG])
def test_model_has_recolorable_finish(prod, index):
    """색 동그라미로 바꿀 finish 재질이 본체나 같이 놓이는 부품(companions.json) 중 하나에 있어야 한다."""
    files = [index["models"][prod["sku"]]["file"]]
    if prod["sku"] in companions():
        files.append(companions()[prod["sku"]]["file"])
    names = {m["name"] for f in files for m in read_glb(MODELS / f)["materials"]}
    assert "finish" in names


def test_water_purifier_faucet_is_placed_with_body():
    """정수기 색 옵션은 파우셋 색이다: 본체는 회색 고정, 파우셋(Ø48·높이 264·돌출 188 mm)이 finish를 가진다."""
    comps = companions()
    for sku in ("WU523AWB", "WU523ACB"):
        c = comps[sku]
        faucet = read_glb(MODELS / c["file"])
        assert "finish" in {m["name"] for m in faucet["materials"]}
        b = bbox_mm(faucet)
        assert abs(b["h"] - 264) <= TOL_MM and abs(b["y0"]) <= 1
        assert len(c["offset_m"]) == 3 and c["offset_m"][1] > 0.5  # 조리대 위
        body = read_glb(MODELS / f"{sku}.glb")
        assert "finish" not in {m["name"] for m in body["materials"]}


def test_products_with_figma_drawing_use_it():
    """data/drawings에 도면이 있는 제품은 도면대로 만든 모델이어야 한다."""
    index = json.loads((MODELS / "index.json").read_text(encoding="utf-8"))["models"]
    drawn = [p.stem for p in (ROOT / "data/drawings").glob("*.json")]
    assert drawn, "도면이 하나는 있어야 한다"
    for sku in drawn:
        assert index[sku]["layout"] == "drawing", sku
