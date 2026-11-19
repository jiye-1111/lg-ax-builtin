"""스캔 가구 3D 모델(apps/web/models/furniture/*.glb) 구성 확인.

build_furniture.py(Blender)가 종류별 기준 크기로 만들고, 웹은 스캔 크기에 맞춰 부품별로 늘린다.
부품 extras.rig = 축(x 폭, y 높이, z 깊이)마다 한 글자:
  s = 크기·위치를 같이 늘림, p = 위치만 늘리고 크기 유지, e = 크기 유지하고 가까운 모서리와 거리 유지
"""
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "apps/web/models/furniture"
NEEDED = ["chair", "table", "storage", "sofa", "bed"]


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    n, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + n])


def node_bounds(g: dict) -> tuple[list[float], list[float]]:
    lo, hi = [1e9] * 3, [-1e9] * 3
    for node in g["nodes"]:
        if "mesh" not in node:
            continue
        t = node.get("translation", [0, 0, 0])
        for prim in g["meshes"][node["mesh"]]["primitives"]:
            a = g["accessors"][prim["attributes"]["POSITION"]]
            lo = [min(x, y + z) for x, y, z in zip(lo, a["min"], t)]
            hi = [max(x, y + z) for x, y, z in zip(hi, a["max"], t)]
    return lo, hi


@pytest.fixture(scope="module")
def index():
    return json.loads((DIR / "index.json").read_text(encoding="utf-8"))


def test_index_covers_roomplan_categories(index):
    assert set(NEEDED) <= set(index["models"])


@pytest.mark.parametrize("cat", NEEDED)
def test_model_bounds_match_reference_size(cat, index):
    e = index["models"][cat]
    lo, hi = node_bounds(read_glb(DIR / e["file"]))
    ref = e["ref_m"]
    for k, i in (("w", 0), ("h", 1), ("d", 2)):
        assert abs((hi[i] - lo[i]) - ref[k]) < 0.003, f"{cat} {k}"
    assert abs(lo[1]) < 0.002 and abs(hi[0] + lo[0]) < 0.003 and abs(hi[2] + lo[2]) < 0.003


@pytest.mark.parametrize("cat", NEEDED)
def test_every_part_has_rig_and_no_baked_rotation(cat, index):
    g = read_glb(DIR / index["models"][cat]["file"])
    parts = [n for n in g["nodes"] if "mesh" in n]
    assert len(parts) >= 3
    for n in parts:
        rig = (n.get("extras") or {}).get("rig", "")
        assert len(rig) == 3 and set(rig) <= set("spe"), n.get("name")
        assert "rotation" not in n and "scale" not in n
