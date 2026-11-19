"""시연 시나리오 1~10 (기획 §4) 통합 테스트 — 가상 카탈로그 사용."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

SAMPLE = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"
KITCHEN = [[0, 0], [3.0, 0], [3.0, 1.6], [0, 1.6]]
LIVING = [[0, 1.6], [5.2, 1.6], [5.2, 3.6], [0, 3.6]]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    svc = Service(storage=tmp_path)
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_full_demo_flow(client):
    c = client
    # 1 상담 요청
    r = c.post("/api/requests", json={"name": "시연 고객", "contact": "010-0000-0000", "address": "시연 주소",
                                      "preferred_at": "2026-12-01T10:00:00+09:00"})
    assert r.status_code == 201
    rid = r.json()["request_id"]

    # 3 스캔 등록 → 4 3D 생성
    with open(SAMPLE, "rb") as f:
        r = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")}, data={"request_id": rid})
    assert r.status_code == 201, r.text
    p = r.json()
    pid = p["project_id"]
    assert p["scene"]["glb"] and "/#/c/" in p["customer_url"]
    assert c.get(f"/api/projects/{pid}/files/scene.glb").content[:4] == b"glTF"
    room = c.get(f"/api/projects/{pid}/room").json()
    assert len(room["walls"]) == 4
    kitchen_wall = next(w for w in room["walls"] if abs(w["start"][1]) < 1e-6 and abs(w["end"][1]) < 1e-6)

    # 5 영역 지정
    z = c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": KITCHEN, "name": "주방"}).json()
    assert kitchen_wall["wall_id"] in z["auto_wall_ids"]
    zl = c.post(f"/api/projects/{pid}/zones", json={"purpose": "living", "polygon_m": LIVING}).json()

    # 6 스타일 (Claude/Codex가 MCP로 호출하는 것과 같은 서비스)
    v0 = c.get(f"/api/projects/{pid}/version").json()["version"]
    r = c.put(f"/api/projects/{pid}/style", json={"prompt": "화이트 우드 톤 미니멀", "palette": ["#F2EFEA", "#C8A27A"],
                                                 "materials": ["wood", "matte"]})
    assert r.status_code == 200
    assert c.get(f"/api/projects/{pid}/version").json()["version"] > v0

    # 8 추천: 스캔값만 → 최고 '조건부'
    rec = c.get(f"/api/projects/{pid}/zones/{z['zone_id']}/recommendations").json()["items"]
    assert rec and all(i["product"]["zone_fit"] == ["kitchen"] or "kitchen" in i["product"]["zone_fit"] for i in rec)
    assert {i["fit"]["verdict"] for i in rec} <= {"conditional", "unknown", "no_fit"}
    # 기존 하부장(0~1.2m) 때문에 가용 폭은 1.2~3.0 = 1.8m
    col = next(i for i in rec if i["product"]["sku"] == "DEMO-RF-01")
    assert col["fit"]["dims"]["width"]["available_mm"] == pytest.approx(1800, abs=1)
    assert col["cmf"][0]["score"] >= col["cmf"][-1]["score"]

    # F3 실측 보정 → 적합 가능
    r = c.put(f"/api/projects/{pid}/walls/{kitchen_wall['wall_id']}/measured",
              json={"length_m": 5.195, "height_m": 2.395, "depth_m": 1.6})
    assert r.status_code == 200 and r.json()["scanned"]["length_m"] == pytest.approx(5.2)
    rec = c.get(f"/api/projects/{pid}/zones/{z['zone_id']}/recommendations").json()["items"]
    col = next(i for i in rec if i["product"]["sku"] == "DEMO-RF-01")
    assert col["fit"]["verdict"] == "fit"
    assert col["fit"]["dims"]["width"]["source"] == "measured"
    big = next(i for i in rec if i["product"]["sku"] == "DEMO-RF-02")
    assert big["fit"]["verdict"] == "fit"  # 1.8m에 912+10 → 적합

    # 7 디자인 조작 + 9 배치 미리보기 + 렌더
    assert c.post(f"/api/projects/{pid}/materials", json={"target": "wall", "hex_color": "#F2EFEA", "finish": "matte"}).status_code == 200
    r = c.post(f"/api/projects/{pid}/placements", json={"zone_id": z["zone_id"], "sku": "DEMO-RF-01"})
    assert r.status_code == 200, r.text
    assert r.json()["scene_state"]["placements"][0]["sku"] == "DEMO-RF-01"
    r = c.post(f"/api/projects/{pid}/render")
    assert c.get(f"/api/projects/{pid}/files/render.png").content[:4] == b"\x89PNG"

    # 10 결과 화면
    res = c.get(f"/api/projects/{pid}/results").json()
    assert {zz["zone_id"] for zz in res["zones"]} == {z["zone_id"], zl["zone_id"]}
    assert res["project"]["status"] == "designed"


def test_validation_errors(client):
    c = client
    assert c.post("/api/projects", files={"file": ("x.txt", b"hello")}).status_code == 422
    assert c.get("/api/projects/p_999").status_code == 404
    with open(SAMPLE, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("room.usdz", f)}).json()["project_id"]
    assert c.put(f"/api/projects/{pid}/walls/w1/measured", json={"length_m": 999}).status_code == 422
    assert c.put(f"/api/projects/{pid}/walls/nope/measured", json={"length_m": 3}).status_code == 404
    assert c.put(f"/api/projects/{pid}/style", json={"palette": ["red"]}).status_code == 422
    assert c.post(f"/api/projects/{pid}/materials", json={"target": "roof", "hex_color": "#FFFFFF"}).status_code == 422


def test_real_ugscan_upload_builds_scene(client):
    real = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
    with open(real, "rb") as f:
        r = client.post("/api/projects", files={"file": ("ugscan.usdz", f, "model/vnd.usdz+zip")})
    assert r.status_code == 201, r.text
    pid = r.json()["project_id"]
    room = client.get(f"/api/projects/{pid}/room").json()
    assert len(room["walls"]) == 8 and len(room["openings"]) == 5
    assert client.get(f"/api/projects/{pid}/files/scene.glb").status_code == 200
