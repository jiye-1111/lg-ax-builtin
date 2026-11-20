"""마감재 카탈로그·적용, 자연어 AI 스타일 추천 API."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.ai_style import StyleIntent
from core.service import Service

SAMPLE = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"
KITCHEN = [[0, 0], [3.0, 0], [3.0, 1.6], [0, 1.6]]


def fake_stylist(prompt, catalog_brief=""):
    s = StyleIntent(palette=["#E6E3DE", "#2B2B2B"], materials=["stone", "black"], summary="대리석과 블랙 포인트",
                    wall_texture="stone", floor_texture="stone")
    s.engine = "claude"
    return s


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    svc = Service(storage=tmp_path, stylist=fake_stylist)
    main.app.dependency_overrides[main.get_service] = lambda: svc
    c = TestClient(main.app)
    with open(SAMPLE, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")}).json()["project_id"]
    yield c, pid
    main.app.dependency_overrides.clear()


def test_list_finishes(ctx):
    c, _ = ctx
    r = c.get("/api/finishes").json()
    assert {f["kind"] for f in r["finishes"]} == {"wall", "floor"}
    assert all(f["source_url"] for f in r["finishes"])


def test_apply_finish_sets_color_and_id(ctx):
    c, pid = ctx
    r = c.post(f"/api/projects/{pid}/finishes", json={"finish_id": "w_lx_diamant_plaster", "tone": "#C08E73"})
    assert r.status_code == 200, r.text
    st = c.get(f"/api/projects/{pid}").json()["scene_state"]
    assert st["finish_ids"]["wall"] == {"id": "w_lx_diamant_plaster", "tone": "#C08E73"}
    assert st["materials"]["wall"] == "#C08E73"


def test_apply_finish_default_tone_and_errors(ctx):
    c, pid = ctx
    assert c.post(f"/api/projects/{pid}/finishes", json={"finish_id": "f_dongwha_kang_linea"}).status_code == 200
    st = c.get(f"/api/projects/{pid}").json()["scene_state"]
    assert st["materials"]["floor"] == "#E2CDB0"
    assert c.post(f"/api/projects/{pid}/finishes", json={"finish_id": "nope"}).status_code == 404
    assert c.post(f"/api/projects/{pid}/finishes", json={"finish_id": "f_dongwha_kang_linea", "tone": "#000000"}).status_code == 422


def test_ai_style_saves_style_applies_finishes_and_changes_recommendations(ctx):
    c, pid = ctx
    zid = c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": KITCHEN}).json()["zone_id"]
    r = c.post(f"/api/projects/{pid}/style/ai", json={"prompt": "대리석 느낌에 블랙 포인트로 시크하게"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["engine"] == "claude" and d["summary"]
    assert d["style"]["palette"] == ["#E6E3DE", "#2B2B2B"]
    assert d["finishes"]["floor"][0]["finish"]["texture"] == "stone"
    assert d["applied"]["floor"]["finish"]["texture"] == "stone"
    p = c.get(f"/api/projects/{pid}").json()
    assert p["style"]["prompt"] == "대리석 느낌에 블랙 포인트로 시크하게"
    assert p["scene_state"]["finish_ids"]["floor"]["id"] == d["applied"]["floor"]["finish"]["id"]
    recs = c.get(f"/api/projects/{pid}/zones/{zid}/recommendations").json()["items"]
    assert any(it["cmf"] and it["cmf"][0]["score"] > 0 for it in recs)


def test_ai_style_can_skip_applying(ctx):
    c, pid = ctx
    d = c.post(f"/api/projects/{pid}/style/ai", json={"prompt": "화이트", "apply_finishes": False}).json()
    assert d["applied"] == {}
    assert not c.get(f"/api/projects/{pid}").json()["scene_state"].get("finish_ids")


def test_ai_style_rejects_empty_prompt(ctx):
    c, pid = ctx
    assert c.post(f"/api/projects/{pid}/style/ai", json={"prompt": "  "}).status_code == 422
