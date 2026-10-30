from datetime import datetime
from unittest import mock

import pytest

from app import db
from app.authz import casbin_engine

from .conftest import IDS, KEY, auth, make_token


def doc_id(owner: str, cls: str) -> str:
    d = db.get_db().documents.find_one({"owner_id": IDS[owner], "classification": cls})
    return str(d["_id"])


def at_hour(hour):
    return mock.patch.object(casbin_engine, "working_hours", lambda _ns: 8 <= hour < 18)


def test_requires_token(client):
    assert client.get("/api/documents").status_code == 401


def test_rejects_wrong_audience_and_bad_signature(client):
    assert client.get("/api/documents", headers={"Authorization": f"Bearer {make_token('alice', aud='other')}"}).status_code == 401
    forged = make_token("alice")[:-4] + "AAAA"
    assert client.get("/api/documents", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


@pytest.mark.parametrize("user,expected", [("alice", 200), ("it.manager", 200), ("admin", 200), ("bob", 403), ("hr.manager", 403)])
def test_r1_r2_read(client, user, expected):
    assert client.get(f"/api/documents/{doc_id('alice', 'internal')}", headers=auth(user)).status_code == expected


@pytest.mark.parametrize("hour,expected", [(10, 200), (20, 403)])
def test_r3_confidential_hours(client, hour, expected):
    with at_hour(hour):
        res = client.get(f"/api/documents/{doc_id('alice', 'confidential')}", headers=auth("alice"))
    assert res.status_code == expected


def test_r1_update_only_owner_or_admin(client):
    d = doc_id("alice", "internal")
    assert client.put(f"/api/documents/{d}", json={"title": "x"}, headers=auth("alice")).status_code == 200
    assert client.put(f"/api/documents/{d}", json={"title": "x"}, headers=auth("it.manager")).status_code == 403
    assert client.put(f"/api/documents/{d}", json={"owner_id": IDS["bob"]}, headers=auth("alice")).status_code == 400


@pytest.mark.parametrize("field", ["role", "salary"])
def test_r4_no_self_role_salary(client, field):
    for user in ("alice", "admin"):
        res = client.patch(f"/api/employees/{IDS[user]}", json={field: "manager" if field == "role" else 1}, headers=auth(user))
        assert res.status_code == 403 and "R4_NO_SELF_ROLE_SALARY" in res.json()["error"]


def test_admin_role_change_syncs_keycloak(client):
    res = client.patch(f"/api/employees/{IDS['alice']}", json={"role": "manager"}, headers=auth("admin"))
    assert res.status_code == 200
    assert ("role", IDS["alice"], "manager") in client.kc.calls


def test_r5_external_ip(client):
    d = doc_id("carol", "internal")
    # TestClient kết nối từ "testclient" (không phải IP) -> không thuộc dải nội bộ
    assert client.delete(f"/api/documents/{d}", headers=auth("admin")).json()["error"] == "Forbidden (R5_INTERNAL_IP)"
    with mock.patch("app.authz.client_ip", return_value="10.1.2.3"):
        assert client.delete(f"/api/documents/{d}", headers=auth("admin")).status_code == 204


@pytest.mark.parametrize("user,dept,expected", [("it.manager", "IT", 200), ("it.manager", "HR", 403), ("alice", "IT", 403), ("admin", "HR", 200)])
def test_r6_department_report(client, user, dept, expected):
    assert client.get(f"/api/departments/{dept}/reports", headers=auth(user)).status_code == expected


def test_log_schema(client):
    client.get(f"/api/documents/{doc_id('alice', 'internal')}", headers={**auth("bob"), "X-Scenario-Id": "S-test"})
    log = db.get_db().audit_logs.find_one({"scenario_id": "S-test"})
    expected = {"timestamp", "request_id", "user_id", "role", "department", "ip", "method", "endpoint", "resource_id",
                "resource_owner_id", "http_status", "decision", "policy_rule", "latency_ms", "user_agent", "scenario_id"}
    assert expected <= set(log)
    assert (log["decision"], log["policy_rule"], log["http_status"], log["user_id"]) == ("deny", "DEFAULT_DENY", 403, IDS["bob"])
    assert isinstance(log["timestamp"], datetime)
