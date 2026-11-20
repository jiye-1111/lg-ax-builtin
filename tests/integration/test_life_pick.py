"""하우니에 생활 이야기 → 가전마다 LGE.COM 가이드 용량 안에서 이 집에 맞는 하나 + 한 줄 이유 → 이어서 배치 추천."""
import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient
from recommender.lifestyle import Life

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Service(storage=tmp_path / "st")
    s.ideator = lambda brief, image=None: None
    return s


@pytest.fixture
def c(svc):
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(REAL, "rb") as f:
        return c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]


def say(c, pid, text, **kw):
    r = c.post(f"/api/projects/{pid}/assist", json={"prompt": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_family_story_picks_one_product_per_appliance_in_guide_range(c, svc, pid):
    d = say(c, pid, "맞벌이 4인 가족, 장은 주말에 몰아서 봐요. 아기도 있어요")
    assert d["type"] == "life" and d["engine"] == "rules"
    by = {it["need"]["category"]: it for it in d["items"]}
    assert set(by) == {"refrigerator", "washer_dryer"}  # 김치 말 없음 → 김치냉장고 없음, 맞벌이 → 워시콤보
    fridge = by["refrigerator"]["product"]
    assert 600 <= fridge["options"]["capacity_l"] <= 699          # 식재료 많은 4인 → 600L대
    assert by["washer_dryer"]["product"]["options"]["wash_kg"] >= 25
    for it in d["items"]:
        assert it["need"]["source_url"].startswith("https://") and it["need"]["why"] and it["reasons"]
        assert (it["fit"] or {}).get("verdict") != "no_fit"  # 영역을 안 그렸으면 판정 없음
        assert svc.catalog.get(it["product"]["sku"]).sale_status in (None, "ACTIVE", "SOLD_OUT")
    assert "4인" in d["message"] and "LGE.COM" in d["message"]


def test_naming_one_appliance_picks_only_that(c, pid):
    d = say(c, pid, "2인 가구인데 냉장고 추천해 줘")
    assert [it["need"]["category"] for it in d["items"]] == ["refrigerator"]
    assert 300 <= d["items"][0]["product"]["options"]["capacity_l"] <= 500


def test_kimchi_story_adds_kimchi_fridge(c, pid):
    d = say(c, pid, "네 식구고 김장을 많이 해요")
    kim = next(it for it in d["items"] if it["need"]["category"] == "kimchi_refrigerator")
    assert 480 <= kim["product"]["options"]["capacity_l"] <= 499


def test_ai_reads_facts_but_code_picks(c, svc, pid):
    svc.life_reader = lambda text: (Life(people=2), "openai")
    d = say(c, pid, "둘이 살아요")
    assert d["engine"] == "openai" and d["items"][0]["need"]["label"] == "300~500L"


def test_vague_story_asks_for_more(c, svc, pid):
    svc.life_reader = lambda text: (Life(), "rules")
    d = say(c, pid, "우리 가족 이야기")
    assert d["type"] == "life" and not d["items"] and "가족 수" in d["message"]


def test_picked_appliances_continue_into_combos(c, pid):
    d = say(c, pid, "2인 가구", categories=["refrigerator"])
    assert d["type"] == "combos" and d["combos"]
    for cb in d["combos"]:
        lg = [i for i in cb["items"] if i["kind"] == "lg"]
        assert all(i["category"] == "refrigerator" for i in lg)


def test_decor_talk_still_goes_to_combos(c, pid):
    assert say(c, pid, "4인 가족 거실을 호텔 느낌으로 꾸며 줘")["type"] == "combos"


def test_combos_from_life_keep_the_guide_capacity(c, svc, pid):
    life = {"people": 4, "kimchi": "lots"}
    d = say(c, pid, "네 식구고 김장을 많이 해요", categories=["kimchi_refrigerator"], life=life)
    assert d["type"] == "combos" and d["combos"]
    lg = [i for cb in d["combos"] for i in cb["items"] if i["kind"] == "lg"]
    assert lg and all(480 <= svc.catalog.get(i["sku"]).options["capacity_l"] <= 499 for i in lg)
