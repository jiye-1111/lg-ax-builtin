"""제품 3D 모델(apps/web/models/products/*.glb)이 카탈로그 치수와 맞는지 확인한다.

지금 화면은 전달받은 모델 묶음(LG-HANDOFF-01)만 쓴다. tools/catalog/import_lg_handoff.mjs가 모델명별 파일로 풀어 둔다.
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
SHOWN = [p for p in CATALOG if p["sku"] in LINEUP]  # 화면에 내놓는 모델


@pytest.fixture(scope="module")
def index():
    return json.loads((MODELS / "index.json").read_text(encoding="utf-8"))


def test_index_lists_exactly_the_lineup(index):
    assert set(index["models"]) == set(LINEUP) == {p["sku"] for p in SHOWN}
    assert {f.stem for f in MODELS.glob("*.glb")} == set(LINEUP)
    assert all(e["layout"] == "handoff" for e in index["models"].values())


@pytest.mark.parametrize("prod", SHOWN, ids=[p["sku"] for p in SHOWN])
def test_model_matches_catalog_dims(prod, index):
    entry = index["models"][prod["sku"]]
    gltf = read_glb(MODELS / entry["file"])
    b = bbox_mm(gltf)
    dims = prod["product_dims_mm"]
    for k in ("w", "h", "d"):
        assert abs(b[k] - dims[k]) <= TOL_MM, f"{prod['sku']} {k}: 모델 {b[k]:.1f} / 카탈로그 {dims[k]}"
    # 가운데가 원점: 화면에서 center_xz에 그대로 놓는다. 높이 기준은 전달본 그대로 (handoff.json y0_mm)
    y0 = handoff()[prod["sku"]]["y0_mm"]
    assert abs(b["y0"] - y0) <= 1 and abs(b["cx"]) <= TOL_MM and abs(b["cz"]) <= TOL_MM


def handoff() -> dict:
    """전달받은 모델 묶음에서 가져온 제품. 색이 모델에 들어 있고 원점은 전달본 기준이다."""
    p = MODELS / "handoff.json"
    return json.loads(p.read_text(encoding="utf-8"))["models"] if p.exists() else {}


def test_handoff_models_keep_their_datum_and_colour():
    """전달본 모델: 색 변형 확장은 풀어서 저장하고, 인덕션은 상판에 닿는 면이 0이라 55 mm가 아래로 들어간다."""
    models = handoff()
    assert set(models) == set(LINEUP) and len(models) == 56
    by_sku = {p["sku"]: p for p in CATALOG}
    for sku, info in models.items():
        gltf = read_glb(MODELS / f"{sku}.glb")
        assert "KHR_materials_variants" not in gltf.get("extensionsUsed", []), sku
        names = {m["name"] for m in gltf["materials"]}
        assert not names & {"finish", "glass"}, f"{sku}: 화면이 덧칠하는 재질 이름과 겹친다"
        b = bbox_mm(gltf)
        assert abs(b["y0"] - info["y0_mm"]) <= 1
        if "counter" in info["datum"]:
            assert info["y0_mm"] == -55 and by_sku[sku]["category"] == "cooktop", sku
        elif "ceiling" in info["datum"]:
            assert info["y0_mm"] < 0, sku  # 천장에 닿는 면이 0이고 판넬이 그 아래로 내려온다
        else:
            assert info["y0_mm"] == 0, sku
        assert (ROOT / "apps/web/img/products" / f"{sku}.webp").exists()


def test_own_models_are_gone():
    """직접 만든 모델은 쓰지 않기로 해서 저장소에 두지 않는다. 화면에는 전달받은 모델만 있다."""
    assert not (ROOT / "archive/own-models-2026-11-24").exists()
    index = json.loads((ROOT / "apps/web/models/products/index.json").read_text(encoding="utf-8"))["models"]
    assert set(index) == set(LINEUP)
