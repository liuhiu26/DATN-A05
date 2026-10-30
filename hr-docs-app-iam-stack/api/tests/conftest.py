"""Test không cần Docker: Mongo giả (mongomock), token RS256 tự ký, policy engine = Casbin
(hoặc OPA nếu đặt OPA_URL trỏ tới OPA đang chạy)."""
import os
import time

os.environ.setdefault("ACCESS_LOG_FILE", "")
os.environ.setdefault("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")

import jwt
import mongomock
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import authz, config, db, security
from app.authz.casbin_engine import CasbinEngine
from app.seed_data import USERS

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
IDS = {u[0]: u[1] for u in USERS}
ROLE = {u[0]: u[3] for u in USERS}
DEPT = {u[0]: u[4] for u in USERS}


def make_token(username: str, **override) -> str:
    now = int(time.time())
    claims = {
        "iss": config.KEYCLOAK_ISSUER, "aud": ["hrdocs-api", "account"], "sub": IDS[username],
        "iat": now, "exp": now + 300, "preferred_username": username, "email": f"{username}@corp.local",
        "realm_access": {"roles": ["default-roles-hrdocs", ROLE[username]]},
        "department": [DEPT[username]] if DEPT[username] else [],
    }
    claims.update(override)
    return jwt.encode(claims, KEY, algorithm="RS256")


class FakeKeycloakAdmin:
    def __init__(self):
        self.calls = []

    def create_user(self, **kw):
        self.calls.append(("create", kw))
        return "new-user-id"

    def delete_user(self, user_id):
        self.calls.append(("delete", user_id))

    def set_role(self, user_id, role):
        self.calls.append(("role", user_id, role))

    def set_department(self, user_id, dept):
        self.calls.append(("dept", user_id, dept))

    def set_enabled(self, user_id, enabled):
        self.calls.append(("enabled", user_id, enabled))


@pytest.fixture
def client(monkeypatch):
    from app import keycloak_admin
    from app.main import app
    from app.seed import seed

    db.set_db(mongomock.MongoClient(tz_aware=True)["test"])
    seed()
    monkeypatch.setattr(security, "_signing_key", lambda token: KEY.public_key())
    authz.set_engine(CasbinEngine())
    kc = FakeKeycloakAdmin()
    keycloak_admin.set_admin(kc)
    c = TestClient(app)
    c.kc = kc
    return c


def auth(username: str) -> dict:
    return {"Authorization": f"Bearer {make_token(username)}"}
