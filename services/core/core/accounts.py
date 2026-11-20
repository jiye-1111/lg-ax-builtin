"""계정: 고객·기사·관리자. 비밀번호는 scrypt로만 저장하고, 로그인 토큰은 해시만 저장한다.

- 고객: 가입하면 바로 쓴다.
- 기사: 서비스센터·사번·연락처를 받아 가입하고, 관리자가 승인해야 기사 기능을 쓴다.
- 관리자: 가입으로는 만들 수 없다. 서버 .env의 ADMIN_EMAIL·ADMIN_PASSWORD로 시작할 때 만든다.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from .store import Store

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
ROLES = ("customer", "technician")
TECH_STATUSES = ("pending", "approved", "suspended", "rejected")
SESSION_DAYS = 30
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


class AuthError(Exception):
    """401: 로그인이 필요하거나 토큰이 틀림"""


class Forbidden(Exception):
    """403: 로그인은 했지만 권한이 없음"""


class Conflict(Exception):
    """409: 이미 있는 이메일"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), h)


# 없는 이메일로 로그인해도 시간이 비슷하게 걸리게 (이메일 존재 여부 노출 방지)
_DUMMY = hash_password(secrets.token_hex(8))


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "pw"}


class Accounts:
    def __init__(self, db: Store):
        self.db = db
        self.ensure_admin()

    # ---- 관리자 ----
    def ensure_admin(self) -> None:
        email, pw = os.getenv("ADMIN_EMAIL", "").strip().lower(), os.getenv("ADMIN_PASSWORD", "")
        if not email or not pw:
            return
        if len(pw) < 10:
            raise ValueError("ADMIN_PASSWORD는 10자 이상이어야 합니다")
        u = self.find_by_email(email)
        if u is None:
            uid = self.db.next_id("u")
            u = {"user_id": uid, "email": email, "name": "관리자", "role": "admin", "status": "active",
                 "created_at": _now().isoformat(timespec="seconds")}
            self.db.put("email", email, {"user_id": uid})
        elif u["role"] != "admin":
            raise ValueError("ADMIN_EMAIL이 이미 고객·기사 계정으로 쓰이고 있습니다")
        if not verify_password(pw, u.get("pw", "")):
            u["pw"] = hash_password(pw)
        self.db.put("user", u["user_id"], u)

    # ---- 조회 ----
    def find_by_email(self, email: str) -> dict | None:
        ref = self.db.get("email", email.strip().lower())
        return self.db.get("user", ref["user_id"]) if ref else None

    def get(self, uid: str) -> dict | None:
        return self.db.get("user", uid)

    # ---- 가입·로그인 ----
    def signup(self, email: str, password: str, name: str, role: str, phone: str | None = None,
               center: str | None = None, employee_no: str | None = None) -> tuple[str, dict]:
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("이메일 형식이 아닙니다")
        if role not in ROLES:
            raise ValueError("가입 유형은 고객 또는 기사만 됩니다")
        if not (8 <= len(password) <= 128):
            raise ValueError("비밀번호는 8자 이상 128자 이하")
        if not name.strip():
            raise ValueError("이름을 넣어 주세요")
        if role == "technician" and not all(x and x.strip() for x in (phone, center, employee_no)):
            raise ValueError("기사 가입은 연락처·서비스센터·사번이 필요합니다")
        if self.find_by_email(email):
            raise Conflict("이미 가입된 이메일입니다")
        uid = self.db.next_id("u")
        u = {"user_id": uid, "email": email, "name": name.strip(), "role": role,
             "status": "pending" if role == "technician" else "active",
             "created_at": _now().isoformat(timespec="seconds"), "pw": hash_password(password)}
        if role == "technician":
            u.update(phone=phone.strip(), center=center.strip(), employee_no=employee_no.strip())
        self.db.put("email", email, {"user_id": uid})
        self.db.put("user", uid, u)
        return self._issue(u), public(u)

    def login(self, email: str, password: str) -> tuple[str, dict]:
        u = self.find_by_email(email)
        ok = verify_password(password, u["pw"] if u and u.get("pw") else _DUMMY)
        if not (u and ok):
            raise AuthError("이메일 또는 비밀번호가 맞지 않습니다")
        if u["status"] in ("suspended", "rejected"):
            raise Forbidden("이용이 중지된 계정입니다. 관리자에게 문의해 주세요")
        return self._issue(u), public(u)

    def _issue(self, u: dict) -> str:
        token = secrets.token_urlsafe(32)
        exp = (_now() + timedelta(days=SESSION_DAYS)).isoformat()
        self.db.put("session", _token_id(token), {"user_id": u["user_id"], "expires_at": exp})
        return token

    def logout(self, token: str) -> None:
        self.db.delete("session", _token_id(token))

    def user_for_token(self, token: str | None) -> dict | None:
        """토큰이 맞고 계정이 살아 있으면 계정(비밀번호 해시 뺀 것)."""
        if not token:
            return None
        sid = _token_id(token)
        s = self.db.get("session", sid)
        if not s:
            return None
        if datetime.fromisoformat(s["expires_at"]) < _now():
            self.db.delete("session", sid)
            return None
        u = self.get(s["user_id"])
        if not u or u["status"] in ("suspended", "rejected"):
            return None
        return public(u)

    # ---- 기사 관리 (관리자) ----
    def technicians(self) -> list[dict]:
        return [public(u) for u in self.db.list("user") if u["role"] == "technician"]

    def set_technician_status(self, uid: str, status: str) -> dict:
        if status not in TECH_STATUSES:
            raise ValueError(f"status는 {TECH_STATUSES} 중 하나")
        u = self.get(uid)
        if not u or u["role"] != "technician":
            raise KeyError(f"기사 계정 없음: {uid}")
        u["status"] = status
        u["status_at"] = _now().isoformat(timespec="seconds")
        self.db.put("user", uid, u)
        return public(u)


def is_approved_tech(u: dict | None) -> bool:
    return bool(u) and (u["role"] == "admin" or (u["role"] == "technician" and u["status"] == "approved"))
