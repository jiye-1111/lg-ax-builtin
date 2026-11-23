"""주방 가전이 실제 집처럼 놓이는지: 인덕션은 상판 위, 식기세척기는 싱크대 옆, 키 큰 가전은 창을 가리지 않게.
하우니에게 가전 여러 개와 예산을 말하면 그 가전으로, 예산 안에서 조합을 만든다."""
import json
import math

import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

APT = main.config.ROOT / "data" / "samples" / "apt_living_kitchen.usdz"
BARE = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
CAT = json.loads((main.config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
SELL = [p for p in CAT if p.get("sale_status") == "ACTIVE" and p.get("price_krw")]
COOKTOP = next(p["sku"] for p in SELL if p["category"] == "cooktop")
DISH = next(p["sku"] for p in SELL if p["category"] == "dishwasher" and p["install_type"] == "built_in")
ASK = "4인 가족이고 리모델링하면서 냉장고랑 식기세척기를 새로 사야 해요. 가전 예산은 600만 원이에요."


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Service(storage=tmp_path / "st")
    s.ideator = lambda brief: None
    return s


@pytest.fixture
def c(svc):
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def home(c, path=APT, clear=False):
    with open(path, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    if clear:
        c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    return pid


def placements(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]


def test_cooktop_goes_on_the_scanned_counter(c):
    pid = home(c)
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": COOKTOP})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    assert x["on"] == "o1" and x["base_m"] == pytest.approx(0.9, abs=0.01)
    assert x["verdict"] != "no_fit"


def test_cooktop_in_a_home_without_counter_brings_a_base_cabinet(c):
    pid = home(c, BARE, clear=True)
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": COOKTOP})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    cabs = [y for y in placements(c, pid) if y["sku"] == "decor:basecab"]
    assert len(cabs) == 1
    assert x["on"] == cabs[0]["placement_id"] and x["base_m"] > 0.8
    assert x["verdict"] != "no_fit"


def test_cooktop_dropped_on_the_floor_by_hand_also_gets_a_cabinet(c):
    pid = home(c, BARE, clear=True)
    room = c.get(f"/api/projects/{pid}/room").json()
    xs = [v for w in room["walls"] for v in (w["start"][0], w["end"][0])]
    zs = [v for w in room["walls"] for v in (w["start"][1], w["end"][1])]
    mid = [(min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": COOKTOP, "center_xz": mid, "yaw_rad": 0, "snap": False})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    assert x["on"] and x["verdict"] != "no_fit"


def test_built_in_dishwasher_stands_right_next_to_the_counter(c):
    pid = home(c)
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": DISH})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    room = c.get(f"/api/projects/{pid}/room").json()
    o1 = next(o for o in room["objects"] if o["object_id"] == "o1")
    gap = math.dist(x["center_xz"], (o1["position"][0], o1["position"][2])) - o1["bbox_m"]["w"] / 2 - x["size_m"][0] / 2
    assert gap < 0.25, f"싱크대에서 {gap:.2f} m 떨어져 있다"


def test_combo_kitchen_appliances_land_where_they_would_in_a_real_home(c):
    pid = home(c)
    out = c.post(f"/api/projects/{pid}/combos", json={"categories": ["refrigerator", "dishwasher", "cooktop"],
                                                       "budget": 7_000_000, "prompt": "밝은 미니멀"}).json()
    for combo in out["combos"]:
        r = c.post(f"/api/projects/{pid}/combos/{combo['combo_id']}/apply")
        assert r.status_code == 200, r.text
        got = {x["sku"]: x for x in placements(c, pid)}
        by_cat = {p["category"]: got[p["sku"]] for p in CAT if p["sku"] in got}
        assert by_cat["cooktop"]["on"], "인덕션이 바닥에 있다"
        fridge = by_cat["refrigerator"]
        assert not any(z["code"] == "covers_window" for z in fridge["reasons"]), "냉장고가 창을 가린다"


def test_hauni_uses_every_appliance_named_and_stays_in_budget(c):
    pid = home(c)
    r = c.post(f"/api/projects/{pid}/assist", json={"prompt": ASK})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["type"] == "combos"
    assert {"refrigerator", "dishwasher"} <= set(out["categories"])
    assert "water_purifier" not in out["categories"]
    assert "냉장고·식기세척기" in out["message"]
    for combo in out["combos"]:
        cats = {it["category"] for it in combo["items"] if it["kind"] == "lg"}
        assert {"refrigerator", "dishwasher"} <= cats | set(), combo["missing"]
        assert combo["lg_total"] <= 6_000_000, f"{combo['name']} {combo['lg_total']}"


def test_combo_rows_do_not_talk_about_shares_or_finish_brands(c):
    pid = home(c)
    out = c.post(f"/api/projects/{pid}/combos", json={"categories": ["refrigerator"], "budget": 3_000_000,
                                                       "prompt": "밝은 미니멀"}).json()
    text = json.dumps(out, ensure_ascii=False)
    assert "몫" not in text
    for combo in out["combos"]:
        for f in combo["finishes"].values():
            assert "PANTONE" not in f["name"] and "동화" not in f["name"]


def test_english_furniture_words_from_the_ai_are_put_into_korean():
    from core.combos import plain_ko
    s = plain_ko("중심은 식탁(table)으로 두고 island나 basecab을 더해요. chair는 한쪽에.")
    assert not any(w in s for w in ("table", "island", "basecab", "chair"))
    assert "식탁" in s and "아일랜드" in s and "하부장" in s and "의자" in s


def test_turning_a_product_that_stands_against_a_wall_moves_it_clear_of_the_wall(c):
    pid = home(c)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "G646GBB031"}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}",
                json={"center_xz": x["center_xz"], "yaw_rad": x["yaw_rad"] + math.pi / 4, "snap": False})
    assert r.status_code == 200, r.text
    y = r.json()["placement"]
    assert y["yaw_rad"] == pytest.approx(x["yaw_rad"] + math.pi / 4)  # 돌린 방향은 그대로
    assert not any(z["code"] == "hits_wall" for z in y["reasons"]), y["reasons"]
    assert math.dist(y["center_xz"], x["center_xz"]) < 0.8  # 벽에서 필요한 만큼만 뗀다
