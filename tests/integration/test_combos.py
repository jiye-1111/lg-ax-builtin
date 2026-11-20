"""조합 추천: 가전 종류 + 목표 가격 + 분위기 → 조합 2~3개 → 하나 고르면 한 번에 들어간다."""
import pytest
from api import main
from core.combos import Idea, Ideas, Slot
from core.service import Service
from fastapi.testclient import TestClient

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Service(storage=tmp_path / "st")
    s.ideator = lambda brief: None   # 키 없음 → 규칙 템플릿
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


def test_hotel_bedroom_gives_three_different_combos_with_bed_and_fridge(c, pid):
    r = c.post(f"/api/projects/{pid}/combos",
               json={"categories": ["refrigerator"], "budget": 3_000_000, "prompt": "호텔 느낌 침실로 꾸며줘"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["purpose"] == "bedroom"
    combos = out["combos"]
    assert 2 <= len(combos) <= 3
    assert len({c["plan"] for c in combos}) == len(combos)  # 성격이 다르다
    for cb in combos:
        kinds = [i["name"] for i in cb["items"]]
        assert "침대" in kinds
        lg = [i for i in cb["items"] if i["kind"] == "lg"]
        assert len(lg) <= 1   # 냉장고는 조합마다 딱 하나
        if lg:
            assert lg[0]["category"] == "refrigerator" and lg[0]["price"] and lg[0]["why"]
            assert cb["lg_total"] == lg[0]["price"]
        assert cb["why"] and cb["tips"]
    # 아끼는 조합이 한 단계 위 조합보다 비싸지 않다
    by = {cb["plan"]: cb["lg_total"] for cb in combos}
    if by.get("save") and by.get("upgrade"):
        assert by["save"] <= by["upgrade"]


def test_apply_puts_everything_at_once_and_replaces_previous_combo(c, pid):
    combos = c.post(f"/api/projects/{pid}/combos", json={"prompt": "호텔 같은 침실", "categories": ["air_purifier"]}).json()["combos"]
    r = c.post(f"/api/projects/{pid}/combos/{combos[0]['combo_id']}/apply")
    assert r.status_code == 200, r.text
    pls = r.json()["scene_state"]["placements"]
    assert len(pls) >= 3 and all(x["combo"] == "c1" for x in pls)
    assert r.json()["scene_state"]["finish_ids"]  # 벽지·바닥재도 같이
    # 다른 조합을 고르면 앞 조합 것은 빠진다
    r2 = c.post(f"/api/projects/{pid}/combos/{combos[1]['combo_id']}/apply").json()
    assert all(x["combo"] == "c2" for x in r2["scene_state"]["placements"])


def test_things_placed_by_hand_stay(c, pid):
    c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:plant"})
    combos = c.post(f"/api/projects/{pid}/combos", json={"prompt": "거실 모던하게"}).json()["combos"]
    pls = c.post(f"/api/projects/{pid}/combos/{combos[0]['combo_id']}/apply").json()["scene_state"]["placements"]
    assert any(not x.get("combo") and x["sku"] == "decor:plant" for x in pls)


def test_ai_concept_is_used_but_code_picks_products(svc, c, pid):
    seen = {}

    def fake(brief):
        seen["brief"] = brief
        idea = Idea(name="갤러리 거실", why="벽 하나를 비워 두면 그림 같은 거실이 돼요.", tips=["조명은 벽 쪽으로"],
                    palette=["#F2F0EC", "#333333"], materials=["minimal", "matte"], wall_texture="paint", floor_texture="stone",
                    furniture=[Slot(kind="sofa", role="anchor"), Slot(kind="coffee", role="front")],
                    price_plan="save", appliance_point="무광 어두운 색")
        return Ideas(purpose="living", ideas=[idea, idea.model_copy(update={"name": "B", "price_plan": "target"})])

    svc.ideator = fake
    out = c.post(f"/api/projects/{pid}/combos", json={"categories": ["tv"], "budget": 2_000_000}).json()
    assert out["engine"] == "ai" and out["combos"][0]["name"] == "갤러리 거실"
    assert "TV" in seen["brief"] and "200만 원" in seen["brief"] and "m" in seen["brief"]
    tv = [i for i in out["combos"][0]["items"] if i["kind"] == "lg"]
    assert tv and tv[0]["category"] == "tv"  # 제품은 카탈로그에서 코드가 고른 것


def test_bad_input_is_rejected(c, pid):
    assert c.post(f"/api/projects/{pid}/combos", json={"categories": ["spaceship"]}).status_code == 422
    assert c.post(f"/api/projects/{pid}/combos", json={"budget": 10}).status_code == 422
    assert c.post(f"/api/projects/{pid}/combos/zz/apply").status_code == 404


def test_haeuni_answers_one_product_or_combos(c, pid):
    r = c.post(f"/api/projects/{pid}/assist", json={"prompt": "냉장고 추천해줘"}).json()
    assert r["type"] == "products" and 1 <= len(r["items"]) <= 3
    assert "가장 잘 맞아요" in r["message"] and "종을 찾았어요" not in r["message"]
    r2 = c.post(f"/api/projects/{pid}/assist", json={"prompt": "호텔 느낌으로 냉장고랑 침대 넣어서 방 꾸며줘"}).json()
    assert r2["type"] == "combos" and r2["combos"] and "refrigerator" in r2["categories"]


def test_clear_combo_keeps_hand_placed(c, pid):
    c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:plant"})
    cb = c.post(f"/api/projects/{pid}/combos", json={"prompt": "호텔 침실"}).json()["combos"][0]
    c.post(f"/api/projects/{pid}/combos/{cb['combo_id']}/apply")
    pls = c.delete(f"/api/projects/{pid}/combos/applied").json()["scene_state"]["placements"]
    assert len(pls) == 1 and pls[0]["sku"] == "decor:plant"


def test_room_word_in_product_question_still_gives_one_product(c, pid):
    r = c.post(f"/api/projects/{pid}/assist", json={"prompt": "방에 놓을 공기청정기 추천해줘"}).json()
    assert r["type"] == "products"


def test_products_without_a_color_name_never_get_a_color_reason(svc):
    from recommender.cmf import StyleTags
    bare = next(p for p in svc.catalog.products if p.cmf_options and p.cmf_options[0].color is None)
    assert svc._color_score(bare, StyleTags()) == (0.5, None)
