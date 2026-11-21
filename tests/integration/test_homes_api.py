"""집 목록은 내 것만 보이고, 이름을 붙이고, 지울 수 있다."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

SAMPLE = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"
ADMIN = ("admin@housetwin.test", "admin-pass-1234")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    svc = Service(storage=tmp_path)
    main.app.dependency_overrides[main.get_service] = lambda: svc
    main.reset_login_limits()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


def signup(c, email):
    r = c.post("/api/auth/signup", json={"email": email, "password": "pass-word-1", "name": "홍길동", "role": "customer"})
    assert r.status_code == 201, r.text
    return bearer(r.json()["token"])


def upload(c, headers=None, **data):
    with open(SAMPLE, "rb") as f:
        r = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")},
                   data={"scanned_by": "customer", **data}, headers=headers or {})
    return r


def test_list_shows_only_my_homes(client):
    c = client
    kim, lee = signup(c, "kim@example.com"), signup(c, "lee@example.com")
    mine = upload(c, kim).json()
    upload(c, lee)
    upload(c)  # 로그인 없이 만든 집

    assert c.get("/api/projects").json() == []  # 로그인 안 하면 남의 집이 보이지 않는다
    assert [p["project_id"] for p in c.get("/api/projects", headers=kim).json()] == [mine["project_id"]]

    admin = bearer(c.post("/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}).json()["token"])
    assert len(c.get("/api/projects", headers=admin).json()) == 3


def test_home_name_is_saved_and_checked(client):
    c = client
    assert upload(c, name="  주방 겸 거실  ").json()["name"] == "주방 겸 거실"
    assert upload(c).json()["name"] == "room"  # 이름을 안 주면 올린 파일 이름
    assert upload(c, name="가" * 41).status_code == 422


def test_delete_needs_owner_or_link(client):
    c = client
    kim, lee = signup(c, "kim@example.com"), signup(c, "lee@example.com")
    mine = upload(c, kim).json()
    pid = mine["project_id"]

    assert c.delete(f"/api/projects/{pid}", headers=lee).status_code == 403
    assert c.delete(f"/api/projects/{pid}", params={"t": mine["share_token"]}).status_code == 403  # 주인 있는 집은 링크만으로 못 지운다
    assert c.delete(f"/api/projects/{pid}", headers=kim).status_code == 204
    assert c.get(f"/api/projects/{pid}").status_code == 404
    assert c.get("/api/projects", headers=kim).json() == []

    free = upload(c).json()
    assert c.delete(f"/api/projects/{free['project_id']}", params={"t": "wrong"}).status_code == 403
    assert c.delete(f"/api/projects/{free['project_id']}", params={"t": free["share_token"]}).status_code == 204


def test_sample_homes_are_served(client):
    for name in ("synthetic_room.usdz", "apt_living_kitchen.usdz", "ugscan_2026-11-18.usdz"):
        assert client.get(f"/api/samples/{name}").status_code == 200, name
    assert client.get("/api/samples/nope.usdz").status_code == 404
