"""로그인·회원가입(고객/기사), 기사 관리, 리모델링 저장(자동·수동)과 되돌리기."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

SAMPLE = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"
KITCHEN = [[0, 0], [3.0, 0], [3.0, 1.6], [0, 1.6]]
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


def signup(c, email, role="customer", **extra):
    body = {"email": email, "password": "pass-word-1", "name": "홍길동", "role": role, **extra}
    r = c.post("/api/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def login(c, email, password="pass-word-1"):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def upload(c, headers=None):
    with open(SAMPLE, "rb") as f:
        r = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")},
                   data={"scanned_by": "customer"}, headers=headers or {})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- 회원가입·로그인 ----------
def test_customer_signup_login_me_logout(client):
    c = client
    out = signup(c, "Kim@Example.com")
    assert out["user"]["role"] == "customer" and out["user"]["status"] == "active"
    assert out["user"]["email"] == "kim@example.com"
    assert "password" not in str(out["user"]).lower() and "pw" not in out["user"]
    assert c.get("/api/auth/me", headers=bearer(out["token"])).json()["email"] == "kim@example.com"

    r = login(c, "kim@example.com")
    assert r.status_code == 200
    tok = r.json()["token"]
    assert c.post("/api/auth/logout", headers=bearer(tok)).status_code == 204
    assert c.get("/api/auth/me", headers=bearer(tok)).status_code == 401
    assert c.get("/api/auth/me").status_code == 401


def test_signup_rejects_duplicates_weak_passwords_and_admin_role(client):
    c = client
    signup(c, "a@example.com")
    assert c.post("/api/auth/signup", json={"email": "A@example.com", "password": "pass-word-1", "name": "x",
                                             "role": "customer"}).status_code == 409
    assert c.post("/api/auth/signup", json={"email": "b@example.com", "password": "short", "name": "x",
                                             "role": "customer"}).status_code == 422
    assert c.post("/api/auth/signup", json={"email": "not-an-email", "password": "pass-word-1", "name": "x",
                                             "role": "customer"}).status_code == 422
    assert c.post("/api/auth/signup", json={"email": "c@example.com", "password": "pass-word-1", "name": "x",
                                             "role": "admin"}).status_code == 422


def test_wrong_password_is_generic_and_rate_limited(client):
    c = client
    signup(c, "a@example.com")
    r1, r2 = login(c, "a@example.com", "wrong-pass-1"), login(c, "nobody@example.com", "wrong-pass-1")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]
    for _ in range(6):
        r = login(c, "a@example.com", "wrong-pass-1")
    assert r.status_code == 429
    # 맞는 비밀번호도 잠깐은 막힌다
    assert login(c, "a@example.com").status_code == 429


# ---------- 기사 가입·승인 ----------
def test_technician_signup_needs_admin_approval(client):
    c = client
    t = signup(c, "tech@example.com", role="technician", phone="010-1234-5678", center="강남 서비스센터",
               employee_no="T-0042")
    assert t["user"]["role"] == "technician" and t["user"]["status"] == "pending"
    assert t["user"]["center"] == "강남 서비스센터"
    # 기사 전용 정보(상담 요청 목록)는 승인 전엔 못 본다
    c.post("/api/requests", json={"name": "고객", "contact": "010", "address": "주소"})
    assert c.get("/api/requests").status_code == 401
    assert c.get("/api/requests", headers=bearer(t["token"])).status_code == 403
    cust = signup(c, "cust@example.com")
    assert c.get("/api/requests", headers=bearer(cust["token"])).status_code == 403

    # 기사 정보 없이 기사 가입은 안 된다
    assert c.post("/api/auth/signup", json={"email": "t2@example.com", "password": "pass-word-1", "name": "x",
                                             "role": "technician"}).status_code == 422

    # 관리자: 기사 목록 → 승인
    adm = login(c, *ADMIN).json()
    assert adm["user"]["role"] == "admin"
    assert c.get("/api/admin/technicians", headers=bearer(cust["token"])).status_code == 403
    techs = c.get("/api/admin/technicians", headers=bearer(adm["token"])).json()
    assert [x["email"] for x in techs] == ["tech@example.com"]
    r = c.patch(f"/api/admin/technicians/{techs[0]['user_id']}", json={"status": "approved"},
                headers=bearer(adm["token"]))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert c.get("/api/requests", headers=bearer(t["token"])).status_code == 200

    # 정지하면 다시 막히고, 로그인도 안 된다
    c.patch(f"/api/admin/technicians/{techs[0]['user_id']}", json={"status": "suspended"}, headers=bearer(adm["token"]))
    assert c.get("/api/requests", headers=bearer(t["token"])).status_code in (401, 403)
    assert login(c, "tech@example.com").status_code == 403
    # 고객 계정은 기사 관리 대상이 아니다
    assert c.patch(f"/api/admin/technicians/{cust['user']['user_id']}", json={"status": "approved"},
                   headers=bearer(adm["token"])).status_code == 404


# ---------- 내 집·저장 ----------
def test_upload_while_logged_in_owns_project_and_lists_in_my_homes(client):
    c = client
    a, b = signup(c, "a@example.com"), signup(c, "b@example.com")
    p = upload(c, bearer(a["token"]))
    assert p["owner_id"] == a["user"]["user_id"]
    mine = c.get("/api/me/projects", headers=bearer(a["token"])).json()
    assert [x["project_id"] for x in mine] == [p["project_id"]]
    assert c.get("/api/me/projects", headers=bearer(b["token"])).json() == []
    # 공유 링크 토큰이 있어도 이미 주인이 있는 집은 가져갈 수 없다
    r = c.post(f"/api/projects/{p['project_id']}/claim", json={"share_token": p["share_token"]}, headers=bearer(b["token"]))
    assert r.status_code == 403


def test_claim_anonymous_project_with_share_token(client):
    c = client
    p = upload(c)
    a = signup(c, "a@example.com")
    assert c.post(f"/api/projects/{p['project_id']}/claim", json={"share_token": "wrong"},
                  headers=bearer(a["token"])).status_code == 403
    r = c.post(f"/api/projects/{p['project_id']}/claim", json={"share_token": p["share_token"]}, headers=bearer(a["token"]))
    assert r.status_code == 200 and r.json()["owner_id"] == a["user"]["user_id"]
    assert len(c.get("/api/me/projects", headers=bearer(a["token"])).json()) == 1


def test_manual_and_auto_save_then_restore(client):
    c = client
    a, b = signup(c, "a@example.com"), signup(c, "b@example.com")
    h = bearer(a["token"])
    p = upload(c, h)
    pid = p["project_id"]
    assert c.post(f"/api/projects/{pid}/saves", json={"kind": "manual"}).status_code == 401
    assert c.post(f"/api/projects/{pid}/saves", json={"kind": "manual"}, headers=bearer(b["token"])).status_code == 403

    c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": KITCHEN, "name": "주방"})
    c.post(f"/api/projects/{pid}/materials", json={"target": "wall", "hex_color": "#EEEEEE"})
    s1 = c.post(f"/api/projects/{pid}/saves", json={"kind": "manual", "label": "흰 벽 주방"}, headers=h)
    assert s1.status_code == 201, s1.text
    s1 = s1.json()
    assert s1["label"] == "흰 벽 주방" and s1["kind"] == "manual" and s1["zones"] == 1

    # 자동 저장은 한 칸을 계속 덮어쓴다
    c.post(f"/api/projects/{pid}/materials", json={"target": "wall", "hex_color": "#333333"})
    a1 = c.post(f"/api/projects/{pid}/saves", json={"kind": "auto"}, headers=h).json()
    a2 = c.post(f"/api/projects/{pid}/saves", json={"kind": "auto"}, headers=h).json()
    assert a1["save_id"] == a2["save_id"]
    saves = c.get(f"/api/projects/{pid}/saves", headers=h).json()
    assert sorted(x["kind"] for x in saves) == ["auto", "manual"]
    assert all("state" not in x for x in saves)

    # 주방 영역을 지우고 벽 색을 바꾼 뒤, 수동 저장본으로 되돌리기
    zid = c.get(f"/api/projects/{pid}/zones").json()[0]["zone_id"]
    c.delete(f"/api/projects/{pid}/zones/{zid}")
    v_before = c.get(f"/api/projects/{pid}/version").json()["version"]
    r = c.post(f"/api/projects/{pid}/saves/{s1['save_id']}/restore", headers=h)
    assert r.status_code == 200, r.text
    proj = c.get(f"/api/projects/{pid}").json()
    assert proj["scene_state"]["materials"]["wall"].upper() == "#EEEEEE"
    assert proj["version"] > v_before and proj["owner_id"] == a["user"]["user_id"]
    assert [z["name"] for z in c.get(f"/api/projects/{pid}/zones").json()] == ["주방"]

    # 지우기
    assert c.delete(f"/api/projects/{pid}/saves/{s1['save_id']}", headers=h).status_code == 204
    assert len(c.get(f"/api/projects/{pid}/saves", headers=h).json()) == 1


def test_assigned_technician_can_save_customer_home(client):
    c = client
    adm = login(c, *ADMIN).json()
    t = signup(c, "tech@example.com", role="technician", phone="010", center="센터", employee_no="T-1")
    c.patch(f"/api/admin/technicians/{t['user']['user_id']}", json={"status": "approved"}, headers=bearer(adm["token"]))
    with open(SAMPLE, "rb") as f:
        p = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")},
                   data={"scanned_by": "technician"}, headers=bearer(t["token"])).json()
    assert p["technician_id"] == t["user"]["user_id"] and p.get("owner_id") is None
    assert c.post(f"/api/projects/{p['project_id']}/saves", json={"kind": "manual"},
                  headers=bearer(t["token"])).status_code == 201
    assert [x["project_id"] for x in c.get("/api/me/projects", headers=bearer(t["token"])).json()] == [p["project_id"]]
