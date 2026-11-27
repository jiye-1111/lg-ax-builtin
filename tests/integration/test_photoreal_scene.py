"""실사로 보기: 장면에 있는 것만 그 자리에. AI가 소파를 더 그리거나, 침대를 소파로 바꾸거나, 공유기를 띄우면 안 된다.

1) 웹이 화면에 보이는 물건 전부(LG 제품·가구·스캔 가구·공유기)의 화면 자리를 보낸다
2) 서버가 그 목록을 이름·자리·무엇 위에 있는지로 적어 프롬프트에 넣는다 (목록 밖은 빈 바닥)
3) 다 그린 뒤 3D와 견줘 본다. 더하거나 뺀 게 있으면 그걸 짚어 한 번 더 그리고, 그래도 틀리면 Blender로
"""
import base64
import io
from types import SimpleNamespace as NS

import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient
from PIL import Image

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
W, H = 1536, 1024
CAM = {"pos": [8.0, 6.0, 9.0], "target": [3.5, 1.0, 5.0], "fov": 45}


def png_url(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


class AI:
    def __init__(self):
        self.prompts = []

    def edit(self, **kw):
        self.prompts.append(kw["prompt"])
        src = kw["image"][0] if isinstance(kw["image"], list) else kw["image"]
        out = Image.open(io.BytesIO(src[1])).convert("RGB").point(lambda v: min(255, v + 10))
        b = io.BytesIO()
        out.save(b, "PNG")
        return NS(data=[NS(b64_json=base64.b64encode(b.getvalue()).decode())])


class Checker:
    """3D와 AI 그림을 견줘 본 결과를 정해 둔다 (차례대로 하나씩 돌려준다)"""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, view, out, scene_lines):
        self.calls.append(scene_lines)
        return self.answers.pop(0) if self.answers else []


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    s = Service(storage=tmp_path / "st")
    s.image_client = AI()
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


def place(c, pid, sku, xz, size=None):
    body = {"sku": sku, "center_xz": xz, "snap": False, **({"size_m": size} if size else {})}
    r = c.post(f"/api/projects/{pid}/placements", json=body)
    assert r.status_code == 200, r.text
    return r.json()["scene_state"]["placements"][-1]["placement_id"]


def shot(**kw):
    view = Image.new("RGB", (W, H), (200, 190, 180))
    mask = Image.new("RGB", (W, H), (0, 0, 0))
    return {"image": png_url(view), "mask": png_url(mask), "camera": CAM, **kw}


@pytest.fixture
def scene(c, pid):
    """침대·식탁, 식탁 위 공유기, 스캔한 의자 하나가 화면에 보인다"""
    bed = place(c, pid, "decor:bed", [1.0, 1.0])
    table = place(c, pid, "decor:table", [3.0, 3.0])
    assert c.put(f"/api/projects/{pid}/router", json={"center_xz": [3.0, 3.0]}).status_code == 200
    objs = [{"ref": bed, "box": [0.7, 0.55, 0.98, 0.95]}, {"ref": table, "box": [0.4, 0.5, 0.6, 0.7]},
            {"ref": "router", "box": [0.48, 0.5, 0.52, 0.55]}, {"ref": "obj:o2", "box": [0.1, 0.2, 0.15, 0.3]}]
    return objs


def test_every_object_on_screen_is_listed_with_its_place_and_nothing_else_may_be_added(c, svc, pid, scene):
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene))
    assert r.status_code == 200, r.text
    p = svc.image_client.prompts[-1]
    assert "exactly 4 objects" in p
    assert "a bed" in p and "x 70-98%" in p          # 침대는 침대로, 그 자리에
    assert "a dining table" in p and "a chair" in p
    router = next(line for line in p.splitlines() if line.startswith("Object") and "Wi-Fi router" in line)
    assert "on top of object" in router                # 공유기는 식탁 위에 (떠 있지 않게)
    assert "empty" in p and "bare floor" in p


def test_router_on_the_floor_says_so(c, svc, pid):
    assert c.put(f"/api/projects/{pid}/router", json={"center_xz": [9.5, 9.5]}).status_code == 200
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=[{"ref": "router", "box": [0.4, 0.5, 0.45, 0.55]}]))
    assert r.status_code == 200, r.text
    router = next(line for line in svc.image_client.prompts[-1].splitlines() if line.startswith("Object") and "Wi-Fi router" in line)
    assert "on the floor" in router


def test_unknown_refs_are_ignored_and_bad_refs_rejected(c, svc, pid):
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=[{"ref": "pl_nope", "box": [0.1, 0.1, 0.2, 0.2]}]))
    assert r.status_code == 200 and "exactly 0 objects" in svc.image_client.prompts[-1]
    for bad in ([{"ref": "../x", "box": [0, 0, 1, 1]}], [{"ref": "router", "box": [0, 0, 2, 1]}]):
        assert c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=bad)).status_code == 422


def test_added_sofa_is_pointed_out_and_drawn_again(c, svc, pid, scene):
    svc.photo_checker = Checker([{"kind": "added", "what": "a sofa", "where": "lower left"}], [])
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene))
    assert r.status_code == 200 and r.json()["model"] != "blender"
    assert len(svc.image_client.prompts) == 2
    again = svc.image_client.prompts[1]
    assert "a sofa" in again and "lower left" in again and "remove" in again.lower()
    assert any("a bed" in x for x in svc.photo_checker.calls[0])  # 견줘 볼 때도 같은 목록을 준다


def test_still_wrong_after_the_second_try_goes_to_blender(c, svc, pid, scene, monkeypatch):
    import json
    import subprocess

    from worker import runner

    def run(cmd, **kw):
        job = json.loads(open(cmd[cmd.index("--job") + 1], encoding="utf-8").read())
        Image.new("RGB", (48, 32), (90, 120, 150)).save(job["out_png"], "PNG")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(runner, "blender_bin", lambda: "blender")
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setenv("USE_BLENDER", "1")
    bad = [{"kind": "changed", "what": "the bed became a sofa", "where": "right"}]
    svc.photo_checker = Checker(bad, bad)
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene))
    assert r.status_code == 200 and r.json()["model"] == "blender"
    assert len(svc.image_client.prompts) == 2


def test_without_blender_the_better_try_is_kept(c, svc, pid, scene, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    two = [{"kind": "added", "what": "a sofa", "where": "left"}, {"kind": "added", "what": "a lamp", "where": "top"}]
    one = [{"kind": "added", "what": "a lamp", "where": "top"}]
    svc.photo_checker = Checker(two, one)
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene))
    assert r.status_code == 200 and r.json()["model"] != "blender"
    notes = (svc.pdir(pid) / "scene" / "photoreal_notes.json").read_text(encoding="utf-8")
    assert "a lamp" in notes  # 무엇이 틀렸는지는 남겨 둔다 (웹에는 안 나감)


def test_a_retry_counts_once_against_the_limit(c, svc, pid, scene):
    svc.photo_checker = Checker([{"kind": "added", "what": "a sofa", "where": "left"}], [])
    codes = [c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene)).status_code for _ in range(3)]
    assert codes == [200, 200, 200]


def test_photo_realism_words_but_no_staging(c, svc, pid, scene):
    r = c.post(f"/api/projects/{pid}/photoreal", json=shot(objects=scene))
    assert r.status_code == 200
    p = svc.image_client.prompts[-1]
    assert "not a render" in p and "no styling" in p and "no leaf or curtain shadows" in p
    assert "plants" in p  # 식물·소품도 더하지 않는다
